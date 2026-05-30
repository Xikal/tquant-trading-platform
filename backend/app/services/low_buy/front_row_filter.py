from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.low_buy.priority_types import PriorityCandidate


FRONT_ROW_LEADER_RANKS = {"leader", "strong_follow"}
FRONT_ROW_MAINLINE_TIERS = {"core_mainline", "secondary_mainline"}
FRONT_ROW_INDUSTRY_TIERS = {"core_hot", "secondary_hot"}
FRONT_ROW_BLOCKED_MARKET_STATES = {"high_flyer_retreat", "risk_release", "fast_rotation"}
FRONT_ROW_KEEP_REASONS = {"disabled", "strong_front_row", "mainline_front_row", "hot_front_row"}


@dataclass(frozen=True)
class FrontRowFilterConfig:
    enabled: bool = False
    max_leader_strength_rank: int = 3
    min_leader_strength_score: float = 58.0
    allow_secondary_hot: bool = True
    block_retreat_states: bool = True


@dataclass
class FrontRowFilterStats:
    scanned_count: int = 0
    kept_count: int = 0
    rejected_count: int = 0
    reason_counts: dict[str, int] = field(default_factory=dict)

    @property
    def retention_rate_pct(self) -> float:
        if self.scanned_count <= 0:
            return 0.0
        return round(self.kept_count / self.scanned_count * 100.0, 2)

    def record(self, reason: str) -> None:
        key = reason or "unknown"
        self.reason_counts[key] = self.reason_counts.get(key, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned_count": self.scanned_count,
            "kept_count": self.kept_count,
            "rejected_count": self.rejected_count,
            "retention_rate_pct": self.retention_rate_pct,
            "reason_counts": dict(sorted(self.reason_counts.items(), key=lambda item: (-item[1], item[0]))),
        }


def default_front_row_filter_config(*, enabled: bool = False) -> FrontRowFilterConfig:
    return FrontRowFilterConfig(enabled=enabled)


def candidate_front_row_decision(candidate: Any, config: FrontRowFilterConfig | None = None) -> tuple[bool, str]:
    cfg = config or FrontRowFilterConfig(enabled=False)
    if not cfg.enabled:
        return True, "disabled"
    if _is_blocked_by_market(candidate, cfg):
        return False, "blocked_market_state"
    if _is_blocked_by_risk(candidate):
        return False, "risk_blocked"
    if _is_strong_front_row(candidate, cfg):
        return True, "strong_front_row"
    if _is_mainline_front_row(candidate, cfg):
        return True, "mainline_front_row"
    if _is_hot_front_row(candidate, cfg):
        return True, "hot_front_row"
    return False, "rear_rank"


def is_front_row_candidate(candidate: Any, config: FrontRowFilterConfig | None = None) -> bool:
    kept, _reason = candidate_front_row_decision(candidate, config)
    return kept


def filter_front_row_candidates(
    candidates: list[Any],
    config: FrontRowFilterConfig | None = None,
) -> tuple[list[Any], FrontRowFilterStats]:
    cfg = config or FrontRowFilterConfig(enabled=False)
    stats = FrontRowFilterStats(scanned_count=len(candidates))
    if not cfg.enabled:
        stats.kept_count = len(candidates)
        stats.record("disabled")
        return list(candidates), stats
    kept: list[Any] = []
    for candidate in candidates:
        allowed, reason = candidate_front_row_decision(candidate, cfg)
        stats.record(reason)
        if allowed:
            kept.append(candidate)
        else:
            stats.rejected_count += 1
    stats.kept_count = len(kept)
    return kept, stats


def filter_priority_front_row_candidates(
    rows: list[PriorityCandidate],
    config: FrontRowFilterConfig | None = None,
) -> tuple[list[PriorityCandidate], FrontRowFilterStats]:
    cfg = config or FrontRowFilterConfig(enabled=False)
    stats = FrontRowFilterStats(scanned_count=len(rows))
    if not cfg.enabled:
        stats.kept_count = len(rows)
        stats.record("disabled")
        return list(rows), stats
    kept_rows: list[PriorityCandidate] = []
    for row in rows:
        best_reason = "rear_rank"
        kept_hits = []
        for hit in row.hits:
            allowed, reason = candidate_front_row_decision(hit.candidate, cfg)
            if allowed:
                kept_hits.append(hit)
                best_reason = reason
            elif best_reason == "rear_rank":
                best_reason = reason
        stats.record(best_reason)
        if kept_hits:
            kept_rows.append(PriorityCandidate(symbol=row.symbol, hits=kept_hits))
        else:
            stats.rejected_count += 1
    stats.kept_count = len(kept_rows)
    return kept_rows, stats


def front_row_filter_warning(stats: FrontRowFilterStats) -> str:
    if stats.scanned_count <= 0:
        return "前排过滤未发现候选，存在长期无推荐风险。"
    if stats.kept_count <= 0:
        return "前排过滤已剔除全部候选，存在长期无推荐风险。"
    if stats.retention_rate_pct < 15.0:
        return f"前排过滤样本留存率仅 {stats.retention_rate_pct:.2f}%，需要重点观察是否长期无推荐。"
    return ""


def _is_blocked_by_market(candidate: Any, config: FrontRowFilterConfig) -> bool:
    if not config.block_retreat_states:
        return False
    return str(getattr(candidate, "market_state", "") or "") in FRONT_ROW_BLOCKED_MARKET_STATES


def _is_blocked_by_risk(candidate: Any) -> bool:
    if str(getattr(candidate, "risk_tier", "") or "") == "block":
        return True
    if bool(getattr(candidate, "false_breakout_flag", False)):
        return True
    if bool(getattr(candidate, "intraday_reversal_flag", False)):
        return True
    return float(getattr(candidate, "distribution_risk_score", 0.0) or 0.0) >= 6.8


def _is_strong_front_row(candidate: Any, config: FrontRowFilterConfig) -> bool:
    rank = int(getattr(candidate, "leader_strength_rank", 0) or 0)
    score = float(getattr(candidate, "leader_strength_score", 0.0) or 0.0)
    if rank <= 0:
        return False
    return rank <= config.max_leader_strength_rank and score >= config.min_leader_strength_score


def _is_mainline_front_row(candidate: Any, config: FrontRowFilterConfig) -> bool:
    leader_rank = str(getattr(candidate, "leader_rank", "") or "")
    mainline_tier = str(getattr(candidate, "mainline_tier", "") or "")
    if leader_rank not in FRONT_ROW_LEADER_RANKS:
        return False
    if mainline_tier == "core_mainline":
        return True
    return config.allow_secondary_hot and mainline_tier in FRONT_ROW_MAINLINE_TIERS


def _is_hot_front_row(candidate: Any, config: FrontRowFilterConfig) -> bool:
    leader_rank = str(getattr(candidate, "leader_rank", "") or "")
    industry_tier = str(getattr(candidate, "industry_tier", "") or "")
    if leader_rank not in FRONT_ROW_LEADER_RANKS:
        return False
    if industry_tier == "core_hot":
        return True
    return config.allow_secondary_hot and industry_tier in FRONT_ROW_INDUSTRY_TIERS
