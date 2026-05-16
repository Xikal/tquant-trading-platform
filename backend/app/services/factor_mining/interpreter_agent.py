from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.schema_defs.factor_mining import FactorEvalResultOut
from app.services.factor_mining.llm_adapter import FactorMiningLLMAdapter


class FactorResultInterpreter:
    def __init__(self, db: Session) -> None:
        self.llm = FactorMiningLLMAdapter(db)

    def interpret(self, *, factor_name: str, result: FactorEvalResultOut) -> dict[str, Any]:
        verdict = _verdict(result)
        fallback = {
            "verdict": verdict,
            "reasoning": _reasoning(result),
            "improvements": _improvements(result),
            "combination_value": "需与已有生产因子做相关性矩阵检验，相关性低于 0.6 才建议生产化。",
        }
        if not self.llm.available():
            return fallback
        data = self.llm.json_task(
            system_prompt=(
                "你是量化因子评估解读员。输出 JSON："
                "{verdict,reasoning,improvements,combination_value}，不得给确定性收益承诺。"
            ),
            payload={"factor_name": factor_name, "metrics": result.model_dump(), "fallback_verdict": verdict},
            max_tokens=1800,
        )
        return data if data else fallback


def _verdict(result: FactorEvalResultOut) -> str:
    if result.passed_production_gate:
        return "keep_production_candidate"
    if result.passed_candidate_gate:
        return "keep_research"
    return "improve_or_reject"


def _reasoning(result: FactorEvalResultOut) -> str:
    return (
        f"IC={result.ic_mean:.4f}, t={result.ic_t_stat:.2f}, ICIR={result.icir:.2f}, "
        f"OOS_IC={result.oos_ic_mean:.4f}, Top五分位={result.top_quintile_return:.2%}。"
    )


def _improvements(result: FactorEvalResultOut) -> list[str]:
    items: list[str] = []
    if result.ic_t_stat <= 2:
        items.append("提升样本外显著性，避免只在少数日期有效。")
    if not result.is_oos_consistent:
        items.append("收紧市场状态或行业过滤，降低 IS/OOS 差距。")
    if result.half_life_days < 3:
        items.append("缩短持有周期或改造成盘中确认因子。")
    return items or ["保留当前公式，下一步做 Walk-forward 与相关性检验。"]
