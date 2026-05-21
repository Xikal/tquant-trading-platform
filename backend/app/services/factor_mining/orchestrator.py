from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.schema_defs.factor_mining import (
    FactorCodeSynthRequest,
    FactorEvaluationRequest,
    FactorEvaluationResponse,
    FactorHypothesisOut,
    FactorHypothesisResponse,
    FactorIterationResponse,
)
from app.services.factor_mining.code_synth_agent import FactorCodeSynthAgent
from app.services.factor_mining.evaluation import FactorEvaluationEngine
from app.services.factor_mining.hypothesis_agent import FactorHypothesisAgent
from app.services.factor_mining.interpreter_agent import FactorResultInterpreter
from app.services.factor_mining.library import FactorLibrary, factor_out
from app.services.factor_mining.runtime_values import store_latest_factor_values


class FactorMiningOrchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.library = FactorLibrary(db)

    def hypotheses(self, *, topic: str, count: int, use_llm: bool = True) -> FactorHypothesisResponse:
        return FactorHypothesisAgent(self.db).generate(topic=topic, count=count, use_llm=use_llm)

    def evaluate_factor(self, factor_key: str, request: FactorEvaluationRequest) -> FactorEvaluationResponse:
        row = self.library.get(factor_key)
        payload = FactorEvaluationEngine(self.db).evaluate(row.formula_code, request)
        interpretation = FactorResultInterpreter(self.db).interpret(factor_name=row.name, result=payload.result)
        store_latest_factor_values(self.db, row.factor_key, payload.factor_values)
        run = self.library.save_evaluation(
            row,
            result=payload.result,
            interpretation=interpretation,
            request=request,
            elapsed_seconds=payload.elapsed_seconds,
        )
        return FactorEvaluationResponse(
            factor=factor_out(row),
            result=payload.result,
            interpretation=interpretation,
            run_id=run.id,
            elapsed_seconds=payload.elapsed_seconds,
        )

    def iterate(
        self,
        *,
        hypothesis: FactorHypothesisOut,
        rounds: int,
        evaluation: FactorEvaluationRequest,
    ) -> FactorIterationResponse:
        responses: list[FactorEvaluationResponse] = []
        current = hypothesis
        for index in range(rounds):
            synth = FactorCodeSynthAgent(self.db).synthesize(FactorCodeSynthRequest(hypothesis=current, use_llm=index == 0))
            factor_key = f"{current.factor_key}_iter{index + 1}"
            try:
                self.library.create(
                    _create_request(current, factor_key=factor_key, formula_code=synth.formula_code)
                )
            except ValueError:
                pass
            response = self.evaluate_factor(factor_key, evaluation)
            responses.append(response)
            if response.result.passed_production_gate:
                break
        final_verdict = responses[-1].interpretation.get("verdict", "reject") if responses else "reject"
        return FactorIterationResponse(rounds=responses, final_verdict=str(final_verdict))


def _create_request(hypothesis: FactorHypothesisOut, *, factor_key: str, formula_code: str):
    from app.models.schema_defs.factor_mining import FactorCreateRequest

    return FactorCreateRequest(
        factor_key=factor_key,
        name=hypothesis.factor_name,
        hypothesis=hypothesis.hypothesis,
        formula_code=formula_code,
        data_deps=hypothesis.data_deps,
        direction=hypothesis.direction,
        category=hypothesis.category,
        source="llm_generated",
    )
