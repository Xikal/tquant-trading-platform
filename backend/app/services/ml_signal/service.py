from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import BacktestTrade, MLSignalSample, PaperTrade
from app.models.schema_defs.phase4 import (
    MLSignalPredictionRequest,
    MLSignalPredictionResponse,
    MLSignalSampleBuildRequest,
    MLSignalSampleBuildResponse,
)


FEATURE_NAMES = [
    "price",
    "quantity",
    "gross_amount",
    "strategy_known",
    "market_state_known",
    "is_sell",
]


class MLSignalService:
    """Research-only signal model surface.

    The first implementation focuses on sample creation and a deterministic
    inference contract. Real XGBoost/LightGBM training can plug into this
    service once enough verified samples exist.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def build_samples(self, payload: MLSignalSampleBuildRequest) -> MLSignalSampleBuildResponse:
        samples: list[dict[str, Any]] = []
        if payload.source in ("paper", "combined"):
            samples.extend(self._paper_samples(payload.limit))
        if payload.source in ("backtest", "combined") and len(samples) < payload.limit:
            samples.extend(self._backtest_samples(payload.limit - len(samples)))
        persisted = 0
        if payload.persist:
            for sample in samples:
                if self._persist_sample(sample):
                    persisted += 1
            self.db.commit()
        warning = ""
        if len(samples) < 1000:
            warning = "样本量不足，当前仅用于研究和数据沉淀，不能进入生产交易建议。"
        return MLSignalSampleBuildResponse(
            source=payload.source,
            generated=len(samples),
            persisted=persisted,
            feature_names=FEATURE_NAMES,
            warning=warning,
        )

    def predict(self, payload: MLSignalPredictionRequest) -> MLSignalPredictionResponse:
        features = payload.features or {}
        score = 0.5
        reasons: list[str] = []
        if _to_float(features.get("priority_score")) >= 80:
            score += 0.18
            reasons.append("优先级分数较高。")
        if _to_float(features.get("risk_score")) >= 6:
            score -= 0.2
            reasons.append("风险分偏高。")
        if _to_float(features.get("volume_shrink_ratio")) and _to_float(features.get("volume_shrink_ratio")) <= 0.8:
            score += 0.08
            reasons.append("缩量承接特征较好。")
        probability = round(min(max(score, 0.0), 1.0), 3)
        label = "positive" if probability >= 0.62 else "negative" if probability <= 0.38 else "neutral"
        return MLSignalPredictionResponse(
            symbol=payload.symbol,
            model_key=payload.model_key,
            model_type="heuristic",
            research_only=True,
            probability=probability,
            label=label,  # type: ignore[arg-type]
            confidence=round(abs(probability - 0.5) * 2, 3),
            reasons=reasons or ["模型骨架未训练，仅输出研究型启发式结果。"],
        )

    def _paper_samples(self, limit: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(PaperTrade).order_by(PaperTrade.id.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "sample_key": f"paper:{row.id}",
                "symbol": row.symbol,
                "trade_date": row.trade_time.date().isoformat() if row.trade_time else "",
                "strategy_key": row.strategy_key,
                "source": "paper",
                "features": _trade_features(
                    price=float(row.price or 0),
                    quantity=int(row.quantity or 0),
                    gross_amount=float(row.gross_amount or 0),
                    strategy_key=row.strategy_key,
                    market_state=row.market_state,
                    side=row.side,
                ),
                "label": {"side": row.side, "net_amount": float(row.net_amount or 0)},
            }
            for row in rows
        ]

    def _backtest_samples(self, limit: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(BacktestTrade).order_by(BacktestTrade.id.desc()).limit(limit)
        ).scalars().all()
        return [
            {
                "sample_key": f"backtest:{row.id}",
                "symbol": row.symbol,
                "trade_date": row.trade_date,
                "strategy_key": row.strategy_key,
                "source": "backtest",
                "features": _trade_features(
                    price=float(row.price or 0),
                    quantity=int(row.quantity or 0),
                    gross_amount=float(row.gross_amount or 0),
                    strategy_key=row.strategy_key,
                    market_state=row.market_state,
                    side=row.side,
                ),
                "label": {"pnl_pct": float(row.pnl_pct or 0), "pnl_amount": float(row.pnl_amount or 0)},
            }
            for row in rows
        ]

    def _persist_sample(self, sample: dict[str, Any]) -> bool:
        existing = self.db.execute(
            select(MLSignalSample).where(MLSignalSample.sample_key == sample["sample_key"])
        ).scalar_one_or_none()
        if existing is not None:
            return False
        self.db.add(
            MLSignalSample(
                sample_key=sample["sample_key"],
                symbol=sample["symbol"],
                trade_date=sample["trade_date"],
                strategy_key=sample["strategy_key"],
                source=sample["source"],
                feature_json=_json_dumps(sample["features"]),
                label_json=_json_dumps(sample["label"]),
            )
        )
        return True


def _trade_features(
    *,
    price: float,
    quantity: int,
    gross_amount: float,
    strategy_key: str,
    market_state: str,
    side: str,
) -> dict[str, Any]:
    return {
        "price": price,
        "quantity": quantity,
        "gross_amount": gross_amount,
        "strategy_known": 1 if strategy_key else 0,
        "market_state_known": 1 if market_state else 0,
        "is_sell": 1 if side == "sell" else 0,
    }


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
