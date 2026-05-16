from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.schema_defs.factor_mining import FactorHypothesisOut, FactorHypothesisResponse
from app.services.factor_mining.llm_adapter import FactorMiningLLMAdapter
from app.services.factor_mining.templates import local_hypotheses


class FactorHypothesisAgent:
    def __init__(self, db: Session) -> None:
        self.llm = FactorMiningLLMAdapter(db)

    def generate(self, *, topic: str, count: int, use_llm: bool = True) -> FactorHypothesisResponse:
        if use_llm and self.llm.available():
            items = self._llm_generate(topic=topic, count=count)
            if len(items) >= min(count, 20):
                return FactorHypothesisResponse(provider=self.llm.default_model, items=items[:count])
        warning = "未配置 DeepSeek API Key，已使用本地结构化模板生成。"
        return FactorHypothesisResponse(provider=self.llm.default_model, items=local_hypotheses(topic, count), warning=warning)

    def _llm_generate(self, *, topic: str, count: int) -> list[FactorHypothesisOut]:
        system_prompt = (
            "你是A股短线低吸量化因子研究专家。输出 JSON："
            "{items:[{factor_name,factor_key,hypothesis,data_deps,direction,category,limitations}]}。"
            "必须避免未来函数，必须说明经济逻辑和局限，方向只能 higher_better/lower_better。"
        )
        payload = {
            "topic": topic,
            "count": count,
            "model": self.llm.default_model,
            "existing_factor_warning": "不要重复 VWAP 折价、连续缩量、MA20 回踩等已有方向，除非给出改进。",
        }
        data = self.llm.json_task(system_prompt=system_prompt, payload=payload)
        raw_items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(raw_items, list):
            return []
        items: list[FactorHypothesisOut] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            try:
                item = FactorHypothesisOut.model_validate({**raw, "source": "deepseek-v4-flash"})
            except Exception:
                continue
            items.append(item)
        return items
