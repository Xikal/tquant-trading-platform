from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.schema_defs.factor_mining import FactorCodeSynthRequest, FactorCodeSynthResponse
from app.services.factor_mining.compute_engine import FactorComputeEngine, FactorSafetyError
from app.services.factor_mining.llm_adapter import FactorMiningLLMAdapter
from app.services.factor_mining.templates import synth_formula_for_hypothesis


class FactorCodeSynthAgent:
    def __init__(self, db: Session) -> None:
        self.llm = FactorMiningLLMAdapter(db)

    def synthesize(self, payload: FactorCodeSynthRequest) -> FactorCodeSynthResponse:
        formula = ""
        warning = ""
        if payload.use_llm and self.llm.available():
            formula = self._llm_synthesize(payload)
        if not formula:
            formula = synth_formula_for_hypothesis(payload.hypothesis.factor_key)
            warning = "未配置 DeepSeek 或返回不可用，已使用本地安全模板。"
        try:
            FactorComputeEngine().validate(formula)
            safety = True
        except FactorSafetyError as exc:
            formula = synth_formula_for_hypothesis(payload.hypothesis.factor_key)
            warning = f"LLM 代码安全检查失败，已回退本地模板：{exc}"
            safety = True
        return FactorCodeSynthResponse(
            factor_key=payload.hypothesis.factor_key,
            formula_code=formula,
            unit_tests=["输出必须为 pd.Series", "禁止 import/open/exec/eval", "无穷值必须转为 NaN 或 0"],
            safety_passed=safety,
            warning=warning,
        )

    def _llm_synthesize(self, payload: FactorCodeSynthRequest) -> str:
        data = self.llm.json_task(
            system_prompt=(
                "你是安全的量化因子代码生成器。只输出 JSON：{formula_code:string}。"
                "代码必须定义 compute_factor(bars)，禁止 import，使用已注入的 pd/np/math。"
            ),
            payload=payload.model_dump(),
            max_tokens=2200,
        )
        value = data.get("formula_code") if isinstance(data, dict) else ""
        return value.strip() if isinstance(value, str) else ""
