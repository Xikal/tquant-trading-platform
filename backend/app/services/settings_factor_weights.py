from __future__ import annotations

from app.models.schema_defs.settings import FactorSpecOut, FactorWeightsResponse, FactorWeightsUpdate
from app.services.low_buy.factor_functions import (
    default_factor_weights,
    get_effective_factor_weights,
    list_factor_specs,
    save_factor_weight_overrides,
)


class SettingsFactorWeightsService:
    """Factor weight seam used by Settings routes and Settings BFF."""

    def build_response(self) -> FactorWeightsResponse:
        specs = list_factor_specs()
        return FactorWeightsResponse(
            weights=get_effective_factor_weights(),
            defaults=default_factor_weights(),
            factors=[
                FactorSpecOut(
                    name=spec.name,
                    weight=spec.weight,
                    data_dependencies=list(spec.data_dependencies),
                    applicable_strategies=list(spec.applicable_strategies),
                    activation_condition=spec.activation_condition,
                    status=spec.status,
                    status_text=spec.status_text,
                )
                for spec in specs
            ],
        )

    def update_response(self, payload: FactorWeightsUpdate) -> FactorWeightsResponse:
        save_factor_weight_overrides(payload.weights)
        return self.build_response()
