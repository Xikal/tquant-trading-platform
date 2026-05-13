import { useEffect, useMemo, useState } from "react";
import { backtestsApi, type PortfolioOptimizationResponse, type PositionPolicyResearchResponse } from "../../api/backtests";
import { mlSignalsApi, type MLSignalOnlineLearningStatus, type StrategyCapacityResponse } from "../../api/mlSignals";
import { formatBacktestStrategy, formatInteger, formatPct, type BacktestStrategyOption } from "./backtestDisplay";
import {
  capacityTone,
  Empty,
  errorMessage,
  formatMoneyCompact,
  Metric,
  PanelTitle,
  TextField,
} from "./BacktestResearchShared";

export function MLCapacityPanel({ strategyOptions }: { strategyOptions: BacktestStrategyOption[] }) {
  const defaultStrategies = strategyOptions.slice(0, 2).map(([key]) => key).join(",");
  const [status, setStatus] = useState<MLSignalOnlineLearningStatus | null>(null);
  const [capacity, setCapacity] = useState<StrategyCapacityResponse | null>(null);
  const [strategies, setStrategies] = useState(defaultStrategies || "first_board,volume_shrink");
  const [runId, setRunId] = useState("");
  const [markowitz, setMarkowitz] = useState<PortfolioOptimizationResponse | null>(null);
  const [policy, setPolicy] = useState<PositionPolicyResearchResponse | null>(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  const selectedStrategies = useMemo(
    () => strategies.split(",").map((item) => item.trim()).filter(Boolean),
    [strategies],
  );

  const loadStatus = async () => {
    setLoading("status");
    setError("");
    try {
      setStatus(await mlSignalsApi.getOnlineLearningStatus(100));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  };

  const runCapacity = async () => {
    setLoading("capacity");
    setError("");
    try {
      setCapacity(await mlSignalsApi.evaluateCapacity({
        strategies: selectedStrategies,
        capital_levels: [500000, 1000000, 5000000],
      }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  };

  const runIncrementalTrain = async () => {
    setLoading("train");
    setError("");
    try {
      await mlSignalsApi.incrementalTrain({ model_type: "xgboost", min_samples: 100, promote: true, warm_start: true });
      await loadStatus();
    } catch (err) {
      setError(errorMessage(err));
      setLoading("");
    }
  };

  const runPortfolioResearch = async () => {
    const numericRunId = Number(runId);
    if (!Number.isFinite(numericRunId) || numericRunId <= 0) {
      setError("请输入有效的回测任务 ID。");
      return;
    }
    setLoading("portfolio");
    setError("");
    try {
      const [markowitzResult, policyResult] = await Promise.all([
        backtestsApi.getPortfolioOptimization(numericRunId, "markowitz"),
        backtestsApi.getPositionPolicyResearch(numericRunId),
      ]);
      setMarkowitz(markowitzResult);
      setPolicy(policyResult);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading("");
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  return (
    <section className="backtest-research-card span-2">
      <PanelTitle title="ML 在线学习 / 策略容量" meta="模拟盘闭环 + 资金容量" />
      {error ? <div className="backtest-error">{error}</div> : null}
      <div className="backtest-mini-metrics">
        <Metric label="Paper 样本" value={formatInteger(status?.paper_sample_count)} />
        <Metric label="平仓样本" value={formatInteger(status?.closed_trade_sample_count)} />
        <Metric label="正/负样本" value={`${formatInteger(status?.positive_sample_count)} / ${formatInteger(status?.negative_sample_count)}`} />
        <Metric label="训练状态" value={status?.ready_for_training ? "可训练" : "样本不足"} className={status?.ready_for_training ? "pbo-low" : "pbo-medium"} />
      </div>
      <div className="backtest-research-note">
        {status?.next_training_rule ?? "每周一 16:00 后自动触发增量训练；模型仍受样本量、AUC、K-fold 和生产门槛限制。"}
        {status?.latest_incremental_task_id ? ` 最近任务 #${status.latest_incremental_task_id}：${status.latest_incremental_task_status || "--"}。` : ""}
        {status?.production_model_key ? ` 当前生产模型：${status.production_model_key}。` : " 暂无生产模型。"}
      </div>
      {status?.warnings?.length ? (
        <div className="backtest-warning-list">
          {status.warnings.slice(0, 3).map((item) => <span key={item}>{item}</span>)}
        </div>
      ) : null}
      <div className="backtest-capacity-controls">
        <TextField label="容量评估策略" value={strategies} hint="英文逗号分隔" onChange={setStrategies} />
        <TextField label="回测任务 ID" value={runId} hint="用于 Markowitz / RL shadow" onChange={setRunId} />
        <button type="button" onClick={loadStatus} disabled={loading === "status"}>{loading === "status" ? "刷新中..." : "刷新 ML 状态"}</button>
        <button type="button" onClick={runCapacity} disabled={loading === "capacity" || !selectedStrategies.length}>{loading === "capacity" ? "评估中..." : "评估容量"}</button>
        <button type="button" className="secondary" onClick={runIncrementalTrain} disabled={loading === "train"}>{loading === "train" ? "训练中..." : "手动增量训练"}</button>
        <button type="button" className="secondary" onClick={runPortfolioResearch} disabled={loading === "portfolio"}>{loading === "portfolio" ? "计算中..." : "组合 / RL 研究"}</button>
      </div>
      {markowitz ? (
        <div className="backtest-research-note">
          Markowitz：预期 {formatPct(markowitz.expected_return_pct)}，波动 {formatPct(markowitz.volatility_pct)}，
          Sharpe {markowitz.portfolio_sharpe ?? "--"}。{markowitz.summary || ""}
        </div>
      ) : null}
      {markowitz?.weights?.length ? (
        <div className="backtest-data-table compact" role="table" aria-label="Markowitz 权重">
          <div className="row head" role="row"><span>策略</span><span>权重</span><span>均值</span><span>波动</span></div>
          {markowitz.weights.slice(0, 8).map((item) => (
            <div className="row" role="row" key={item.strategy_key}>
              <span>{formatBacktestStrategy(item.strategy_key)}</span>
              <span>{formatPct(item.weight_pct)}</span>
              <span>{formatPct(item.avg_return_pct)}</span>
              <span>{formatPct(item.volatility_pct)}</span>
            </div>
          ))}
        </div>
      ) : null}
      {markowitz?.efficient_frontier?.length ? <EfficientFrontierChart points={markowitz.efficient_frontier} /> : null}
      {policy ? (
        <div className="backtest-research-note">
          RL Shadow：{policy.summary || "仅研究输出，不自动交易。"} 样本 {String(policy.shadow_reinforcement_learning?.sample_count ?? "--")}。
        </div>
      ) : null}
      <div className="backtest-data-table capacity" role="table" aria-label="策略容量评估">
        <div className="row head" role="row">
          <span>策略</span>
          <span>样本</span>
          <span>成交额</span>
          <span>50万</span>
          <span>100万</span>
          <span>500万</span>
          <span>提示</span>
        </div>
        {(capacity?.items ?? []).map((item) => (
          <div className="row" role="row" key={item.strategy_key}>
            <span>{formatBacktestStrategy(item.strategy_key)}</span>
            <span>{formatInteger(item.sample_count)} / {formatInteger(item.symbol_count)}</span>
            <span>{formatMoneyCompact(item.avg_daily_amount)}</span>
            {item.curve.slice(0, 3).map((point) => (
              <span className={capacityTone(point.capacity_status)} key={`${item.strategy_key}-${point.capital}`}>
                {point.capacity_status} · {formatPct(point.net_edge_pct)}
                {point.almgren_chriss_cost_pct !== undefined ? ` / 分批${formatPct(point.almgren_chriss_cost_pct)}` : ""}
              </span>
            ))}
            <span>{item.notes?.[0] || "容量评估完成"}</span>
          </div>
        ))}
        {capacity?.items?.length ? null : <Empty text="点击“评估容量”后显示 Kyle Lambda 与资金冲击曲线。" />}
      </div>
    </section>
  );
}

function EfficientFrontierChart({ points }: { points: NonNullable<PortfolioOptimizationResponse["efficient_frontier"]> }) {
  const visible = points.slice(0, 80);
  const maxRisk = Math.max(...visible.map((item) => Number(item.volatility_pct || 0)), 1);
  const returns = visible.map((item) => Number(item.expected_return_pct || 0));
  const minReturn = Math.min(...returns, 0);
  const maxReturn = Math.max(...returns, 1);
  const range = Math.max(maxReturn - minReturn, 1);
  return (
    <div className="efficient-frontier-card" aria-label="Markowitz 有效前沿">
      <div className="chart-title"><b>风险-收益有效前沿</b><span>横轴波动，纵轴预期收益</span></div>
      <svg viewBox="0 0 320 150" role="img">
        <line x1="28" y1="122" x2="300" y2="122" />
        <line x1="28" y1="18" x2="28" y2="122" />
        {visible.map((point, index) => {
          const x = 28 + (Number(point.volatility_pct || 0) / maxRisk) * 268;
          const y = 122 - ((Number(point.expected_return_pct || 0) - minReturn) / range) * 100;
          return <circle key={`${point.volatility_pct}-${point.expected_return_pct}-${index}`} cx={x} cy={y} r={2.3} />;
        })}
      </svg>
    </div>
  );
}
