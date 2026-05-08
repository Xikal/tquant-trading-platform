from __future__ import annotations

from app.core.timezone import beijing_now
from app.models.schemas import KlineBar, MarketEventOut, QuoteSnapshot, SectorSnapshot
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.regime_scoring import normalize_board_frame
from app.services.market.shared import (
    _safe_float,
    _safe_str,
    ak,
    guess_market,
)

_ST_NAME_MARKERS = ("ST", "*ST", "退")
_ST_PREFIX_MARKERS = ("退市",)


class AkshareMarketProvider:
    name = "akshare"

    def __init__(self, service) -> None:
        self.service = service
        self._industry_board_frame_cache = None
        self._spot_snapshot_cache: dict[str, dict[str, QuoteSnapshot]] = {}

    def _raw_call(self, func, *args, purpose: str = "default", **kwargs):  # noqa: ANN001
        raw_client = getattr(self.service, "akshare_raw", None)
        if raw_client is not None:
            return raw_client.call(func, *args, purpose=purpose, **kwargs)
        legacy_call = getattr(self.service, "_call_akshare", None)
        if legacy_call is not None:
            return legacy_call(func, *args, purpose=purpose, **kwargs)
        raise RuntimeError("akshare raw client unavailable")

    def fetch_quote(self, symbol: str) -> ProviderResult[QuoteSnapshot]:
        try:
            instrument_type = (
                "etf"
                if __import__("app.services.market.shared", fromlist=["MarketRuleService"]).MarketRuleService.looks_like_etf(symbol)
                else "stock"
            )
            snapshot = self._load_spot_snapshot_map(instrument_type).get(symbol)
            if snapshot is None:
                raise RuntimeError(f"{instrument_type} spot snapshot missing {symbol}")
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=snapshot)

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult[list[KlineBar]]:
        try:
            bars = self._fetch_sina_minute_bars(symbol, "1m")
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if bars else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=bars or None,
        )

    def _load_spot_snapshot_map(self, instrument_type: str) -> dict[str, QuoteSnapshot]:
        if ak is None:
            raise RuntimeError("akshare unavailable")
        cached = self._spot_snapshot_cache.get(instrument_type)
        if cached is not None:
            return cached
        frame = self._raw_call(
            ak.fund_etf_spot_em if instrument_type == "etf" else ak.stock_zh_a_spot,
            purpose="spot_snapshot",
        )
        if frame is None or getattr(frame, "empty", False):
            raise RuntimeError(f"{instrument_type} spot snapshot empty")
        result: dict[str, QuoteSnapshot] = {}
        for row in frame.to_dict("records"):
            symbol = _safe_str(row.get("代码") or row.get("symbol")).strip()
            if not symbol:
                continue
            if symbol.startswith(("sh", "sz", "bj")):
                symbol = symbol[-6:]
            name = _safe_str(row.get("名称") or row.get("name")) or symbol
            latest_price = _safe_float(row.get("最新价") or row.get("最新"))
            prev_close = _safe_float(row.get("昨收") or row.get("昨收价") or row.get("昨收盘"))
            change_amount = _safe_float(row.get("涨跌额"))
            change_pct = _safe_float(row.get("涨跌幅"))
            if not change_amount and latest_price and prev_close:
                change_amount = round(latest_price - prev_close, 4)
            if not change_pct and change_amount and prev_close:
                change_pct = round((change_amount / prev_close) * 100, 4)
            timestamp = self.service._normalize_quote_timestamp(
                _safe_str(row.get("时间戳") or row.get("更新时间") or row.get("数据日期"))
            )
            result[symbol] = QuoteSnapshot(
                symbol=symbol,
                name=name,
                market=guess_market(symbol),
                instrument_type=instrument_type,
                last_price=latest_price,
                change_pct=change_pct,
                change_amount=change_amount,
                open_price=_safe_float(row.get("今开") or row.get("开盘价") or row.get("开盘")),
                high_price=_safe_float(row.get("最高") or row.get("最高价")),
                low_price=_safe_float(row.get("最低") or row.get("最低价")),
                prev_close=prev_close,
                volume=_safe_float(row.get("成交量") or row.get("成交量(手)")),
                amount=_safe_float(row.get("成交额")),
                turnover_rate=None,
                volume_ratio=None,
                timestamp=timestamp,
                data_source=self.name,
                source_quality=MarketDataQuality.FRESH.value,
                is_stale=False,
            )
        self._spot_snapshot_cache[instrument_type] = result
        return result

    def _fetch_sina_minute_bars(self, symbol: str, period: str) -> list[KlineBar]:
        if ak is None:
            raise RuntimeError("akshare unavailable")
        frame = self._raw_call(
            ak.stock_zh_a_minute,
            symbol=self.service._to_sina_symbol(symbol),
            period=period.replace("m", ""),
            adjust="",
            purpose="minute_bars",
        )
        if frame is None or getattr(frame, "empty", False):
            raise RuntimeError(f"{symbol} minute bars empty")
        bars: list[KlineBar] = []
        for row in frame.tail(1970).to_dict("records"):
            open_price = _safe_float(row.get("open"))
            high_price = _safe_float(row.get("high"))
            low_price = _safe_float(row.get("low"))
            close_price = _safe_float(row.get("close"))
            if close_price <= 0:
                continue
            amplitude = round((high_price - low_price) / open_price * 100, 4) if open_price else None
            change_pct = round((close_price - open_price) / open_price * 100, 4) if open_price else None
            bars.append(
                KlineBar(
                    timestamp=str(row.get("day"))[:16],
                    open=open_price or close_price,
                    close=close_price,
                    high=high_price or close_price,
                    low=low_price or close_price,
                    volume=_safe_float(row.get("volume")),
                    amount=_safe_float(row.get("amount")),
                    amplitude=amplitude,
                    change_pct=change_pct,
                    turnover=None,
                )
            )
        if not bars:
            raise RuntimeError(f"{symbol} minute bars parse empty")
        return bars

    def fetch_sector_heatmap(self) -> ProviderResult[list[SectorSnapshot]]:
        try:
            frame_result = self.fetch_board_breadth_frame()
            frame = frame_result.data
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        if frame is None or frame.empty:
            return ProviderResult(
                quality=MarketDataQuality.UNAVAILABLE,
                source=self.name,
                message="industry board breadth unavailable",
            )
        median_change = float(frame["change_pct"].median()) if "change_pct" in frame else 0.0
        market_strength = _bounded_strength(median_change)
        heatmap = [
            SectorSnapshot(
                sector_name=str(row.get("industry") or ""),
                sector_strength=_bounded_strength(float(row.get("change_pct") or 0.0)),
                market_strength=market_strength,
                alignment_score=round(
                    (_bounded_strength(float(row.get("change_pct") or 0.0)) + market_strength) / 2,
                    2,
                ),
                notes="板块热力来自 AkShare 行业板块快照。",
            )
            for row in frame.head(30).to_dict("records")
            if str(row.get("industry") or "").strip()
        ]
        return ProviderResult(
            quality=MarketDataQuality.FRESH if heatmap else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=heatmap or None,
        )

    def fetch_board_breadth_frame(self) -> ProviderResult:
        try:
            frame = self._industry_board_frame()
            normalized = normalize_board_frame(frame)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        if normalized is None or normalized.empty:
            return ProviderResult(
                quality=MarketDataQuality.UNAVAILABLE,
                source=self.name,
                message="industry board breadth unavailable",
            )
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=normalized)

    def _industry_board_frame(self):
        if ak is None:
            raise RuntimeError("akshare unavailable")
        if self._industry_board_frame_cache is None:
            self._industry_board_frame_cache = self._raw_call(
                ak.stock_board_industry_name_em,
                purpose="industry",
            )
        return self._industry_board_frame_cache

    def fetch_trade_dates(self) -> ProviderResult[list[str]]:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self._raw_call(ak.tool_trade_date_hist_sina, purpose="trade_dates")
            values = [
                item.isoformat() if hasattr(item, "isoformat") else str(item)
                for item in frame["trade_date"].tolist()
            ]
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if values else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=values or None,
        )

    def fetch_market_emotion_pools(
        self,
        effective_trade_date: str,
        previous_trade_date: str | None = None,
    ) -> ProviderResult[dict[str, object]]:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        compact_date = effective_trade_date.replace("-", "")
        try:
            data = {
                "current": self._raw_call(
                    ak.stock_zt_pool_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "broken": self._raw_call(
                    ak.stock_zt_pool_zbgc_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous_board": self._raw_call(
                    ak.stock_zt_pool_previous_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous": None,
            }
            if previous_trade_date:
                data["previous"] = self._raw_call(
                    ak.stock_zt_pool_em,
                    date=previous_trade_date.replace("-", ""),
                    purpose="limit_pool",
                )
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=data)

    def fetch_limit_up_pool(self, trade_date: str) -> ProviderResult:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self._raw_call(
                ak.stock_zt_pool_em,
                date=trade_date.replace("-", ""),
                purpose="limit_pool",
            )
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if frame is not None else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=frame,
        )

    def fetch_limit_down_pool(self, trade_date: str) -> ProviderResult:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self._raw_call(
                ak.stock_zt_pool_dtgc_em,
                date=trade_date.replace("-", ""),
                purpose="market_breadth",
            )
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if frame is not None else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=frame,
        )

    def fetch_daily_history(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        normalized = None
        try:
            frame = self._raw_call(
                ak.stock_zh_a_daily,
                symbol=self.service._to_sina_symbol(symbol),
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
                purpose="daily_history",
            )
            if frame is not None and not frame.empty:
                normalized = frame.rename(
                    columns={
                        "date": "date",
                        "open": "open",
                        "close": "close",
                        "high": "high",
                        "low": "low",
                        "volume": "volume",
                        "amount": "amount",
                    }
                ).copy()
                normalized["pct_chg"] = normalized["close"].pct_change().fillna(0.0) * 100
        except Exception:
            normalized = None
        if normalized is None:
            try:
                frame = self._raw_call(
                    ak.stock_zh_a_hist_tx,
                    symbol=self.service._to_sina_symbol(symbol),
                    start_date=start_date,
                    end_date=end_date,
                    purpose="daily_history",
                )
                if frame is not None and not frame.empty:
                    normalized = frame.rename(
                        columns={
                            "date": "date",
                            "open": "open",
                            "close": "close",
                            "high": "high",
                            "low": "low",
                            "amount": "volume",
                        }
                    ).copy()
                    normalized["amount"] = 0.0
                    normalized["pct_chg"] = normalized["close"].pct_change().fillna(0.0) * 100
            except Exception as exc:
                return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if normalized is not None and not normalized.empty else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=normalized,
        )

    def fetch_sector_fund_flow_rank(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_sector_fund_flow_rank,
                indicator="今日",
                sector_type="行业资金流",
                purpose="industry",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_individual_fund_flow(self, symbol: str, market: str) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_individual_fund_flow,
                stock=symbol,
                market=market,
                purpose="quote",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_northbound_fund_flow_summary(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_hsgt_fund_flow_summary_em,
                purpose="market_breadth",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_limit_up_snapshot(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(ak.stock_zt_pool_em, purpose="limit_pool")
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_lhb_stock_statistic(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_lhb_stock_statistic_em,
                symbol="近一月",
                purpose="market_breadth",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_stock_notice_report(self, symbol: str) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.stock_notice_report,
                symbol=symbol,
                purpose="news",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_market_events(self, symbol: str) -> ProviderResult[list[MarketEventOut]]:
        if ak is None:
            return self._ak_unavailable()
        try:
            events = self._fetch_notice_events(symbol) + self._fetch_news_events(symbol)
        except Exception as exc:
            return self._unavailable(str(exc))
        deduped: list[MarketEventOut] = []
        seen: set[tuple[str, str]] = set()
        for event in events:
            key = (event.title, event.source)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)
        return ProviderResult(
            quality=MarketDataQuality.FRESH if deduped else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=deduped[:8] or None,
        )

    def fetch_stock_instrument_rows(self) -> ProviderResult[list[dict[str, object]]]:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(ak.stock_info_a_code_name, purpose="industry")
        except Exception as exc:
            return self._unavailable(str(exc))
        rows = frame.to_dict("records") if frame is not None and not getattr(frame, "empty", False) else []
        return ProviderResult(
            quality=MarketDataQuality.FRESH if rows else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=rows or None,
        )

    def fetch_etf_instrument_rows(self) -> ProviderResult[list[dict[str, object]]]:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self._raw_call(
                ak.fund_etf_category_sina,
                symbol="ETF基金",
                purpose="industry",
            )
        except Exception as exc:
            return self._unavailable(str(exc))
        rows = frame.to_dict("records") if frame is not None and not getattr(frame, "empty", False) else []
        return ProviderResult(
            quality=MarketDataQuality.FRESH if rows else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=rows or None,
        )

    def fetch_industry_constituent_map(self) -> ProviderResult[dict[str, str]]:
        if ak is None:
            return self._ak_unavailable()
        result = self._load_em_industry_constituent_map()
        for symbol, industry in self._load_sw_industry_constituent_map().items():
            result.setdefault(symbol, industry)
        return ProviderResult(
            quality=MarketDataQuality.FRESH if result else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=result or None,
        )

    def fetch_stock_industry(self, symbol: str) -> ProviderResult[str]:
        if ak is None:
            return self._ak_unavailable()
        try:
            info_df = self._raw_call(ak.stock_individual_info_em, symbol=symbol, purpose="industry")
            industry_values = info_df.loc[info_df["item"] == "行业", "value"].tolist()
        except Exception as exc:
            return self._unavailable(str(exc))
        industry = str(industry_values[0]).strip() if industry_values else ""
        return ProviderResult(
            quality=MarketDataQuality.FRESH if industry else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=industry or None,
        )

    def _load_em_industry_constituent_map(self) -> dict[str, str]:
        try:
            industry_frame = self._raw_call(ak.stock_board_industry_name_em, purpose="industry")
        except Exception:
            return {}
        industry_names = _extract_industry_names(industry_frame.to_dict("records"))
        result: dict[str, str] = {}
        for industry in industry_names:
            try:
                constituents = self._raw_call(
                    ak.stock_board_industry_cons_em,
                    symbol=industry,
                    purpose="industry",
                )
            except Exception:
                continue
            for record in constituents.to_dict("records"):
                symbol = _extract_first_value(record, ("代码", "股票代码", "code", "symbol"))
                name = _extract_first_value(record, ("名称", "股票名称", "name", "证券简称"))
                if not symbol or _is_st_or_delist_name(name):
                    continue
                result.setdefault(symbol, industry)
        return result

    def _load_sw_industry_constituent_map(self) -> dict[str, str]:
        try:
            history_frame = self._raw_call(ak.stock_industry_clf_hist_sw, purpose="industry")
            category_frame = self._raw_call(
                ak.stock_industry_category_cninfo,
                symbol="申银万国行业分类标准",
                purpose="industry",
            )
        except Exception:
            return {}
        category_map = _build_sw_category_map(category_frame.to_dict("records"))
        latest_by_symbol: dict[str, tuple[str, str, str]] = {}
        for row in history_frame.to_dict("records"):
            symbol = _extract_first_value(row, ("symbol", "股票代码", "代码"))
            industry_code = _extract_first_value(row, ("industry_code", "行业代码", "类目编码"))
            if not symbol or not industry_code:
                continue
            start_date = _extract_first_value(row, ("start_date", "开始日期"))
            update_time = _extract_first_value(row, ("update_time", "更新时间"))
            current = latest_by_symbol.get(symbol)
            marker = (start_date, update_time)
            if current is None or marker >= (current[1], current[2]):
                latest_by_symbol[symbol] = (industry_code, start_date, update_time)
        result: dict[str, str] = {}
        for symbol, (industry_code, _, _) in latest_by_symbol.items():
            industry = _resolve_sw_industry_name(industry_code, category_map)
            if industry:
                result[symbol] = industry
        return result

    def _fetch_notice_events(self, symbol: str) -> list[MarketEventOut]:
        today = beijing_now().strftime("%Y%m%d")
        categories = ("风险提示", "重大事项", "持股变动")
        hits: list[MarketEventOut] = []
        for category in categories:
            try:
                frame = self._raw_call(
                    ak.stock_notice_report,
                    symbol=category,
                    date=today,
                    purpose="notice",
                )
            except Exception:
                continue
            if frame is None or getattr(frame, "empty", True):
                continue
            matched = frame[frame["代码"].astype(str) == symbol] if "代码" in frame else frame.iloc[0:0]
            for _, row in matched.head(3).iterrows():
                risk_level = "high" if category in {"风险提示", "重大事项"} else "medium"
                hits.append(
                    MarketEventOut(
                        title=str(row.get("公告标题", "相关公告")),
                        risk_level=risk_level,
                        description=f"{category}公告，需确认是否影响盘中波动与流动性。",
                        source="notice",
                        event_time=str(row.get("公告日期", "")),
                    )
                )
        return hits

    def _fetch_news_events(self, symbol: str) -> list[MarketEventOut]:
        try:
            frame = self._raw_call(ak.stock_news_em, symbol=symbol, purpose="news")
        except Exception:
            return []
        if frame is None or getattr(frame, "empty", True):
            return []
        risk_keywords = {
            "停牌": "high",
            "问询": "high",
            "立案": "high",
            "风险提示": "high",
            "减持": "medium",
            "诉讼": "high",
            "异常波动": "medium",
            "预亏": "high",
            "预减": "high",
            "回购": "low",
            "增持": "low",
            "中标": "low",
        }
        events: list[MarketEventOut] = []
        for _, row in frame.head(8).iterrows():
            text = f"{row.get('新闻标题', '')} {row.get('新闻内容', '')}"
            matched_level = next((level for keyword, level in risk_keywords.items() if keyword in text), None)
            if matched_level:
                events.append(
                    MarketEventOut(
                        title=str(row.get("新闻标题", "相关新闻")),
                        risk_level=matched_level,
                        description=str(row.get("新闻内容", ""))[:120],
                        source="news",
                        event_time=str(row.get("发布时间", "")),
                    )
                )
        return events

    def _ak_unavailable(self) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")

    def _unavailable(self, message: str) -> ProviderResult:
        return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=message[:160])

    def _frame_result(self, frame) -> ProviderResult:
        usable = frame is not None and not getattr(frame, "empty", False)
        return ProviderResult(
            quality=MarketDataQuality.FRESH if usable else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=frame if usable else None,
        )


def _bounded_strength(change_pct: float) -> float:
    return round(max(0.0, min(100.0, 50.0 + change_pct * 8.0)), 2)


def _extract_industry_names(rows: list[dict[str, object]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        industry = _extract_first_value(row, ("板块名称", "行业", "name", "industry"))
        if industry and industry not in names:
            names.append(industry)
    return names


def _extract_first_value(row: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _safe_str(row.get(key)).strip()
        if value:
            return value
    return ""


def _build_sw_category_map(rows: list[dict[str, object]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        raw_code = _extract_first_value(row, ("类目编码", "code"))
        name = _extract_first_value(row, ("类目名称", "name"))
        if not raw_code or not name:
            continue
        result[raw_code.removeprefix("S")] = name
    return result


def _resolve_sw_industry_name(industry_code: str, category_map: dict[str, str]) -> str:
    code = str(industry_code or "").strip().removeprefix("S")
    if not code:
        return ""
    for candidate in (code[:4], code[:6], code[:2], code):
        name = category_map.get(candidate)
        if name:
            return name
    return ""


def _is_st_or_delist_name(name: str) -> bool:
    text = str(name or "").strip().upper()
    if not text:
        return False
    return text.startswith(_ST_PREFIX_MARKERS) or any(marker in text for marker in _ST_NAME_MARKERS)
