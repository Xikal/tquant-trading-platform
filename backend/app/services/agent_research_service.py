from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from app.core.timezone import beijing_now_string
from app.models.schema_defs.agent import AgentAnalysisRequest
from app.services.agent_research_utils import (
    OPERATION_CHECKLIST,
    clean_symbols as _clean_symbols,
    decision_summary as _decision_summary,
    first_attr as _first_attr,
    get_value as _get,
    mainline_score as _mainline_score,
    market_risk_level as _market_risk_level,
    market_risk_notes as _market_risk_notes,
    match_hot_industry as _match_hot_industry,
    metadata as _metadata,
    normalize_proposal as _normalize_proposal,
    position_range as _position_range,
    ratio as _ratio,
    risk_check_notes as _risk_check_notes,
    rotation_risks as _rotation_risks,
    sector_evidence as _sector_evidence,
    stock_brief as _stock_brief,
    to_float as _float,
    to_int as _int,
    to_pct as _to_pct,
    validation_item as _validation_item,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.services.agent_context_service import AgentContextService
    from app.services.market.service import MarketDataService
else:
    Session = Any
    AgentContextService = Any
    MarketDataService = Any


class AgentResearchService:
    """Read-only research context aggregator for Hermes multi-agent workflows."""

    def __init__(
        self,
        db: Session | None = None,
        *,
        context_service: AgentContextService | None = None,
        market_data: MarketDataService | None = None,
    ) -> None:
        self.db = db
        if context_service is None:
            from app.services.agent_context_service import AgentContextService as RealAgentContextService

            context_service = RealAgentContextService()
        if market_data is None:
            from app.services.market.service import MarketDataService as RealMarketDataService

            market_data = RealMarketDataService()
        self.context = context_service
        self.market_data = market_data

    def market_state_analysis(self, db: Session | None = None) -> dict[str, Any]:
        resolved_db = self._db(db)
        errors: list[str] = []
        board = self._safe_call("priority_board", lambda: self.context.priority_board(resolved_db, limit=12), errors)
        regime = self._safe_call("market_regime", self.market_data.get_market_regime_fast, errors)
        if regime is None:
            return self._degraded("market_state_analysis", errors)

        state = _first_attr(regime, "state", "degraded")
        label = _first_attr(regime, "label", "行情上下文降级")
        confidence = _to_pct(_first_attr(regime, "regime_confidence", 0.0))
        strength = _to_pct(_first_attr(regime, "state_strength", 0.0))
        position_range = _position_range(state, _float(_first_attr(regime, "position_multiplier", 0.75)))
        risk_level = _market_risk_level(state, _float(_first_attr(regime, "broken_board_ratio", 0.0)), _int(_first_attr(regime, "limit_down_count", 0)))

        return {
            "ok": not errors,
            "context": "market_state_analysis",
            "updated_at": beijing_now_string(),
            "market_state": {
                "state": state,
                "label": label,
                "description": _first_attr(regime, "description", _get(board, "market_state_text", "")),
                "confidence_pct": confidence,
                "strength_pct": strength,
                "directional_bias": _get(board, "directional_bias", "neutral"),
                "directional_bias_text": _get(board, "directional_bias_text", "观望"),
            },
            "emotion": {
                "limit_up_count": _int(_first_attr(regime, "limit_up_count", 0)),
                "limit_down_count": _int(_first_attr(regime, "limit_down_count", 0)),
                "broken_board_ratio": _ratio(_first_attr(regime, "broken_board_ratio", 0.0)),
                "broken_board_pct": _to_pct(_first_attr(regime, "broken_board_ratio", 0.0)),
                "promotion_ratio": _ratio(_first_attr(regime, "promotion_ratio", 0.0)),
                "board_height": _int(_first_attr(regime, "board_height", 0)),
                "previous_board_height": _int(_first_attr(regime, "previous_board_height", 0)),
            },
            "breadth": {
                "stock_up_ratio": _ratio(_first_attr(regime, "stock_up_ratio", 0.0)),
                "stock_up_pct": _to_pct(_first_attr(regime, "stock_up_ratio", 0.0)),
                "stock_median_change": _float(_first_attr(regime, "stock_median_change", 0.0)),
                "breadth_ready": bool(_first_attr(regime, "breadth_ready", False)),
                "emotion_ready": bool(_first_attr(regime, "emotion_ready", False)),
            },
            "risk": {
                "risk_level": risk_level,
                "recommended_position_range": position_range,
                "transition_risk_pct": _to_pct(_first_attr(regime, "transition_risk", 0.0)),
                "notes": _market_risk_notes(state, risk_level, position_range, errors),
            },
            "hot_industries": list(_first_attr(regime, "hot_industries", _get(board, "hot_industries", [])) or [])[:6],
            "errors": errors,
            "metadata": _metadata("market_state_analysis"),
        }

    def sector_mainline_analysis(self, db: Session | None = None) -> dict[str, Any]:
        resolved_db = self._db(db)
        errors: list[str] = []
        board = self._safe_call("priority_board", lambda: self.context.priority_board(resolved_db, limit=30), errors)
        if board is None:
            return self._degraded("sector_mainline_analysis", errors)

        hot_industries = list(_get(board, "hot_industries", []) or [])
        grouped: dict[str, list[Any]] = defaultdict(list)
        for item in list(_get(board, "items", []) or []):
            sector = _get(item, "sector_name", "") or _match_hot_industry(item, hot_industries)
            grouped[sector or "未归因"].append(item)

        mainlines = []
        ordered_sectors = hot_industries + [sector for sector in grouped if sector not in hot_industries]
        for rank, sector in enumerate(ordered_sectors[:5], start=1):
            items = grouped.get(sector, [])
            score = _mainline_score(rank, items, sector in hot_industries)
            mainlines.append(
                {
                    "rank": rank,
                    "sector": sector,
                    "continuity_score": score,
                    "limit_up_count": 0,
                    "net_inflow_yi": 0.0,
                    "core_symbols": [_stock_brief(item) for item in items[:5]],
                    "evidence": _sector_evidence(sector, items, sector in hot_industries),
                }
            )

        return {
            "ok": True,
            "context": "sector_mainline_analysis",
            "updated_at": beijing_now_string(),
            "market_state": {
                "category": _get(board, "market_state_category", ""),
                "text": _get(board, "market_state_category_text", _get(board, "market_state_text", "")),
            },
            "mainlines": mainlines,
            "rotation_risks": _rotation_risks(board, mainlines),
            "data_quality": {
                "state": _get(board, "data_quality", "ok"),
                "text": _get(board, "data_quality_text", "数据完整"),
                "tags": list(_get(board, "data_quality_tags", []) or []),
            },
            "errors": errors,
            "metadata": _metadata("sector_mainline_analysis"),
        }

    def cross_validate(self, db_or_symbols: Session | list[str] | None = None, symbols: list[str] | None = None) -> dict[str, Any]:
        resolved_db, resolved_symbols = self._resolve_db_and_symbols(db_or_symbols, symbols)
        errors: list[str] = []
        board = self._safe_call("priority_board", lambda: self.context.priority_board(resolved_db, limit=50), errors)
        board_items = {_get(item, "symbol", ""): item for item in list(_get(board, "items", []) or [])}
        hot_industries = set(_get(board, "hot_industries", []) or [])

        items: list[dict[str, Any]] = []
        for symbol in _clean_symbols(resolved_symbols):
            analysis = self._safe_call(
                f"analysis:{symbol}",
                lambda symbol=symbol: self.context.analysis(
                    resolved_db,
                    AgentAnalysisRequest(symbol=symbol, include_ai=False),
                ),
                errors,
            )
            board_item = board_items.get(symbol)
            item = _validation_item(symbol, analysis, board_item, hot_industries)
            items.append(item)

        return {
            "ok": not errors,
            "context": "strategy_cross_validation",
            "updated_at": beijing_now_string(),
            "summary": {
                "evaluated_count": len(items),
                "high_confidence_count": sum(item["consensus"] == "high" for item in items),
                "conflict_count": sum(item["consensus"] == "conflict" for item in items),
                "watch_count": sum(item["consensus"] == "watch" for item in items),
            },
            "items": items,
            "high_confidence": [item for item in items if item["consensus"] == "high"],
            "conflicts": [item for item in items if item["consensus"] == "conflict"],
            "errors": errors,
            "metadata": _metadata("strategy_cross_validation"),
        }

    def risk_check(self, db_or_proposals: Session | list[dict[str, Any]] | None = None, proposals: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        _resolved_db, resolved_proposals = self._resolve_db_and_proposals(db_or_proposals, proposals)
        normalized = [_normalize_proposal(item) for item in resolved_proposals if isinstance(item, dict)]
        total_pct = round(sum(item["position_pct"] for item in normalized), 2)
        max_single = max((item["position_pct"] for item in normalized), default=0.0)
        sector_totals: dict[str, float] = defaultdict(float)
        for item in normalized:
            sector_totals[item["sector"]] += item["position_pct"]

        violations: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for item in normalized:
            if item["position_pct"] > 20:
                violations.append({"type": "single_position", "symbol": item["symbol"], "value_pct": item["position_pct"], "limit_pct": 20})
            elif item["position_pct"] > 15:
                warnings.append({"type": "single_position", "symbol": item["symbol"], "value_pct": item["position_pct"], "limit_pct": 20})
        for sector, pct in sector_totals.items():
            if pct > 25:
                violations.append({"type": "sector_concentration", "sector": sector, "value_pct": round(pct, 2), "limit_pct": 25})
            elif pct > 20:
                warnings.append({"type": "sector_concentration", "sector": sector, "value_pct": round(pct, 2), "limit_pct": 25})
        if total_pct > 65:
            violations.append({"type": "total_position", "value_pct": total_pct, "limit_pct": 65})
        elif total_pct > 50:
            warnings.append({"type": "total_position", "value_pct": total_pct, "limit_pct": 65})

        risk_level = "block" if violations else "degrade" if warnings else "clear"
        return {
            "ok": True,
            "context": "risk_check",
            "updated_at": beijing_now_string(),
            "risk_level": risk_level,
            "summary": {
                "proposal_count": len(normalized),
                "total_position_pct": total_pct,
                "max_single_position_pct": round(max_single, 2),
                "top_sector": max(sector_totals, key=sector_totals.get) if sector_totals else "",
                "top_sector_pct": round(max(sector_totals.values()), 2) if sector_totals else 0.0,
            },
            "violations": violations,
            "warnings": warnings,
            "notes": _risk_check_notes(risk_level, violations, warnings),
            "metadata": _metadata("risk_check"),
        }

    def comprehensive_analysis(self, db_or_symbols: Session | list[str] | None = None, symbols: list[str] | None = None) -> dict[str, Any]:
        resolved_db, resolved_symbols = self._resolve_db_and_symbols(db_or_symbols, symbols)
        market = self.market_state_analysis(resolved_db)
        sector = self.sector_mainline_analysis(resolved_db)
        validation = self.cross_validate(resolved_db, resolved_symbols)
        proposals = [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "sector": item.get("sector") or "未归因",
                "position_pct": 10,
            }
            for item in validation.get("high_confidence", [])[:5]
        ]
        risk = self.risk_check(resolved_db, proposals)
        return {
            "ok": bool(market.get("ok") or sector.get("ok") or validation.get("items")),
            "context": "comprehensive_analysis",
            "updated_at": beijing_now_string(),
            "market_overview": market,
            "sector_mainline": sector,
            "cross_validation": validation,
            "risk_check": risk,
            "decision": _decision_summary(market, validation, risk),
            "operation_checklist": OPERATION_CHECKLIST,
            "metadata": _metadata("comprehensive_analysis"),
        }

    def _db(self, db: Session | None) -> Session:
        resolved = db or self.db
        if resolved is None:
            raise ValueError("db session is required")
        return resolved

    def _resolve_db_and_symbols(
        self,
        db_or_symbols: Session | list[str] | None,
        symbols: list[str] | None,
    ) -> tuple[Session, list[str]]:
        if symbols is None and isinstance(db_or_symbols, list):
            return self._db(None), db_or_symbols
        return self._db(db_or_symbols if not isinstance(db_or_symbols, list) else None), symbols or []

    def _resolve_db_and_proposals(
        self,
        db_or_proposals: Session | list[dict[str, Any]] | None,
        proposals: list[dict[str, Any]] | None,
    ) -> tuple[Session | None, list[dict[str, Any]]]:
        if proposals is None and isinstance(db_or_proposals, list):
            return self.db, db_or_proposals
        return db_or_proposals if not isinstance(db_or_proposals, list) else self.db, proposals or []

    @staticmethod
    def _safe_call(name: str, func, errors: list[str]):  # noqa: ANN001
        try:
            return func()
        except Exception as exc:  # pragma: no cover - exact providers vary by runtime
            errors.append(f"{name}: {exc}")
            return None

    @staticmethod
    def _degraded(context: str, errors: list[str]) -> dict[str, Any]:
        return {
            "ok": False,
            "context": context,
            "updated_at": beijing_now_string(),
            "market_state": {"state": "degraded", "label": "上下文降级", "confidence_pct": 0},
            "emotion": {},
            "breadth": {},
            "risk": {
                "risk_level": "high",
                "recommended_position_range": {"min_pct": 0, "max_pct": 15},
                "notes": ["行情上下文不可用，禁止因本上下文提高仓位。"],
            },
            "errors": errors or ["unknown error"],
            "metadata": _metadata(context),
        }

