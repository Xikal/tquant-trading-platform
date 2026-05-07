from __future__ import annotations

from app.core.timezone import beijing_now
from app.models.schemas import KlineBar, MarketEventOut, QuoteSnapshot, SectorSnapshot
from app.services.market.providers.quality import MarketDataQuality, ProviderResult
from app.services.market.regime_scoring import normalize_board_frame
from app.services.market.shared import ak


class AkshareMarketProvider:
    name = "akshare"

    def __init__(self, service) -> None:
        self.service = service
        self._industry_board_frame_cache = None

    def fetch_quote(self, symbol: str) -> ProviderResult[QuoteSnapshot]:
        try:
            quote = self.service._fetch_quote_from_spot_snapshot(symbol)
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(quality=MarketDataQuality.FRESH, source=self.name, data=quote)

    def fetch_intraday_bars(self, symbol: str) -> ProviderResult[list[KlineBar]]:
        try:
            bars = self.service._fetch_sina_minute_bars(symbol, "1m")
        except Exception as exc:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message=str(exc)[:160])
        return ProviderResult(
            quality=MarketDataQuality.FRESH if bars else MarketDataQuality.UNAVAILABLE,
            source=self.name,
            data=bars or None,
        )

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
            self._industry_board_frame_cache = self.service._call_akshare(
                ak.stock_board_industry_name_em,
                purpose="industry",
            )
        return self._industry_board_frame_cache

    def fetch_trade_dates(self) -> ProviderResult[list[str]]:
        if ak is None:
            return ProviderResult(quality=MarketDataQuality.UNAVAILABLE, source=self.name, message="akshare unavailable")
        try:
            frame = self.service._call_akshare(ak.tool_trade_date_hist_sina, purpose="trade_dates")
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
                "current": self.service._call_akshare(
                    ak.stock_zt_pool_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "broken": self.service._call_akshare(
                    ak.stock_zt_pool_zbgc_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous_board": self.service._call_akshare(
                    ak.stock_zt_pool_previous_em,
                    date=compact_date,
                    purpose="limit_pool",
                ),
                "previous": None,
            }
            if previous_trade_date:
                data["previous"] = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
                frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(ak.stock_zt_pool_em, purpose="limit_pool")
        except Exception as exc:
            return self._unavailable(str(exc))
        return self._frame_result(frame)

    def fetch_lhb_stock_statistic(self) -> ProviderResult:
        if ak is None:
            return self._ak_unavailable()
        try:
            frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(
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

    def _fetch_notice_events(self, symbol: str) -> list[MarketEventOut]:
        today = beijing_now().strftime("%Y%m%d")
        categories = ("风险提示", "重大事项", "持股变动")
        hits: list[MarketEventOut] = []
        for category in categories:
            try:
                frame = self.service._call_akshare(
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
            frame = self.service._call_akshare(ak.stock_news_em, symbol=symbol, purpose="news")
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
