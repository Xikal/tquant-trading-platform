from __future__ import annotations

from app.core.timezone import beijing_now_string
from app.models.schema_defs.market import IntradayAnomalyResponse
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
        quote = self.market_data.get_quote(symbol)
        bars = self.market_data.get_intraday_bars(symbol, period="1m", limit=60)
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
        if quote.change_pct >= 5.0:
            score += 20
            reasons.append("日内涨幅较大，存在冲高兑现压力。")
        if quote.change_pct <= -4.0:
            score += 18
            reasons.append("日内跌幅较大，存在退潮或风险释放。")
        if (quote.volume_ratio or 0.0) >= 2.5:
            score += 14
            reasons.append("量比显著放大，需确认是承接还是出货。")
        if bars:
            latest = bars[-1]
            high = max(bar.high for bar in bars)
            low = min(bar.low for bar in bars)
            range_pct = (high / max(low, 0.01) - 1.0) * 100
            close_position = (latest.close - low) / max(high - low, 0.01)
            early_high_retrace = (high - latest.close) / max(high, 0.01) * 100
            if range_pct >= 4.0:
                score += 12
                reasons.append(f"近 60 分钟振幅约 {range_pct:.1f}%，波动异常放大。")
            if early_high_retrace >= 2.0 and close_position < 0.45:
                score += 18
                pattern = "冲高回落"
                reasons.append("冲高后回落明显，可能进入兑现或退潮节点。")
            elif close_position >= 0.72 and quote.change_pct > 1.5:
                score += 8
                pattern = "拉伸加速"
                reasons.append("价格维持在分时高位，属于强拉伸状态。")
            volumes = [float(bar.volume or 0.0) for bar in bars[-10:]]
            if len(volumes) >= 5 and volumes[-1] > max(sum(volumes[:-1]) / max(len(volumes) - 1, 1), 1.0) * 2:
                score += 10
                reasons.append("最新分钟量能突然放大，需防范急拉急跌。")
        if quote.is_stale:
            score += 12
            risk_notes.append("行情源标记为延迟或降级，信号仅供观察。")
        level = "normal"
        text = "暂无异常"
        hint = "按原计划观察，不因单一波动追买。"
        if score >= 55:
            level = "high"
            text = "高异常"
            hint = "优先暂停新增买入；已有仓位按止盈/止损计划处理。"
        elif score >= 32:
            level = "medium"
            text = "中等异常"
            hint = "降低仓位动作，等待 VWAP 或关键位重新确认。"
        elif score >= 18:
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
