from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.schemas import AiDecisionFixedSections, AiDecisionSupportRequest, AiDecisionSupportResponse, AiInsight
from app.services.ai_service import AiService
from app.services.settings_service import SettingsService


MAX_CONTEXT_BYTES = 18_000
MAX_LIST_ITEMS = 12
MAX_PRIORITY_BOARD_ITEMS = 5
MAX_TEXT_LENGTH = 600
PRIORITY_ITEM_FIELDS = (
    "symbol",
    "name",
    "strategy_titles",
    "strategy_count",
    "latest_price",
    "change_pct",
    "buy_signal_text",
    "priority_score",
    "action_summary",
    "industry_tier_text",
    "mainline_tier_text",
    "execution_quality_text",
    "strategy_performance_text",
    "stop_loss",
    "suggested_position_text",
)
PRIORITY_BOARD_CONTEXT_FIELDS = (
    "updated_at",
    "total_candidates",
    "immediate_count",
    "focus_count",
    "market_state_text",
    "market_bonus",
    "regime_confidence",
    "transition_risk",
    "stock_up_ratio",
    "stock_median_change",
    "limit_down_count",
    "limit_up_count",
    "hot_industry_source_text",
    "hot_industries",
    "mainline_lifecycle_text",
    "portfolio_risk",
)


TASK_PROMPTS = {
    "stock_explain": (
        "你是A股策略解释助手。只根据输入的结构化数据解释个股，不得新增不存在的数据。"
        "输出必须是 JSON，字段为 summary, confidence, suggestions, warnings。"
        "summary 说明当前是否值得处理；suggestions 给出观察、买点、止损和仓位执行要点；"
        "warnings 只写明确风险。不能直接承诺收益，不能放松止损。"
    ),
    "daily_review": (
        "你是A股收盘复盘助手。只根据输入的收盘后复盘样本总结今日机会质量。"
        "输出必须是 JSON，字段为 summary, confidence, suggestions, warnings。"
        "suggestions 要给出明日优先跟踪、应剔除和需要等待确认的规则。"
    ),
    "strategy_attribution": (
        "你是A股策略归因助手。只解释输入的命中率、收益率、回撤和分桶归因。"
        "输出必须是 JSON，字段为 summary, confidence, suggestions, warnings。"
        "重点说明策略近期是否应升权、降权或保持观察，不能修改硬买点条件。"
    ),
    "priority_board_summary": (
        "你是A股盘中优先级榜解释助手。只根据榜单、市场状态和行业强弱做文字总结。"
        "输出必须是 JSON，字段为 summary, confidence, suggestions, warnings。"
        "summary 不超过180字；suggestions 最多5条，按优先处理、重点观察、暂不处理三个层次组织；"
        "warnings 最多3条。每条必须短、明确、可执行，不能写长篇复盘。"
    ),
    "event_risk_summary": (
        "你是A股公告/事件风险摘要助手。只根据输入事件输出 summary, confidence, suggestions, warnings。"
        "只能说明摘要、风险类型、严重度、影响周期和证据引用 id；严禁输出买入、卖出、加仓、减仓、持有或放宽止损建议。"
    ),
}


