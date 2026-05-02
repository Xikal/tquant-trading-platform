from __future__ import annotations

from dataclasses import dataclass
import json
import time

import pandas as pd

from app.repositories.low_buy import LowBuyHotIndustryRepository
from app.services.low_buy.mainline_strength import (
    MainlineIndustryScore,
    normalize_live_industry_frame,
    rank_mainline_industries,
)
from app.services.low_buy.shared import Any, BoardCandidate, Session, ak


@dataclass
class _HotIndustrySnapshotView:
    latest_trade_date: str
    source: str
    industries: list[str]
    trade_gap: int = 0


class LowBuyHotIndustryContextMixin:
    _live_industry_frame_cache: tuple[float, pd.DataFrame | None] | None = None
    _live_industry_frame_ttl_seconds = 180.0

    HOT_INDUSTRY_SOURCE_TEXT = {
        "mainline_strength": "热点依据：主线强度评分（持续性、强势样本、实时强度综合）",
        "board_strength": "热点依据：实时行业强度",
        "pool_inference": "热点依据：由近期强势样本推断",
        "historical_cache": "热点依据：沿用最近一次有效热点",
        "historical_cache_stale": "热点依据：沿用较早热点，仅供参考",
        "unavailable": "热点依据：当前暂无稳定热点",
    }

    def _load_live_industry_frame(self) -> pd.DataFrame | None:
        cached = self._live_industry_frame_cache
        now = time.monotonic()
        if cached is not None and cached[0] > now:
            frame = cached[1]
            return frame.copy() if frame is not None else None
        if ak is None:
            return None
        try:
            frame = self.market_data._call_akshare(ak.stock_board_industry_name_em, purpose="industry")
        except Exception:
            self._live_industry_frame_cache = (now + 30.0, None)
            return None
        normalized = normalize_live_industry_frame(frame)
        self._live_industry_frame_cache = (now + self._live_industry_frame_ttl_seconds, normalized)
        return normalized.copy()

    def _load_hot_industries(self, latest_trade_date: str) -> list[str]:
        live_frame = self._load_live_industry_frame()
        if live_frame is None or live_frame.empty:
            return []
        top_rows = live_frame.head(3)
        return [str(item).strip() for item in top_rows["industry"].tolist() if str(item).strip()]

    def _resolve_hot_industries(
        self,
        *,
        db: Session,
        latest_trade_date: str,
        pooled_candidates: dict[str, BoardCandidate],
    ) -> tuple[list[str], str, str]:
        mainline_scores = self._rank_mainline_industries(
            db=db,
            latest_trade_date=latest_trade_date,
            pooled_candidates=pooled_candidates,
        )
        stable_industries = self._industries_from_mainline_scores(mainline_scores, limit=3)
        if stable_industries:
            self._save_hot_industry_snapshot(
                db=db,
                latest_trade_date=latest_trade_date,
                source="mainline_strength",
                industries=stable_industries,
            )
            return stable_industries, "mainline_strength", self.HOT_INDUSTRY_SOURCE_TEXT["mainline_strength"]

        cached = self._load_latest_hot_industry_snapshot(db=db, latest_trade_date=latest_trade_date)
        if cached and cached.industries:
            if cached.trade_gap <= 2:
                if cached.latest_trade_date == latest_trade_date:
                    source_text = self.HOT_INDUSTRY_SOURCE_TEXT.get(cached.source, self.HOT_INDUSTRY_SOURCE_TEXT["historical_cache"])
                else:
                    source_text = f"{self.HOT_INDUSTRY_SOURCE_TEXT['historical_cache']}（最近有效 {cached.latest_trade_date}）"
                return cached.industries, "historical_cache", source_text
            if cached.trade_gap <= 5:
                source_text = f"{self.HOT_INDUSTRY_SOURCE_TEXT['historical_cache_stale']}（最近有效 {cached.latest_trade_date}）"
                return cached.industries, "historical_cache_stale", source_text

        inferred = self._infer_hot_industries_from_pool(
            pooled_candidates=pooled_candidates,
            latest_trade_date=latest_trade_date,
        )
        if inferred:
            self._save_hot_industry_snapshot(
                db=db,
                latest_trade_date=latest_trade_date,
                source="pool_inference",
                industries=inferred,
            )
            return inferred, "pool_inference", self.HOT_INDUSTRY_SOURCE_TEXT["pool_inference"]

        return [], "unavailable", self.HOT_INDUSTRY_SOURCE_TEXT["unavailable"]

    def _resolve_hot_industries_cached(
        self,
        *,
        db: Session,
        latest_trade_date: str,
        pooled_candidates: dict[str, BoardCandidate],
    ) -> tuple[list[str], str, str]:
        cached = self._load_latest_hot_industry_snapshot(db=db, latest_trade_date=latest_trade_date)
        if cached and cached.industries:
            if cached.trade_gap <= 2:
                if cached.latest_trade_date == latest_trade_date:
                    source_key = cached.source or "historical_cache"
                    return (
                        cached.industries,
                        source_key,
                        self.HOT_INDUSTRY_SOURCE_TEXT.get(source_key, self.HOT_INDUSTRY_SOURCE_TEXT["historical_cache"]),
                    )
                return (
                    cached.industries,
                    "historical_cache",
                    f"{self.HOT_INDUSTRY_SOURCE_TEXT['historical_cache']}（最近有效 {cached.latest_trade_date}）",
                )
            if cached.trade_gap <= 5:
                stale_text = self.HOT_INDUSTRY_SOURCE_TEXT["historical_cache_stale"]
                return (
                    cached.industries,
                    "historical_cache_stale",
                    f"{stale_text}（最近有效 {cached.latest_trade_date}）",
                )

        inferred = self._infer_hot_industries_from_pool(
            pooled_candidates=pooled_candidates,
            latest_trade_date=latest_trade_date,
        )
        if inferred:
            return inferred, "pool_inference", self.HOT_INDUSTRY_SOURCE_TEXT["pool_inference"]
        return [], "unavailable", self.HOT_INDUSTRY_SOURCE_TEXT["unavailable"]

    def _rank_mainline_industries(
        self,
        *,
        db: Session,
        latest_trade_date: str,
        pooled_candidates: dict[str, BoardCandidate],
    ) -> list[MainlineIndustryScore]:
        return rank_mainline_industries(
            live_frame=self._load_live_industry_frame(),
            pooled_candidates=pooled_candidates,
            latest_trade_date=latest_trade_date,
            recent_sequences=self._load_recent_hot_industry_sequences(
                db=db,
                latest_trade_date=latest_trade_date,
                limit=5,
            ),
        )

    @staticmethod
    def _industries_from_mainline_scores(
        scores: list[MainlineIndustryScore],
        *,
        limit: int,
    ) -> list[str]:
        preferred_tiers = {"core_mainline", "secondary_mainline", "rotation_hot"}
        industries = [item.industry for item in scores if item.tier in preferred_tiers]
        return industries[: max(limit, 1)]

    def _infer_hot_industries_from_pool(
        self,
        *,
        pooled_candidates: dict[str, BoardCandidate],
        latest_trade_date: str,
    ) -> list[str]:
        recent_dates = sorted(
            {item.board_date for item in pooled_candidates.values() if item.board_date <= latest_trade_date},
            reverse=True,
        )[:3]
        if not recent_dates:
            return []
        weights = {trade_date: max(1, 3 - index) for index, trade_date in enumerate(recent_dates)}
        scores: dict[str, float] = {}
        for item in pooled_candidates.values():
            industry = item.industry.strip()
            weight = weights.get(item.board_date)
            if not industry or weight is None:
                continue
            amount_score = max(item.amount, 1.0) / 100000000
            board_score = 1.0 if item.board_count == 1 else 0.45
            scores[industry] = scores.get(industry, 0.0) + weight * (amount_score + board_score)
        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
        return [name for name, _ in ranked[:3]]

    def _load_limit_down_count(self, latest_trade_date: str) -> int | None:
        if ak is None:
            return None
        try:
            frame = self.market_data._call_akshare(
                ak.stock_zt_pool_dtgc_em,
                date=latest_trade_date.replace("-", ""),
                purpose="limit_pool",
            )
        except Exception:
            return None
        return int(len(frame.index)) if frame is not None else None

    def _build_strategy_notes(
        self,
        base_notes: list[str],
        hot_industries: list[str],
        limit_down_count: int | None,
        hot_industry_source_text: str = "",
    ) -> list[str]:
        notes = list(base_notes)
        if hot_industries:
            notes.append(f"当前热点行业优先：{' / '.join(hot_industries)}。")
        if hot_industry_source_text:
            notes.append(hot_industry_source_text)
        if limit_down_count is not None:
            notes.append(
                "市场情绪正常，可执行低吸筛选。"
                if limit_down_count <= 20
                else f"当前跌停家数 {limit_down_count} 家，市场情绪偏弱，所有结果都应降一档看。"
            )
        return notes

    @staticmethod
    def _safe_json_object(raw: str) -> dict[str, Any]:
        try:
            value = json.loads(raw or "{}")
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _safe_json_list(raw: str) -> list[str]:
        try:
            value = json.loads(raw or "[]")
        except Exception:
            return []
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _load_latest_hot_industry_snapshot(
        self,
        *,
        db: Session,
        latest_trade_date: str,
    ) -> _HotIndustrySnapshotView | None:
        row = LowBuyHotIndustryRepository(db).fetch_latest_valid(latest_trade_date)
        if row is None:
            return None
        industries = self._safe_json_list(row.industries_json)
        if not industries:
            return None
        return _HotIndustrySnapshotView(
            latest_trade_date=row.latest_trade_date,
            source=row.source,
            industries=industries,
            trade_gap=self._trade_date_gap(row.latest_trade_date, latest_trade_date),
        )

    def _load_recent_hot_industry_sequences(
        self,
        *,
        db: Session,
        latest_trade_date: str,
        limit: int = 3,
    ) -> list[list[str]]:
        rows = LowBuyHotIndustryRepository(db).fetch_recent_valids(
            latest_trade_date=latest_trade_date,
            limit=limit,
        )
        sequences: list[list[str]] = []
        for row in rows:
            industries = self._safe_json_list(row.industries_json)
            if industries:
                sequences.append(industries)
        return sequences

    def _save_hot_industry_snapshot(
        self,
        *,
        db: Session,
        latest_trade_date: str,
        source: str,
        industries: list[str],
    ) -> None:
        LowBuyHotIndustryRepository(db).save(
            latest_trade_date=latest_trade_date,
            source=source,
            industries_json=json.dumps(industries, ensure_ascii=False),
        )
        db.commit()

    def _trade_date_gap(self, previous_trade_date: str, latest_trade_date: str) -> int:
        if not previous_trade_date or not latest_trade_date or previous_trade_date >= latest_trade_date:
            return 0
        try:
            trade_dates = self._get_recent_trade_dates(20)
        except Exception:
            return 99
        index_map = {trade_date: index for index, trade_date in enumerate(trade_dates)}
        previous_index = index_map.get(previous_trade_date)
        latest_index = index_map.get(latest_trade_date)
        if previous_index is None or latest_index is None or latest_index < previous_index:
            return 99
        return latest_index - previous_index
