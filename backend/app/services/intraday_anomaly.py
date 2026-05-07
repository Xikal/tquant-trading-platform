from __future__ import annotations

from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import (
    IntradayAnomalyResponse,
    MarketModelValidationMetric,
    MarketModelValidationResponse,
)
from app.services.market.parameter_defaults import MARKET_INTRADAY_ANOMALY_DEFAULTS
from app.services.market_data import MarketDataService


class IntradayAnomalyService:
    """Detect intraday stretch/retreat anomalies for active A-share names.

    The first production version uses deterministic features and keeps a model
    hook boundary.  It intentionally reports warnings instead of trading
    instructions so low-quality model output cannot bypass hard risk rules.
    """

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self.market_data = market_data or MarketDataService()

    def detect(self, symbol: str) -> IntradayAnomalyResponse:
        params = _params()
        quote = self.market_data.get_quote(symbol)
        bars = self.market_data.get_intraday_bars(
            symbol,
            period="1m",
            limit=_int_param(params, "intraday_bar_limit"),
        )
        reasons: list[str] = []
        risk_notes: list[str] = []
        score = 0.0
        pattern = "正常波动"
        if quote.last_price <= 0:
            return IntradayAnomalyResponse(
                symbol=symbol,
                name=quote.name,
                updated_at=beijing_now_string(),
                anomaly_level="data_unavailable",
                anomaly_text="行情数据异常",
                score=0.0,
                pattern="价格无效",
                action_hint="等待行情恢复后再判断。",
                risk_notes=["当前价格为 0 或缺失，禁止用于交易判断。"],
                data_quality_text=quote.data_quality_message or quote.data_quality or "行情异常",
            )
        if quote.change_pct >= _float_param(params, "change_up_threshold_pct"):
            score += _float_param(params, "change_up_score")
            reasons.append("日内涨幅较大，存在冲高兑现压力。")
        if quote.change_pct <= _float_param(params, "change_down_threshold_pct"):
            score += _float_param(params, "change_down_score")
            reasons.append("日内跌幅较大，存在退潮或风险释放。")
        if (quote.volume_ratio or 0.0) >= _float_param(params, "volume_ratio_threshold"):
            score += _float_param(params, "volume_ratio_score")
            reasons.append("量比显著放大，需确认是承接还是出货。")
        if bars:
            latest = bars[-1]
            high = max(bar.high for bar in bars)
            low = min(bar.low for bar in bars)
            range_pct = (high / max(low, 0.01) - 1.0) * 100
            close_position = (latest.close - low) / max(high - low, 0.01)
            early_high_retrace = (high - latest.close) / max(high, 0.01) * 100
            if range_pct >= _float_param(params, "range_pct_threshold"):
                score += _float_param(params, "range_score")
                reasons.append(f"近 60 分钟振幅约 {range_pct:.1f}%，波动异常放大。")
            if (
                early_high_retrace >= _float_param(params, "high_retrace_threshold_pct")
                and close_position < _float_param(params, "weak_close_position_max")
            ):
                score += _float_param(params, "retrace_score")
                pattern = "冲高回落"
                reasons.append("冲高后回落明显，可能进入兑现或退潮节点。")
            elif (
                close_position >= _float_param(params, "strong_close_position_min")
                and quote.change_pct > _float_param(params, "strong_change_min_pct")
            ):
                score += _float_param(params, "strong_stretch_score")
                pattern = "拉伸加速"
                reasons.append("价格维持在分时高位，属于强拉伸状态。")
            volumes = [float(bar.volume or 0.0) for bar in bars[-_int_param(params, "volume_tail_count"):]]
            if (
                len(volumes) >= _int_param(params, "volume_tail_min_count")
                and volumes[-1] > max(sum(volumes[:-1]) / max(len(volumes) - 1, 1), 1.0) * _float_param(params, "volume_spike_multiplier")
            ):
                score += _float_param(params, "volume_spike_score")
                reasons.append("最新分钟量能突然放大，需防范急拉急跌。")
        if quote.is_stale:
            score += _float_param(params, "stale_data_score")
            risk_notes.append("行情源标记为延迟或降级，信号仅供观察。")
        level = "normal"
        text = "暂无异常"
        hint = "按原计划观察，不因单一波动追买。"
        if score >= _float_param(params, "high_level_score"):
            level = "high"
            text = "高异常"
            hint = "优先暂停新增买入；已有仓位按止盈/止损计划处理。"
        elif score >= _float_param(params, "medium_level_score"):
            level = "medium"
            text = "中等异常"
            hint = "降低仓位动作，等待 VWAP 或关键位重新确认。"
        elif score >= _float_param(params, "watch_level_score"):
            level = "watch"
            text = "需要观察"
            hint = "只观察不追高，等待量价结构稳定。"
        return IntradayAnomalyResponse(
            symbol=symbol,
            name=quote.name,
            updated_at=beijing_now_string(),
            anomaly_level=level,
            anomaly_text=text,
            score=round(min(score, 100.0), 1),
            pattern=pattern,
            action_hint=hint,
            reasons=reasons or ["量价结构未触发异常阈值。"],
            risk_notes=risk_notes,
            data_quality_text=quote.data_quality_message or quote.data_quality or "行情正常",
        )

    def validation_report(self, symbols: list[str]) -> MarketModelValidationResponse:
        """Validate anomaly model readiness on a bounded symbol set."""

        params = _params()
        checked: list[IntradayAnomalyResponse] = []
        for symbol in symbols[:_int_param(params, "validation_symbol_limit")]:
            cleaned = str(symbol or "").strip()
            if not cleaned:
                continue
            try:
                checked.append(self.detect(cleaned))
            except Exception:
                continue
        valid = [item for item in checked if item.anomaly_level != "data_unavailable"]
        actionable = [item for item in valid if item.anomaly_level in {"watch", "medium", "high"}]
        high_quality = [
            item for item in actionable
            if item.score >= _float_param(params, "validation_min_score") and item.pattern and item.action_hint and item.risk_notes is not None
        ]
        pass_rate = len(high_quality) / max(len(actionable), 1) * 100.0 if actionable else 0.0
        production_ready = len(valid) >= _int_param(params, "validation_min_samples") and (
            not actionable or pass_rate >= _float_param(params, "validation_pass_rate_min_pct")
        )
        return MarketModelValidationResponse(
            model_key="intraday_anomaly",
            generated_at=beijing_now_string(),
            production_ready=production_ready,
            acceptance_status="passed" if production_ready else "watch",
            metrics=[
                MarketModelValidationMetric(
                    name="异常识别输出完整性",
                    status="passed" if production_ready else "watch",
                    sample_count=len(valid),
                    pass_rate_pct=round(pass_rate, 2),
                    avg_edge_pct=0.0,
                    notes="检查异常模型是否返回等级、模式、建议和风险提示，避免空字段进入前端或通知。",
                )
            ],
            notes=[
                "盘中异常模型只做预警，不参与放宽买点或自动买入。",
                "验收样本不足时仍允许页面展示，但生产通知应保持观察级别。",
            ],
        )


def _params() -> dict[str, object]:
    from app.services.quant.runtime_parameters import get_market_intraday_anomaly

    values = get_market_intraday_anomaly()
    return {**MARKET_INTRADAY_ANOMALY_DEFAULTS, **values} if isinstance(values, dict) else dict(MARKET_INTRADAY_ANOMALY_DEFAULTS)


def _float_param(params: dict[str, object], key: str) -> float:
    try:
        return float(params.get(key, MARKET_INTRADAY_ANOMALY_DEFAULTS[key]))
    except (KeyError, TypeError, ValueError):
        return float(MARKET_INTRADAY_ANOMALY_DEFAULTS[key])


def _int_param(params: dict[str, object], key: str) -> int:
    return int(round(_float_param(params, key)))