class AiDecisionSupportService:
    def __init__(self) -> None:
        self.ai_service = AiService()

    def explain(self, db: Session, request: AiDecisionSupportRequest) -> AiDecisionSupportResponse:
        settings = SettingsService(db).get_payload().model_dump()
        payload = self._build_payload(request)
        prompt = TASK_PROMPTS[request.task]
        insight = self.ai_service.build_task_insight(
            settings=settings,
            payload=payload,
            system_prompt=prompt,
            include_ai=request.include_ai,
            max_tokens=700 if request.task == "priority_board_summary" else 1600,
        )
        insight = self._guard_insight_output(request.task, insight)
        if request.task == "priority_board_summary" and not insight.enabled:
            insight = self._build_priority_board_quant_fallback(payload.get("context"))
        return AiDecisionSupportResponse(
            task=request.task,
            title=request.title or self._default_title(request.task),
            insight=insight,
            model=settings.get("llm_model", ""),
            provider=settings.get("llm_provider", "auto"),
            fixed_sections=self._build_fixed_sections(request.task, payload.get("context"), insight),
        )

    def _build_payload(self, request: AiDecisionSupportRequest) -> dict[str, Any]:
        context = self._sanitize(request.payload)
        if request.task == "priority_board_summary":
            context = self._compact_priority_board_context(context)
        if request.task == "event_risk_summary":
            context = self._compact_event_risk_context(context)
        payload = {
            "task": request.task,
            "title": request.title,
            "context": context,
            "guardrails": [
                "AI 只解释量化和策略结果，不替代买入、卖出、仓位和止损规则。",
                "如果输入数据不足，必须明确提示数据不足。",
                "不得编造实时价格、行业热点、胜率或收益率。",
                "事件风险摘要不得包含买入、卖出、加仓、减仓、持有或放宽止损建议。",
            ],
        }
        return self._fit_context(payload)

    def _guard_insight_output(self, task: str, insight: AiInsight) -> AiInsight:
        if task != "event_risk_summary":
            return insight
        text = " ".join(
            [
                str(insight.summary or ""),
                *[str(item or "") for item in insight.suggestions],
                *[str(item or "") for item in insight.warnings],
            ]
        )
        if not _contains_trade_advice(text):
            return insight
        return AiInsight(
            enabled=False,
            summary="已拒绝包含买卖建议的事件风险输出；本模块仅保留风险摘要和证据引用。",
            confidence=0.0,
            suggestions=["仅查看事件类型、严重度、影响周期和证据 id。"],
            warnings=["LLM 输出包含买卖建议，已由后端 guard 拦截。"],
            raw={"guarded": "event_risk_trade_advice_rejected", "original": insight.raw},
        )

    def _build_priority_board_quant_fallback(self, context: Any) -> AiInsight:
        if not isinstance(context, dict):
            return AiInsight(
                enabled=False,
                summary="AI 未返回有效内容，本次使用量化规则自动摘要。",
                confidence=0.0,
                suggestions=["优先查看全策略榜单前排，按确定买入、接近买点、继续观察分层处理。"],
                warnings=["AI 解读未生效，不影响硬规则和榜单排序。"],
                raw=None,
            )
        items = context.get("items") if isinstance(context.get("items"), list) else []
        hot_industries = context.get("hot_industries") if isinstance(context.get("hot_industries"), list) else []
        portfolio_risk = context.get("portfolio_risk") if isinstance(context.get("portfolio_risk"), dict) else {}
        immediate = int(context.get("immediate_count") or 0)
        focus = int(context.get("focus_count") or 0)
        total = int(context.get("total_candidates") or len(items) or 0)
        top_items = [self._format_priority_item(item) for item in items[:3] if isinstance(item, dict)]
        summary = self._build_priority_summary(context, total, immediate, focus, hot_industries, top_items)
        suggestions = self._build_priority_suggestions(items, top_items)
        warnings = self._build_priority_warnings(portfolio_risk)
        return AiInsight(
            enabled=False,
            summary=summary,
            confidence=0.0,
            suggestions=suggestions,
            warnings=warnings,
            raw={"fallback": "quant_priority_board"},
        )

    @staticmethod
    def _build_priority_summary(
        context: dict[str, Any],
        total: int,
        immediate: int,
        focus: int,
        hot_industries: list[Any],
        top_items: list[str],
    ) -> str:
        market_text = str(context.get("market_state_text") or "市场状态待确认").split("。", 1)[0]
        hot_text = " / ".join(str(item) for item in hot_industries[:3]) or "暂无明确热点"
        leader_text = "；前排：" + "、".join(top_items[:2]) if top_items else ""
        return f"{market_text}。全策略共 {total} 只，确定买入 {immediate} 只，接近买点 {focus} 只；热点：{hot_text}{leader_text}。"

    def _build_priority_suggestions(self, items: list[Any], top_items: list[str]) -> list[str]:
        buy_items = [
            self._format_priority_item(item)
            for item in items
            if isinstance(item, dict) and "买入" in str(item.get("buy_signal_text") or "")
        ][:3]
        suggestions = [
            f"优先处理：{self._join_or_empty(buy_items, '暂无确定买入，先等价格和止跌确认。')}",
            f"重点观察：{self._join_or_empty(top_items, '暂无前排样本，等待榜单缓存刷新。')}",
            "暂不处理：非主线、风险阻断或未到买点的票，不用因为 AI 解读而放宽规则。",
        ]
        return suggestions

    @staticmethod
    def _build_priority_warnings(portfolio_risk: dict[str, Any]) -> list[str]:
        notes = portfolio_risk.get("notes")
        warnings = ["AI 未返回有效文本，本次为量化规则自动摘要。"]
        if isinstance(notes, list):
            warnings.extend(str(item)[:90] for item in notes[:2])
        return warnings[:3]

    @staticmethod
    def _format_priority_item(item: dict[str, Any]) -> str:
        name = str(item.get("name") or item.get("symbol") or "--")
        symbol = str(item.get("symbol") or "")
        signal = str(item.get("buy_signal_text") or "")
        score = item.get("priority_score")
        score_text = f" 分{float(score):.0f}" if isinstance(score, (int, float)) else ""
        return f"{name}{f'({symbol})' if symbol else ''}{f' {signal}' if signal else ''}{score_text}".strip()

    @staticmethod
    def _join_or_empty(items: list[str], empty_text: str) -> str:
        return "、".join(items) if items else empty_text

    def _compact_priority_board_context(self, context: Any) -> Any:
        if not isinstance(context, dict):
            return context

        items = context.get("items")
        compact = {
            key: self._compact_priority_context_value(key, context[key])
            for key in PRIORITY_BOARD_CONTEXT_FIELDS
            if key in context and context[key] not in ("", None, [])
        }
        if isinstance(items, list):
            compact["items"] = [self._compact_priority_item(item) for item in items[:MAX_PRIORITY_BOARD_ITEMS]]
            compact["items_count_sent_to_ai"] = min(len(items), MAX_PRIORITY_BOARD_ITEMS)
            compact["items_truncated"] = len(items) > MAX_PRIORITY_BOARD_ITEMS
        return compact

    def _compact_event_risk_context(self, context: Any) -> Any:
        if not isinstance(context, dict):
            return context
        result = {
            key: self._trim_value(context[key])
            for key in ("symbol", "trade_date", "severity", "risk_types", "impact_window", "evidence_ids", "summary", "data_quality")
            if key in context
        }
        events = context.get("events")
        if isinstance(events, list):
            result["events"] = [
                {
                    key: self._trim_value(event[key])
                    for key in ("id", "title", "source", "event_time", "risk_level", "description")
                    if isinstance(event, dict) and key in event
                }
                for event in events[:5]
                if isinstance(event, dict)
            ]
        return result

    def _compact_priority_item(self, item: Any) -> Any:
        if not isinstance(item, dict):
            return self._trim_value(item)
        return {
            key: self._compact_priority_item_value(key, item[key])
            for key in PRIORITY_ITEM_FIELDS
            if key in item and item[key] not in ("", None, [])
        }

    def _compact_priority_item_value(self, key: str, value: Any) -> Any:
        if isinstance(value, str):
            limit = 90 if key in {"action_summary", "suggested_position_text"} else 70
            return value[:limit]
        if key == "strategy_titles" and isinstance(value, list):
            return self._trim_value(value[:4])
        return self._trim_value(value)

    def _compact_priority_context_value(self, key: str, value: Any) -> Any:
        if key == "hot_industries" and isinstance(value, list):
            return self._trim_value(value[:5])
        if key == "portfolio_risk" and isinstance(value, dict):
            return {
                field: self._compact_portfolio_value(field, value[field])
                for field in (
                    "risk_level",
                    "recommended_total_cap_pct",
                    "total_planned_position_pct",
                    "holding_position_pct",
                    "top_industry",
                    "industry_concentration_pct",
                    "notes",
                )
                if field in value and value[field] not in ("", None, [])
            }
        if isinstance(value, str):
            return value[:220]
        return self._trim_value(value)

    def _compact_portfolio_value(self, field: str, value: Any) -> Any:
        if field == "notes" and isinstance(value, list):
            return [str(item)[:80] for item in value[:2]]
        if isinstance(value, str):
            return value[:80]
        return self._trim_value(value)

    def _sanitize(self, value: Any) -> Any:
        encoded = jsonable_encoder(value, sqlalchemy_safe=True)
        return self._trim_value(encoded)

    def _trim_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key)[:80]: self._trim_value(item)
                for key, item in list(value.items())[:MAX_LIST_ITEMS * 3]
                if not self._is_sensitive_key(str(key))
            }
        if isinstance(value, list):
            return [self._trim_value(item) for item in value[:MAX_LIST_ITEMS]]
        if isinstance(value, str):
            return value[:MAX_TEXT_LENGTH]
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return str(value)[:MAX_TEXT_LENGTH]

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = key.lower()
        return any(token in normalized for token in ("api_key", "token", "password", "secret"))

    def _fit_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload)
        if len(text.encode("utf-8")) <= MAX_CONTEXT_BYTES:
            return payload
        compact = dict(payload)
        context = compact.get("context")
        if isinstance(context, dict):
            compact["context"] = self._fallback_compact_context(context)
            compact["context_truncated"] = True
        return compact

    @staticmethod
    def _fallback_compact_context(context: dict[str, Any]) -> dict[str, Any]:
        preferred_keys = [
            "updated_at",
            "market_state_text",
            "regime_confidence",
            "transition_risk",
            "stock_up_ratio",
            "stock_median_change",
            "limit_down_count",
            "hot_industries",
            "mainline_lifecycle_text",
            "portfolio_risk",
            "items",
            "items_count_sent_to_ai",
        ]
        compact = {key: context[key] for key in preferred_keys if key in context}
        if compact:
            return compact
        return {key: context[key] for key in list(context)[:8]}

    @staticmethod
    def _default_title(task: str) -> str:
        return {
            "stock_explain": "个股策略解释",
            "daily_review": "收盘后复盘",
            "strategy_attribution": "策略归因解读",
            "priority_board_summary": "优先级榜解读",
            "event_risk_summary": "事件风险摘要",
        }.get(task, "AI 决策辅助")

    def _build_fixed_sections(self, task: str, context: Any, insight: AiInsight) -> AiDecisionFixedSections:
        if task != "priority_board_summary" or not isinstance(context, dict):
            return AiDecisionFixedSections(
                can_buy="按硬规则执行",
                why=self._first_text(insight.summary, insight.suggestions, fallback="量化规则已生成结论。"),
                main_risk=self._first_text("", insight.warnings, fallback="不要放宽止损和仓位。"),
                tomorrow_plan="明天继续按买点、止损和仓位复查。",
            )
        immediate = int(context.get("immediate_count") or 0)
        focus = int(context.get("focus_count") or 0)
        if immediate > 0:
            can_buy = f"可以小仓，只看前排 {min(immediate, 3)} 只"
        elif focus > 0:
            can_buy = "等到价格，暂不提前买"
        else:
            can_buy = "不能买，空仓或只处理持仓"
        why = self._first_text(
            str(context.get("market_state_text") or ""),
            insight.suggestions,
            fallback="榜单暂未给出确定买入，按价格和止跌确认执行。",
        )
        return AiDecisionFixedSections(
            can_buy=can_buy,
            why=why[:160],
            main_risk=self._first_text("", insight.warnings, fallback="最大风险是未到买点提前买，或跌破止损不退出。")[:160],
            tomorrow_plan="明天先看是否仍在买点区，冲高先减仓，跌破止损先退出。",
        )

    @staticmethod
    def _first_text(primary: str, items: list[str], fallback: str) -> str:
        primary = str(primary or "").strip()
        if primary:
            return primary
        for item in items:
            text = str(item or "").strip()
            if text:
                return text
        return fallback


def _contains_trade_advice(text: str) -> bool:
    normalized = str(text or "")
    trade_tokens = (
        "直接买入",
        "买入",
        "卖出",
        "加仓",
        "减仓",
        "满仓",
        "清仓",
        "持有",
        "拿着",
        "放宽止损",
        "不用止损",
    )
    return any(token in normalized for token in trade_tokens)
