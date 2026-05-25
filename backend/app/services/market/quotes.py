from __future__ import annotations

from app.services.market.local_quote_cache import read_local_quote_snapshot, write_local_quote_snapshot
from app.services.market.go_read_client import load_go_market_read_quotes
from app.services.market.spot_snapshot import fetch_eastmoney_stock_spot_snapshot_map
from app.services.market.shared import (
    DataSourceError,
    KlineBar,
    QuoteSnapshot,
    _safe_float,
    _safe_str,
    datetime,
    guess_instrument_type,
    guess_market,
    requests,
    subprocess,
    sys,
    time,
    to_secid,
)


class MarketQuoteMixin:
    _provider_router_flag_cache: tuple[float, bool] = (0.0, False)
    _provider_router_flag_ttl_seconds = 30.0

    def get_quote(self, symbol: str, force_refresh: bool = False) -> QuoteSnapshot:
        cached = None if force_refresh else self._get_quote_cache(symbol)
        if cached is not None:
            return cached
        distributed = None if force_refresh else read_local_quote_snapshot(symbol)
        if distributed is not None:
            self._set_quote_cache(symbol, distributed, persist_local=False)
            return distributed
        if self._market_provider_router_enabled():
            result = self.provider_router.fetch_quote(symbol)
            if result.usable and result.data is not None:
                snapshot = result.data.model_copy(
                    update={
                        "data_source": result.source,
                        "source_quality": result.quality.value,
                        "data_quality": result.quality.value,
                        "data_quality_message": result.message,
                        "is_stale": result.quality.value != "fresh",
                    }
                )
                self._set_quote_cache(symbol, snapshot)
                return snapshot
        snapshot = self.quote_router.fetch(symbol)
        self._set_quote_cache(symbol, snapshot)
        return snapshot

    @staticmethod
    def _market_provider_router_enabled() -> bool:
        now = time.monotonic()
        expires_at, cached_value = MarketQuoteMixin._provider_router_flag_cache
        if now < expires_at:
            return cached_value
        try:
            from app.core.database import SessionLocal
            from app.core.config import get_settings
            from app.services.shared.feature_flags import feature_enabled

            with SessionLocal() as db:
                enabled = feature_enabled(db, "market_provider_router_enabled", get_settings().market_provider_router_enabled)
        except Exception:
            try:
                from app.core.config import get_settings

                enabled = get_settings().market_provider_router_enabled
            except Exception:
                enabled = True
        MarketQuoteMixin._provider_router_flag_cache = (
            now + MarketQuoteMixin._provider_router_flag_ttl_seconds,
            enabled,
        )
        return enabled

    @staticmethod
    def clear_market_provider_router_flag_cache() -> None:
        MarketQuoteMixin._provider_router_flag_cache = (0.0, False)

    def get_quotes_batch(
        self,
        symbols: list[str],
        force_refresh: bool = False,
        allow_slow_fallback: bool = True,
    ) -> dict[str, QuoteSnapshot]:
        ordered_symbols = [symbol.strip() for symbol in symbols if symbol and symbol.strip()]
        if not ordered_symbols:
            return {}
        deduped_symbols = list(dict.fromkeys(ordered_symbols))
        result: dict[str, QuoteSnapshot] = {}
        remaining: list[str] = []
        for symbol in deduped_symbols:
            cached = None if force_refresh else self._get_quote_cache(symbol)
            if cached is not None:
                result[symbol] = cached
            else:
                distributed = None if force_refresh else read_local_quote_snapshot(symbol)
                if distributed is not None:
                    self._set_quote_cache(symbol, distributed, persist_local=False)
                    result[symbol] = distributed
                else:
                    remaining.append(symbol)
        if remaining:
            batch_quotes: dict[str, QuoteSnapshot] = {}
            if not force_refresh:
                remote_quotes = load_go_market_read_quotes(remaining)
                for symbol, snapshot in remote_quotes.items():
                    batch_quotes[symbol] = snapshot
                    self._set_quote_cache(symbol, snapshot, persist_local=False)
                    result[symbol] = snapshot
                if remote_quotes:
                    remaining = [symbol for symbol in remaining if symbol not in remote_quotes]
            if allow_slow_fallback and self._market_provider_router_enabled():
                unresolved: list[str] = []
                for symbol in remaining:
                    try:
                        batch_quotes[symbol] = self.get_quote(symbol, force_refresh=force_refresh)
                    except Exception:
                        unresolved.append(symbol)
                remaining = unresolved
            if remaining:
                batch_quotes.update(
                    self.quote_router.fetch_batch(
                        remaining,
                        allow_slow_fallback=allow_slow_fallback,
                    )
                )
            for symbol, snapshot in batch_quotes.items():
                self._set_quote_cache(symbol, snapshot)
                result[symbol] = snapshot
        return result

    def get_stock_spot_snapshot_map(self, *, force_refresh: bool = False) -> dict[str, QuoteSnapshot]:
        cached = None if force_refresh else self._get_spot_snapshot_cache("stock")
        if cached is not None:
            return cached
        snapshot_map = fetch_eastmoney_stock_spot_snapshot_map(self)
        if snapshot_map:
            self._set_spot_snapshot_cache("stock", snapshot_map)
        return snapshot_map

    def _fetch_quote_from_spot_snapshot(self, symbol: str) -> QuoteSnapshot:
        result = self.provider_router.fetch_quote(symbol)
        if result.usable and result.data is not None:
            return result.data
        raise DataSourceError(result.message or f"Provider Router 未返回 {symbol} 的现货快照。")

    def _fetch_eastmoney_realtime_quote(self, symbol: str) -> QuoteSnapshot:
        snapshots = self._fetch_eastmoney_realtime_quotes_batch([symbol])
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            raise DataSourceError(f"东方财富实时行情未返回 {symbol}。")
        return snapshot

    def _fetch_eastmoney_realtime_quotes_batch(self, symbols: list[str]) -> dict[str, QuoteSnapshot]:
        """Fetch free Eastmoney real-time quotes for arbitrary A-share symbols.

        Eastmoney `ulist.np/get` is a free public web endpoint used as the
        second real-time source after Tencent.  It is not treated as an
        exchange-guaranteed feed, so every snapshot carries freshness metadata.
        """

        cleaned_symbols = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol and symbol.strip()))
        if not cleaned_symbols:
            return {}
        payload = self._fetch_json(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={
                "fltt": "2",
                "fields": "f12,f13,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18,f8,f10,f124",
                "secids": ",".join(to_secid(symbol) for symbol in cleaned_symbols),
            },
        )
        rows = ((payload.get("data") or {}).get("diff") or [])
        result: dict[str, QuoteSnapshot] = {}
        for row in rows:
            symbol = _safe_str(row.get("f12")).strip()
            if not symbol:
                continue
            snapshot = self._build_eastmoney_realtime_quote_snapshot(symbol, row)
            if snapshot.last_price > 0:
                result[symbol] = snapshot
        return result

    def _build_eastmoney_realtime_quote_snapshot(self, symbol: str, row: dict) -> QuoteSnapshot:
        timestamp = self._normalize_eastmoney_timestamp(row.get("f124"))
        name = _safe_str(row.get("f14")) or symbol
        return QuoteSnapshot(
            symbol=symbol,
            name=name,
            market="SH" if str(row.get("f13")) == "1" else "SZ",
            instrument_type=guess_instrument_type(symbol, name),
            last_price=_safe_float(row.get("f2")),
            change_pct=_safe_float(row.get("f3")),
            change_amount=_safe_float(row.get("f4")),
            open_price=_safe_float(row.get("f17")),
            high_price=_safe_float(row.get("f15")),
            low_price=_safe_float(row.get("f16")),
            prev_close=_safe_float(row.get("f18")),
            volume=_safe_float(row.get("f5")),
            amount=_safe_float(row.get("f6")),
            turnover_rate=_safe_float(row.get("f8")) or None,
            volume_ratio=_safe_float(row.get("f10")) or None,
            timestamp=timestamp,
            data_source="eastmoney_realtime",
            source_quality="free_realtime",
            is_stale=self._is_quote_timestamp_stale(timestamp),
        )

    def _fetch_quote_from_trends(self, symbol: str) -> QuoteSnapshot:
        payload = self._fetch_json("https://push2his.eastmoney.com/api/qt/stock/trends2/get", params={"fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58", "ut": "7eea3edcaed734bea9cbfc24409ed989", "ndays": "5", "iscr": "0", "secid": to_secid(symbol)})
        data = payload.get("data") or {}
        raw_bars = data.get("trends") or []
        if not raw_bars:
            raise DataSourceError(f"东财分时未返回 {symbol} 的 trends 数据。")
        bars = self._fetch_trend_bars(symbol)
        latest_bar = bars[-1]
        latest_date = latest_bar.timestamp.split(" ", 1)[0]
        day_bars = [bar for bar in bars if bar.timestamp.startswith(latest_date)]
        previous_day_close = None
        for bar in reversed(bars[:-1]):
            if bar.timestamp.split(" ", 1)[0] != latest_date:
                previous_day_close = bar.close
                break
        prev_close = _safe_float(data.get("preClose")) or _safe_float(previous_day_close) or latest_bar.close
        last_price = latest_bar.close
        change_amount = round(last_price - prev_close, 4)
        change_pct = round((change_amount / prev_close) * 100, 4) if prev_close else 0.0
        name = _safe_str(data.get("name")) or symbol
        market = guess_market(symbol)
        return QuoteSnapshot(symbol=symbol, name=name, market=market, instrument_type=guess_instrument_type(symbol, name), last_price=last_price, change_pct=change_pct, change_amount=change_amount, open_price=day_bars[0].open, high_price=max(bar.high for bar in day_bars), low_price=min(bar.low for bar in day_bars), prev_close=prev_close, volume=round(sum(bar.volume for bar in day_bars), 4), amount=round(sum(bar.amount for bar in day_bars), 4), turnover_rate=None, volume_ratio=None, timestamp=latest_bar.timestamp)

    def _fetch_eastmoney_quote(self, symbol: str) -> QuoteSnapshot:
        return self._fetch_quote_from_trends(symbol)

    def _fetch_quote_from_minute_bars(self, symbol: str) -> QuoteSnapshot:
        try:
            bars = self._fetch_tencent_minute_bars(symbol)
        except Exception:
            try:
                bars = self._fetch_sina_minute_bars(symbol, "1m")
            except Exception:
                bars = self._fetch_sina_minute_bars_subprocess(symbol)
        if not bars:
            raise DataSourceError(f"分钟线数据未返回 {symbol} 的盘中数据。")
        latest_bar = bars[-1]
        latest_date = latest_bar.timestamp.split(" ", 1)[0]
        day_bars = [bar for bar in bars if bar.timestamp.startswith(latest_date)]
        prev_close = None
        for bar in reversed(bars[:-1]):
            if not bar.timestamp.startswith(latest_date):
                prev_close = bar.close
                break
        prev_close = prev_close or day_bars[0].open or latest_bar.close
        last_price = latest_bar.close
        change_amount = round(last_price - prev_close, 4)
        change_pct = round((change_amount / prev_close) * 100, 4) if prev_close else 0.0
        market = guess_market(symbol)
        return QuoteSnapshot(symbol=symbol, name=symbol, market=market, instrument_type=guess_instrument_type(symbol), last_price=last_price, change_pct=change_pct, change_amount=change_amount, open_price=day_bars[0].open, high_price=max(bar.high for bar in day_bars), low_price=min(bar.low for bar in day_bars), prev_close=prev_close, volume=round(sum(bar.volume for bar in day_bars), 4), amount=round(sum(bar.amount for bar in day_bars), 4), turnover_rate=None, volume_ratio=None, timestamp=latest_bar.timestamp)

    def _fetch_tencent_quote(self, symbol: str) -> QuoteSnapshot:
        url = f"https://qt.gtimg.cn/q={self._to_sina_symbol(symbol)}"
        try:
            response = self.session.get(url, timeout=self.settings.market_quote_timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DataSourceError(f"腾讯实时行情请求失败: {exc}") from exc
        response.encoding = "gbk"
        text = response.text.strip()
        if '="' not in text:
            raise DataSourceError(f"腾讯实时行情返回异常: {text[:80]}")
        payload = text.split('="', 1)[1].rsplit('"', 1)[0]
        return self._build_tencent_quote_snapshot(symbol, payload.split("~"))

    def _fetch_tencent_quotes_batch(self, symbols: list[str]) -> dict[str, QuoteSnapshot]:
        if not symbols:
            return {}
        sina_symbols = [self._to_sina_symbol(symbol) for symbol in symbols]
        sina_map = dict(zip(sina_symbols, symbols))
        url = f"https://qt.gtimg.cn/q={','.join(sina_symbols)}"
        try:
            response = self.session.get(url, timeout=self.settings.market_batch_timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DataSourceError(f"腾讯批量实时行情请求失败: {exc}") from exc
        response.encoding = "gbk"
        result: dict[str, QuoteSnapshot] = {}
        for line in [chunk.strip() for chunk in response.text.strip().split(";") if chunk.strip()]:
            if '="' not in line:
                continue
            header, payload = line.split('="', 1)
            symbol = sina_map.get(header.rsplit("_", 1)[-1].strip()) or header.rsplit("_", 1)[-1].strip()[-6:]
            try:
                result[symbol] = self._build_tencent_quote_snapshot(symbol, payload.rsplit('"', 1)[0].split("~"))
            except DataSourceError:
                continue
        return result

    def _build_tencent_quote_snapshot(self, symbol: str, fields: list[str]) -> QuoteSnapshot:
        if len(fields) < 38:
            raise DataSourceError(f"腾讯实时行情字段不足: {fields[:6]}")
        name = _safe_str(fields[1]) or symbol
        timestamp_raw = _safe_str(fields[30])
        timestamp = timestamp_raw
        if len(timestamp_raw) == 14 and timestamp_raw.isdigit():
            timestamp = datetime.strptime(timestamp_raw, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        normalized_timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return QuoteSnapshot(symbol=symbol, name=name, market=guess_market(symbol), instrument_type=guess_instrument_type(symbol, name), last_price=_safe_float(fields[3]), change_pct=_safe_float(fields[32]), change_amount=_safe_float(fields[31]), open_price=_safe_float(fields[5]), high_price=_safe_float(fields[33]), low_price=_safe_float(fields[34]), prev_close=_safe_float(fields[4]), volume=_safe_float(fields[36] or fields[6]), amount=_safe_float(fields[37], scale=0.0001), turnover_rate=None, volume_ratio=None, timestamp=normalized_timestamp, data_source="tencent_realtime", source_quality="free_realtime", is_stale=self._is_quote_timestamp_stale(normalized_timestamp))

    def _fetch_sina_quote(self, symbol: str) -> QuoteSnapshot:
        fields = self._fetch_sina_quote_fields(symbol)
        if len(fields) < 32:
            raise DataSourceError(f"未获取到 {symbol} 的新浪实时行情。")
        name = _safe_str(fields[0]) or symbol
        prev_close = _safe_float(fields[2])
        last_price = _safe_float(fields[3])
        change_amount = round(last_price - prev_close, 4)
        change_pct = round((change_amount / prev_close * 100), 4) if prev_close else 0.0
        timestamp = f"{_safe_str(fields[30])} {_safe_str(fields[31])}".strip()
        normalized_timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return QuoteSnapshot(symbol=symbol, name=name, market=guess_market(symbol), instrument_type=guess_instrument_type(symbol, name), last_price=last_price, change_pct=change_pct, change_amount=change_amount, open_price=_safe_float(fields[1]), high_price=_safe_float(fields[4]), low_price=_safe_float(fields[5]), prev_close=prev_close, volume=_safe_float(fields[8]), amount=_safe_float(fields[9]), turnover_rate=None, volume_ratio=None, timestamp=normalized_timestamp, data_source="sina_realtime", source_quality="free_fallback", is_stale=self._is_quote_timestamp_stale(normalized_timestamp))

    @classmethod
    def _get_quote_cache(cls, symbol: str):
        now = time.monotonic()
        with cls._cache_lock:
            cached = cls._quote_cache.get(symbol)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._quote_cache.pop(symbol, None)
                return None
            return payload

    @classmethod
    def _set_quote_cache(cls, symbol: str, payload: QuoteSnapshot, *, persist_local: bool = True) -> None:
        with cls._cache_lock:
            cls._quote_cache[symbol] = (time.monotonic() + cls._quote_cache_ttl, payload)
            if len(cls._quote_cache) > 5000:
                cls._trim_expired_cache(cls._quote_cache, max_items=4000)
        if persist_local:
            write_local_quote_snapshot(payload)

    @classmethod
    def _get_spot_snapshot_cache(cls, instrument_type: str):
        now = time.monotonic()
        with cls._cache_lock:
            cached = cls._spot_snapshot_cache.get(instrument_type)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._spot_snapshot_cache.pop(instrument_type, None)
                return None
            return dict(payload)

    @classmethod
    def _set_spot_snapshot_cache(cls, instrument_type: str, payload: dict[str, QuoteSnapshot]) -> None:
        with cls._cache_lock:
            cls._spot_snapshot_cache[instrument_type] = (
                time.monotonic() + cls._spot_snapshot_cache_ttl,
                dict(payload),
            )

    @staticmethod
    def _trim_expired_cache(cache: dict, max_items: int) -> None:
        now = time.monotonic()
        expired_keys = [key for key, value in cache.items() if value[0] <= now]
        for key in expired_keys:
            cache.pop(key, None)
        if len(cache) <= max_items:
            return
        overflow = len(cache) - max_items
        for key, _ in sorted(cache.items(), key=lambda item: item[1][0])[:overflow]:
            cache.pop(key, None)

    @staticmethod
    def _normalize_quote_timestamp(value: str) -> str:
        if not value:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        raw = value.strip()
        return f"{datetime.now().strftime('%Y-%m-%d')} {raw}" if len(raw) <= 8 and ":" in raw else raw

    @staticmethod
    def _normalize_eastmoney_timestamp(value) -> str:
        try:
            epoch = int(value)
        except (TypeError, ValueError):
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if epoch <= 0:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _is_quote_timestamp_stale(timestamp: str) -> bool:
        try:
            quote_time = datetime.strptime(str(timestamp)[:19], "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            return False
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        current_minute = now.hour * 60 + now.minute
        if not ((9 * 60 + 25) <= current_minute <= (15 * 60 + 10)):
            return False
        return (now - quote_time).total_seconds() > 300

    @staticmethod
    def _to_sina_symbol(symbol: str) -> str:
        prefix_map = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
        return f"{prefix_map.get(guess_market(symbol), 'sh')}{symbol}"
