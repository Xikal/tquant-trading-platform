from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import ping_database
from app.core.timezone import beijing_now_string
from app.models.schema_defs.agent import (
    AgentAnalysisRequest,
    AgentAnalysisResponse,
    AgentHealthResponse,
    AgentPriorityBoardItem,
    AgentPriorityBoardResponse,
    AgentWatchlistContextItem,
    AgentWatchlistContextResponse,
)
from app.models.schemas import AnalysisRequest
from app.services.analysis_service import AnalysisService
from app.services.low_buy_screener import LowBuyScreenerService
from app.services.watchlist_signal_service import WatchlistSignalService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_NEXT_INDEX_FILE = PROJECT_ROOT / "frontend-next" / "dist" / "index.html"


class AgentContextService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.watchlist_signals = WatchlistSignalService()
        self.low_buy_screener = LowBuyScreenerService()
        self.analysis_service = AnalysisService()

    def health(self, db: Session) -> AgentHealthResponse:  # noqa: ARG002
        checks = {
            "database": False,
            "frontend_dist": FRONTEND_NEXT_INDEX_FILE.exists(),
            "frontend_next_dist": FRONTEND_NEXT_INDEX_FILE.exists(),
            "watchlist_signals": False,
            "priority_board": False,
        }
        errors: list[str] = []
        try:
            ping_database()
            checks["database"] = True
        except Exception as exc:
            errors.append(f"database: {exc}")
        checks["watchlist_signals"] = checks["database"]
        checks["priority_board"] = checks["database"]
        status = "ok" if all(checks.values()) else "degraded"
        return AgentHealthResponse(
            status=status,  # type: ignore[arg-type]
            app=self.settings.app_name,
            checks=checks,
            updated_at=_now_string(),
            errors=errors,
        )

    def watchlist_context(self, db: Session) -> AgentWatchlistContextResponse:
        payloads = self.watchlist_signals.list_signals(db)
        items = [self._watchlist_item(payload) for payload in payloads]
        return AgentWatchlistContextResponse(
            updated_at=_now_string(),
            total=len(items),
            actionable_count=sum(item.action in {"positive_t", "negative_t"} for item in items),
            high_risk_count=sum(item.risk_level == "high" for item in items),
            items=items,
        )

    def priority_board(self, db: Session, limit: int = 12) -> AgentPriorityBoardResponse:
        safe_limit = max(1, min(int(limit), 50))
        board = self.low_buy_screener.priority_board(db=db, limit=safe_limit)
        items = [
            AgentPriorityBoardItem(
                rank=index + 1,
                symbol=item.symbol,
                name=item.name,
                sector_name=item.sector_name or "",
                latest_price=item.latest_price,
                change_pct=item.change_pct,
                data_quality=item.data_quality,
                data_quality_text=item.data_quality_text,
                data_quality_tags=item.data_quality_tags,
                market_state_category=item.market_state_category,
                market_state_category_text=item.market_state_category_text,
                priority_score=round(item.priority_score, 2),
                buy_signal_text=item.buy_signal_text,
                strategy_titles=item.strategy_titles[:4] if item.strategy_titles else [item.strategy_title],
                entry_zone=f"{item.entry_zone_low:.3f}-{item.entry_zone_high:.3f}",
                stop_loss=item.stop_loss,
                suggested_position_text=item.suggested_position_text,
                summary=_first_text(item.next_action_text, item.action_summary, item.trigger_condition),
            )
            for index, item in enumerate(board.items[:safe_limit])
        ]
        return AgentPriorityBoardResponse(
            updated_at=board.updated_at or _now_string(),
            market_state_text=board.market_state_text,
            market_state_category=board.market_state_category,
            market_state_category_text=board.market_state_category_text,
            data_quality=board.data_quality,
            data_quality_text=board.data_quality_text,
            data_quality_tags=board.data_quality_tags,
            directional_bias=board.directional_bias,
            directional_bias_text=board.directional_bias_text,
            total_candidates=board.total_candidates,
            immediate_count=board.immediate_count,
            focus_count=board.focus_count,
            track_count=board.track_count,
            hot_industries=board.hot_industries[:6],
            items=items,
        )

    def analysis(self, db: Session, payload: AgentAnalysisRequest) -> AgentAnalysisResponse:
        result = self.analysis_service.analyze(
            db,
            AnalysisRequest(
                symbol=payload.symbol,
                base_position=payload.base_position,
                available_position=payload.available_position,
                cost_basis=payload.cost_basis,
                include_ai=payload.include_ai,
                include_events=True,
                include_microstructure=True,
            ),
            persist=False,
        )
        suggestion = result.suggestion
        return AgentAnalysisResponse(
            symbol=result.symbol,
            name=result.instrument.name,
            last_price=result.quote.last_price,
            change_pct=result.quote.change_pct,
            action=suggestion.action,
            action_text=_action_text(suggestion.action, suggestion.plain_action_text),
            signal_score=suggestion.signal_score,
            tradability_score=suggestion.tradability_score,
            risk_level=suggestion.risk_level,
            entry_price=suggestion.entry_price,
            exit_price=suggestion.exit_price,
            stop_loss=suggestion.stop_loss,
            take_profit=suggestion.take_profit,
            position_pct=suggestion.position_pct,
            expected_profit_pct=suggestion.expected_profit_pct,
            reasons=_trim_lines(suggestion.reasons, 4),
            blocking_rules=_trim_lines(suggestion.blocking_rules, 4),
            summary=_first_text(suggestion.plain_execution_text, suggestion.plain_action_reason, suggestion.strategy_notes),
        )

    @staticmethod
    def _watchlist_item(payload: dict[str, Any]) -> AgentWatchlistContextItem:
        quote = payload.get("quote") or {}
        signal = payload.get("signal") or {}
        reasons = _trim_lines(signal.get("reasons") or [], 3)
        blockers = _trim_lines(signal.get("blocking_rules") or [], 3)
        action = str(signal.get("action") or "hold")
        return AgentWatchlistContextItem(
            symbol=str(payload.get("symbol") or quote.get("symbol") or ""),
            name=str(payload.get("name") or quote.get("name") or payload.get("symbol") or ""),
            last_price=_float(quote.get("last_price")),
            change_pct=_float(quote.get("change_pct")),
            action=action,
            action_text=_action_text(action, signal.get("plain_action_text")),
            signal_score=_float(signal.get("signal_score")),
            tradability_score=_float(signal.get("tradability_score")),
            risk_level=str(signal.get("risk_level") or "medium"),
            base_position=int(payload.get("base_position") or 0),
            available_position=int(payload.get("available_position") or 0),
            cost_basis=_optional_float(payload.get("cost_basis")),
            summary=_first_text(signal.get("plain_action_reason"), signal.get("strategy_notes"), *(reasons[:1])),
            top_reasons=reasons,
            blocking_rules=blockers,
        )


def _now_string() -> str:
    return beijing_now_string()


def _action_text(action: str, plain: Any = "") -> str:
    cleaned = str(plain or "").strip()
    if cleaned:
        return cleaned
    if action == "positive_t":
        return "正T"
    if action == "negative_t":
        return "反T"
    return "观望"


def _trim_lines(values: Any, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip()[:120] for item in values if str(item).strip()][:limit]


def _first_text(*values: Any) -> str:
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned:
            return cleaned[:180]
    return ""


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
