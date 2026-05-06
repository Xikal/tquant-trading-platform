from __future__ import annotations

import re

from app.services.market.shared import (
    DataSourceError,
    KlineBar,
    MinuteBarSnapshot,
    QuoteSnapshot,
    _safe_float,
    _safe_str,
    datetime,
    func,
    guess_market,
    json,
    requests,
    select,
    subprocess,
    sys,
    time,
)

_SAFE_AKSHARE_SYMBOL_RE = re.compile(r"^[A-Za-z0-9]+$")


class MarketIntradayMixin:
    def _fetch_tencent_minute_bars(self, symbol: str) -> list[KlineBar]:
        tencent_symbol = self._to_tencent_symbol(symbol)
        try:
            response = self.session.get("https://ifzq.gtimg.cn/appstock/app/minute/query", params={"code": tencent_symbol}, timeout=self.settings.http_timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(f"腾讯分钟线请求失败: {exc}") from exc
        symbol_payload = ((payload.get("data") or {}).get(tencent_symbol) or {})
        data_payload = symbol_payload.get("data") or {}
        rows = data_payload.get("data") or []
        trade_date = _safe_str(data_payload.get("date"))
        if not rows or not trade_date:
            raise DataSourceError(f"腾讯分钟线未返回 {symbol} 的有效数据。")
        qt_payload = symbol_payload.get("qt") or {}
        qt_fields = qt_payload.get(tencent_symbol) if isinstance(qt_payload, dict) else None
        prev_close = _safe_float(qt_fields[4]) if isinstance(qt_fields, list) and len(qt_fields) > 4 else 0.0
        bars: list[KlineBar] = []
        previous_close = prev_close
        previous_volume = 0.0
        previous_amount = 0.0
        trade_day = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        for raw in rows:
            parts = _safe_str(raw).split()
            if len(parts) < 4:
                continue
            hhmm = parts[0].strip()
            close_price = _safe_float(parts[1])
            cumulative_volume = _safe_float(parts[2])
            cumulative_amount = _safe_float(parts[3])
            if len(hhmm) != 4 or close_price <= 0:
                continue
            minute_timestamp = f"{trade_day} {hhmm[:2]}:{hhmm[2:]}"
            open_price = previous_close or close_price
            high_price = max(open_price, close_price)
            low_price = min(open_price, close_price)
            minute_volume = max(cumulative_volume - previous_volume, 0.0)
            minute_amount = max(cumulative_amount - previous_amount, 0.0)
            amplitude = round((high_price - low_price) / open_price * 100, 4) if open_price else None
            change_pct = round((close_price - open_price) / open_price * 100, 4) if open_price else None
            bars.append(KlineBar(timestamp=minute_timestamp, open=open_price, close=close_price, high=high_price, low=low_price, volume=minute_volume, amount=minute_amount, amplitude=amplitude, change_pct=change_pct, turnover=None))
            previous_close = close_price
            previous_volume = cumulative_volume
            previous_amount = cumulative_amount
        if not bars:
            raise DataSourceError(f"未解析到 {symbol} 的腾讯分钟线数据。")
        return bars

    def _fetch_sina_minute_bars_subprocess(self, symbol: str) -> list[KlineBar]:
        sina_symbol = self._to_sina_symbol(symbol)
        if not _SAFE_AKSHARE_SYMBOL_RE.fullmatch(sina_symbol):
            raise DataSourceError(f"非法证券代码，已拒绝分钟线子进程回退: {symbol}")
        script = (
            "import json\n"
            "import akshare as ak\n"
            f"df = ak.stock_zh_a_minute(symbol='{sina_symbol}', period='1', adjust='')\n"
            "print(json.dumps(df.tail(240).to_dict('records'), ensure_ascii=False, default=str))\n"
        )
        try:
            result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, timeout=max(int(self.settings.http_timeout), 10) + 20)
            rows = json.loads(result.stdout)
        except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
            stderr = (exc.stderr or "").strip() if isinstance(exc, subprocess.CalledProcessError) else ""
            detail = f"{exc}" if not stderr else f"{exc}; stderr={stderr[:200]}"
            raise DataSourceError(f"分钟线子进程回退失败: {detail}") from exc
        bars: list[KlineBar] = []
        for row in rows:
            open_price = _safe_float(row.get("open"))
            high_price = _safe_float(row.get("high"))
            low_price = _safe_float(row.get("low"))
            close_price = _safe_float(row.get("close"))
            timestamp = _safe_str(row.get("day"))[:16]
            if not timestamp or close_price <= 0:
                continue
            amplitude = round((high_price - low_price) / open_price * 100, 4) if open_price else None
            change_pct = round((close_price - open_price) / open_price * 100, 4) if open_price else None
            bars.append(KlineBar(timestamp=timestamp, open=open_price or close_price, close=close_price, high=high_price or close_price, low=low_price or close_price, volume=_safe_float(row.get("volume")), amount=_safe_float(row.get("amount")), amplitude=amplitude, change_pct=change_pct, turnover=None))
        if not bars:
            raise DataSourceError(f"分钟线子进程未解析到 {symbol} 的有效数据。")
        return bars

    def get_intraday_bars(self, symbol: str, period: str = "5m", limit: int = 240) -> list[KlineBar]:
        cache_key = f"{symbol}:{period}"
        cached = self._get_intraday_cache(cache_key)
        if cached is not None:
            return cached[-limit:]
        if period == "1m":
            bars = self._load_one_minute_bars(symbol)
            self._set_intraday_cache(cache_key, bars)
            return bars[-limit:]
        base_bars = self._load_one_minute_bars(symbol)
        bars = self._aggregate_bars(base_bars, interval_minutes={"5m": 5, "15m": 15}.get(period, 5))
        if not bars:
            raise DataSourceError(f"未获取到 {symbol} 的 {period} 分钟K线。")
        self._set_intraday_cache(cache_key, bars)
        return bars[-limit:]

    def get_intraday_bars_batch(
        self,
        symbols: list[str],
        period: str = "1m",
        limit: int = 30,
        max_workers: int = 8,
    ) -> dict[str, list[KlineBar]]:
        """Fetch intraday bars concurrently for independent symbols."""
        import logging
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cleaned_symbols = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol and symbol.strip()))
        if not cleaned_symbols:
            return {}

        logger = logging.getLogger(__name__)
        results: dict[str, list[KlineBar]] = {}
        workers = min(max(1, max_workers), len(cleaned_symbols))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="intraday-bars") as pool:
            futures = {
                pool.submit(self.get_intraday_bars, symbol, period, limit): symbol
                for symbol in cleaned_symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    bars = future.result()
                except Exception:
                    logger.warning("intraday bars batch failed for %s", symbol, exc_info=True)
                    continue
                if bars:
                    results[symbol] = bars
        return results

    def get_tick_snapshot(self, symbol: str) -> dict[str, object]:
        """Return a compact real-time snapshot for intraday confirmation.

        Free data sources do not provide stable Level2 depth.  This method keeps
        the contract explicit by returning quote-derived depth estimates and a
        `depth_quality` marker so higher layers can avoid over-trusting it.
        """

        quote = self.get_quote(symbol)
        spread = max(float(quote.last_price or 0) * 0.001, 0.001)
        return {
            "symbol": quote.symbol,
            "name": quote.name,
            "last_price": quote.last_price,
            "change_pct": quote.change_pct,
            "open_price": quote.open_price,
            "high_price": quote.high_price,
            "low_price": quote.low_price,
            "prev_close": quote.prev_close,
            "volume": quote.volume,
            "amount": quote.amount,
            "timestamp": quote.timestamp,
            "best_bid": round(max(float(quote.last_price or 0) - spread, 0), 4),
            "best_ask": round(float(quote.last_price or 0) + spread, 4),
            "spread_pct": round(spread / max(float(quote.last_price or 0), 0.01) * 100, 4),
            "depth_quality": "quote_estimate",
        }

    def get_volume_profile(self, symbol: str, period: str = "1m", limit: int = 240) -> dict[str, object]:
        bars = self.get_intraday_bars(symbol, period=period, limit=limit)
        if not bars:
            raise DataSourceError(f"未获取到 {symbol} 的分时成交分布。")
        midpoint = max(len(bars) // 2, 1)
        morning = bars[:midpoint]
        afternoon = bars[midpoint:]
        last_30 = bars[-30:]
        return {
            "symbol": symbol,
            "period": period,
            "bar_count": len(bars),
            "total_volume": round(sum(float(bar.volume or 0) for bar in bars), 2),
            "total_amount": round(sum(float(bar.amount or 0) for bar in bars), 2),
            "morning_amount": round(sum(float(bar.amount or 0) for bar in morning), 2),
            "afternoon_amount": round(sum(float(bar.amount or 0) for bar in afternoon), 2),
            "last_30m_amount": round(sum(float(bar.amount or 0) for bar in last_30), 2),
            "vwap": self._profile_vwap(bars),
            "close_position": self._profile_close_position(bars),
        }

    def get_big_order_tracker(self, symbol: str, period: str = "1m", limit: int = 120) -> dict[str, object]:
        bars = self.get_intraday_bars(symbol, period=period, limit=limit)
        if not bars:
            raise DataSourceError(f"未获取到 {symbol} 的大单追踪基础数据。")
        avg_amount = sum(float(bar.amount or 0) for bar in bars) / max(len(bars), 1)
        large_bars = [bar for bar in bars if float(bar.amount or 0) >= avg_amount * 1.8 and float(bar.amount or 0) > 0]
        active_buy_amount = sum(float(bar.amount or 0) for bar in large_bars if float(bar.close or 0) >= float(bar.open or 0))
        active_sell_amount = sum(float(bar.amount or 0) for bar in large_bars if float(bar.close or 0) < float(bar.open or 0))
        total_large = active_buy_amount + active_sell_amount
        net_ratio = (active_buy_amount - active_sell_amount) / max(total_large, 1.0)
        return {
            "symbol": symbol,
            "period": period,
            "bar_count": len(bars),
            "large_bar_count": len(large_bars),
            "active_buy_amount": round(active_buy_amount, 2),
            "active_sell_amount": round(active_sell_amount, 2),
            "net_amount": round(active_buy_amount - active_sell_amount, 2),
            "net_ratio": round(net_ratio, 4),
            "quality": "minute_amount_estimate",
            "note": "免费数据源无逐笔大单，本结果按分钟成交额异常放大估算。",
        }

    def get_intraday_bars_for_analysis(self, db, quote: QuoteSnapshot, period: str = "5m", limit: int = 240, persist_snapshots: bool = True) -> list[KlineBar]:
        cache_key = f"{quote.symbol}:{period}"
        cached = self._get_intraday_cache(cache_key)
        if cached is not None:
            if persist_snapshots:
                base_cache_key = f"{quote.symbol}:1m"
                base_bars = self._get_intraday_cache(base_cache_key)
                if base_bars is None:
                    base_bars = self._load_one_minute_bars(quote.symbol)
                    self._set_intraday_cache(base_cache_key, base_bars)
                self.persist_minute_snapshots(
                    db,
                    quote,
                    base_bars[-240:] if len(base_bars) > 240 else base_bars,
                    bar_period="1m",
                )
            return cached[-limit:]
        base_bars = self._load_one_minute_bars(quote.symbol)
        self._set_intraday_cache(f"{quote.symbol}:1m", base_bars)
        if persist_snapshots:
            self.persist_minute_snapshots(db, quote, base_bars[-240:] if len(base_bars) > 240 else base_bars, bar_period="1m")
        if period == "1m":
            self._set_intraday_cache(cache_key, base_bars)
            return base_bars[-limit:]
        bars = self._aggregate_bars(base_bars, interval_minutes={"5m": 5, "15m": 15}.get(period, 5))
        if not bars:
            raise DataSourceError(f"未聚合出 {quote.symbol} 的 {period} 分钟K线。")
        self._set_intraday_cache(cache_key, bars)
        return bars[-limit:]

    def persist_minute_snapshots(self, db, quote: QuoteSnapshot, bars: list[KlineBar], bar_period: str = "1m") -> int:
        if not bars:
            return 0
        latest_stored = db.execute(select(func.max(MinuteBarSnapshot.bar_timestamp)).where(MinuteBarSnapshot.symbol == quote.symbol, MinuteBarSnapshot.bar_period == bar_period)).scalar_one()
        candidate_bars = [bar for bar in bars if not latest_stored or bar.timestamp >= str(latest_stored)]
        if not candidate_bars:
            return 0
        existing_rows = db.execute(select(MinuteBarSnapshot).where(MinuteBarSnapshot.symbol == quote.symbol, MinuteBarSnapshot.bar_period == bar_period, MinuteBarSnapshot.bar_timestamp.in_([bar.timestamp for bar in candidate_bars]))).scalars().all()
        rows_by_timestamp = {row.bar_timestamp: row for row in existing_rows}
        persisted = 0
        for bar in candidate_bars:
            row = rows_by_timestamp.get(bar.timestamp)
            if row is None:
                row = MinuteBarSnapshot(symbol=quote.symbol, market=quote.market, instrument_type=quote.instrument_type, bar_period=bar_period, bar_timestamp=bar.timestamp)
                db.add(row)
                persisted += 1
            row.quote_timestamp = quote.timestamp
            row.last_price = quote.last_price
            row.change_pct = quote.change_pct
            row.open_price = bar.open
            row.close_price = bar.close
            row.high_price = bar.high
            row.low_price = bar.low
            row.volume = bar.volume
            row.amount = bar.amount
        if persisted or existing_rows:
            db.commit()
        return len(candidate_bars)

    @staticmethod
    def _profile_vwap(bars: list[KlineBar]) -> float:
        amount = sum(float(bar.amount or 0) for bar in bars)
        volume = sum(float(bar.volume or 0) for bar in bars)
        if amount > 0 and volume > 0:
            raw = amount / volume
            latest_close = float(bars[-1].close or 0)
            if latest_close > 0 and raw > latest_close * 20:
                raw = raw / 100
            return round(raw, 4)
        weighted = sum(float(bar.close or 0) * float(bar.volume or 0) for bar in bars)
        return round(weighted / volume, 4) if volume > 0 else 0.0

    @staticmethod
    def _profile_close_position(bars: list[KlineBar]) -> float:
        high = max(float(bar.high or 0) for bar in bars)
        low = min(float(bar.low or 0) for bar in bars if float(bar.low or 0) > 0)
        close = float(bars[-1].close or 0)
        return round((close - low) / max(high - low, 0.01), 4) if close > 0 else 0.0

    def _fetch_json(self, url: str, params: dict[str, object]) -> dict[str, object]:
        try:
            response = self.session.get(url, params=params, timeout=self.settings.http_timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            payload = self._fetch_json_by_curl(url, params)
        if payload.get("rc") not in (0, None):
            raise DataSourceError(payload.get("rt", "数据源返回异常"))
        return payload

    def _fetch_json_by_curl(self, url: str, params: dict[str, object]) -> dict[str, object]:
        query = __import__("urllib.parse").parse.urlencode(params, safe=",:")
        full_url = f"{url}?{query}"
        request = __import__("urllib.request").request.Request(
            full_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/",
            },
        )
        try:
            with __import__("urllib.request").request.urlopen(
                request,
                timeout=max(int(self.settings.http_timeout), 10) + 5,
            ) as response:
                return json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception as exc:
            raise DataSourceError(f"数据源请求失败: {exc}") from exc

    def _fetch_trend_bars(self, symbol: str) -> list[KlineBar]:
        payload = self._fetch_json("https://push2his.eastmoney.com/api/qt/stock/trends2/get", params={"fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58", "ut": "7eea3edcaed734bea9cbfc24409ed989", "ndays": "5", "iscr": "0", "secid": __import__('app.services.market.shared', fromlist=['to_secid']).to_secid(symbol)})
        raw_bars = (payload.get("data") or {}).get("trends") or []
        if not raw_bars:
            raise DataSourceError(f"未获取到 {symbol} 的 1m 分钟K线。")
        bars: list[KlineBar] = []
        for item in raw_bars:
            parts = item.split(",")
            if len(parts) < 8:
                continue
            close_price = float(parts[2])
            open_price = float(parts[1]) if parts[1] not in {"", "0", "0.000"} else close_price
            bars.append(KlineBar(timestamp=parts[0], open=open_price, close=close_price, high=float(parts[3]), low=float(parts[4]), volume=float(parts[5]), amount=float(parts[6]), amplitude=None, change_pct=None, turnover=None))
        if not bars:
            raise DataSourceError(f"未解析到 {symbol} 的分钟线数据。")
        return bars

    def _fetch_sina_quote_fields(self, symbol: str) -> list[str]:
        url = f"https://hq.sinajs.cn/list={self._to_sina_symbol(symbol)}"
        try:
            response = self.session.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=self.settings.http_timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DataSourceError(f"新浪实时行情请求失败: {exc}") from exc
        response.encoding = "gbk"
        text = response.text.strip()
        if '="' not in text:
            raise DataSourceError(f"新浪实时行情返回异常: {text[:80]}")
        return text.split('="', 1)[1].rsplit('"', 1)[0].split(",")

    def _fetch_sina_minute_bars(self, symbol: str, period: str) -> list[KlineBar]:
        ak = __import__("app.services.market.shared", fromlist=["ak"]).ak
        if ak is None:
            raise DataSourceError("未安装 akshare，无法使用新浪分钟线数据。")
        df = self._call_akshare(
            ak.stock_zh_a_minute,
            symbol=self._to_sina_symbol(symbol),
            period=period.replace("m", ""),
            adjust="",
            purpose="minute_bars",
        )
        if df.empty:
            raise DataSourceError(f"未获取到 {symbol} 的 {period} 分钟K线。")
        bars: list[KlineBar] = []
        for row in df.tail(1970).to_dict("records"):
            open_price = float(row["open"])
            high_price = float(row["high"])
            low_price = float(row["low"])
            close_price = float(row["close"])
            amplitude = round((high_price - low_price) / open_price * 100, 4) if open_price else None
            change_pct = round((close_price - open_price) / open_price * 100, 4) if open_price else None
            bars.append(KlineBar(timestamp=str(row["day"])[:16], open=open_price, close=close_price, high=high_price, low=low_price, volume=float(row["volume"]), amount=float(row["amount"]), amplitude=amplitude, change_pct=change_pct, turnover=None))
        if not bars:
            raise DataSourceError(f"未解析到 {symbol} 的新浪分钟线数据。")
        return bars

    def _load_one_minute_bars(self, symbol: str) -> list[KlineBar]:
        if self._market_provider_router_enabled():
            result = self.provider_router.fetch_intraday_bars(symbol)
            if result.usable and result.data:
                return list(result.data)
        return self.intraday_router.load_one_minute_bars(symbol)

    def _to_tencent_symbol(self, symbol: str) -> str:
        market = guess_market(symbol)
        if market == "SH":
            return f"sh{symbol}"
        if market == "BJ":
            return f"bj{symbol}"
        return f"sz{symbol}"

    @classmethod
    def _get_intraday_cache(cls, cache_key: str):
        now = time.monotonic()
        with cls._cache_lock:
            expired = [key for key, value in cls._intraday_cache.items() if value[0] <= now]
            for key in expired:
                cls._intraday_cache.pop(key, None)
            if len(cls._intraday_cache) > 3000:
                sorted_keys = sorted(cls._intraday_cache.keys(), key=lambda key: cls._intraday_cache[key][0])
                for key in sorted_keys[:600]:
                    cls._intraday_cache.pop(key, None)
            cached = cls._intraday_cache.get(cache_key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                cls._intraday_cache.pop(cache_key, None)
                return None
            return list(payload)

    @classmethod
    def _set_intraday_cache(cls, cache_key: str, payload: list[KlineBar]) -> None:
        with cls._cache_lock:
            cls._intraday_cache[cache_key] = (time.monotonic() + cls._intraday_cache_ttl, list(payload))

    @staticmethod
    def _aggregate_bars(bars: list[KlineBar], interval_minutes: int) -> list[KlineBar]:
        if interval_minutes <= 1:
            return bars
        grouped: list[KlineBar] = []
        bucket: list[KlineBar] = []
        bucket_key = None
        for bar in bars:
            current_key = MarketIntradayMixin._bucket_start(bar.timestamp, interval_minutes)
            if bucket_key is None:
                bucket_key = current_key
            if current_key != bucket_key and bucket:
                grouped.append(MarketIntradayMixin._merge_bucket(bucket_key, bucket))
                bucket, bucket_key = [], current_key
            bucket.append(bar)
        if bucket and bucket_key is not None:
            grouped.append(MarketIntradayMixin._merge_bucket(bucket_key, bucket))
        return grouped

    @staticmethod
    def _bucket_start(timestamp: str, interval_minutes: int) -> str:
        dt = datetime.strptime(timestamp[:16], "%Y-%m-%d %H:%M")
        bucket_dt = dt.replace(minute=(dt.minute // interval_minutes) * interval_minutes, second=0, microsecond=0)
        return bucket_dt.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _merge_bucket(bucket_key: str, bucket: list[KlineBar]) -> KlineBar:
        open_price = next((item.open for item in bucket if item.open > 0), bucket[0].close)
        close_price = bucket[-1].close
        high_price = max(item.high for item in bucket)
        low_price = min(item.low for item in bucket)
        volume = sum(item.volume for item in bucket)
        amount = sum(item.amount for item in bucket)
        change_pct = round((close_price - open_price) / open_price * 100, 4) if open_price else None
        amplitude = round((high_price - low_price) / open_price * 100, 4) if open_price else None
        return KlineBar(timestamp=bucket_key, open=open_price, close=close_price, high=high_price, low=low_price, volume=volume, amount=amount, amplitude=amplitude, change_pct=change_pct, turnover=None)
