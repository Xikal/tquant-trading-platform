import { useEffect, useMemo } from "react";
import { Button } from "antd";
import { backtestsApi, type PortfolioOptimizationResponse, type PortfolioOptimizationWeight, type PositionPolicyResearchResponse } from "../../api/backtests";
import { mlSignalsApi, type MLSignalOnlineLearningStatus, type StrategyCapacityItem, type StrategyCapacityResponse } from "../../api/mlSignals";
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
import { DataTable } from "../../ui/table/DataTable";
import { useBacktestResearchUiStore } from "../../stores/backtestResearchUiStore";

export function MLCapacityPanel({ strategyOptions }: { strategyOptions: BacktestStrategyOption[] }) {
  const defaultStrategies = strategyOptions.slice(0, 2).map(([key]) => key).join(",");
  const strategies = useBacktestResearchUiStore((ui) => ui.capacityStrategies) || defaultStrategies || "first_board,volume_shrink";
  const runId = useBacktestResearchUiStore((ui) => ui.capacityRunId);
  const status = useBacktestResearchUiStore((ui) => ui.mlStatus);
  const capacity = useBacktestResearchUiStore((ui) => ui.capacity);
  const markowitz = useBacktestResearchUiStore((ui) => ui.markowitz);
  const blackLitterman = useBacktestResearchUiStore((ui) => ui.blackLitterman);
  const policy = useBacktestResearchUiStore((ui) => ui.policy);
  const loading = useBacktestResearchUiStore((ui) => ui.capacityLoading);
  const error = useBacktestResearchUiStore((ui) => ui.capacityError);
  const setStrategies = useBacktestResearchUiStore((ui) => ui.setCapacityStrategies);
  const setRunId = useBacktestResearchUiStore((ui) => ui.setCapacityRunId);
  const setStatus = useBacktestResearchUiStore((ui) => ui.setMlStatus);
  const setCapacity = useBacktestResearchUiStore((ui) => ui.setCapacity);
  const setMarkowitz = useBacktestResearchUiStore((ui) => ui.setMarkowitz);
  const setBlackLitterman = useBacktestResearchUiStore((ui) => ui.setBlackLitterman);
  const setPolicy = useBacktestResearchUiStore((ui) => ui.setPolicy);
  const setLoading = useBacktestResearchUiStore((ui) => ui.setCapacityLoading);
  const setError = useBacktestResearchUiStore((ui) => ui.setCapacityError);

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
      const [markowitzResult, blackLittermanResult, policyResult] = await Promise.all([
        backtestsApi.getPortfolioOptimization(numericRunId, "markowitz"),
        backtestsApi.getPortfolioOptimization(numericRunId, "black_litterman"),
        backtestsApi.getPositionPolicyResearch(numericRunId),
      ]);
      setMarkowitz(markowitzResult);
      setBlackLitterman(blackLittermanResult);
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
        <Button onClick={loadStatus} disabled={loading === "status"}>{loading === "status" ? "刷新中..." : "刷新 ML 状态"}</Button>
        <Button onClick={runCapacity} disabled={loading === "capacity" || !selectedStrategies.length}>{loading === "capacity" ? "评估中..." : "评估容量"}</Button>
        <Button onClick={runIncrementalTrain} disabled={loading === "train"}>{loading === "train" ? "训练中..." : "手动增量训练"}</Button>
        <Button onClick={runPortfolioResearch} disabled={loading === "portfolio"}>{loading === "portfolio" ? "计算中..." : "组合 / RL 研究"}</Button>
      </div>
      {markowitz ? (
        <div className="backtest-research-note">
          Markowitz：预期 {formatPct(markowitz.expected_return_pct)}，波动 {formatPct(markowitz.volatility_pct)}，
          Sharpe {markowitz.portfolio_sharpe ?? "--"}。{markowitz.summary || ""}
        </div>
      ) : null}
      {markowitz?.weights?.length ? (
        <DataTable<PortfolioOptimizationWeight>
          className="backtest-data-table compact"
          rowKey="strategy_key"
          dataSource={markowitz.weights.slice(0, 8)}
          columns={[
            { title: "策略", dataIndex: "strategy_key", render: (value) => formatBacktestStrategy(value) },
            { title: "权重", dataIndex: "weight_pct", align: "right", render: (value) => formatPct(value) },
            { title: "均值", dataIndex: "avg_return_pct", align: "right", render: (value) => formatPct(value) },
            { title: "波动", dataIndex: "volatility_pct", align: "right", render: (value) => formatPct(value) },
          ]}
        />
      ) : null}
      {markowitz?.efficient_frontier?.length ? <EfficientFrontierChart points={markowitz.efficient_frontier} /> : null}
      {blackLitterman ? (
        <div className="backtest-research-note">
          Black-Litterman：预期 {formatPct(blackLitterman.expected_return_pct)}，波动 {formatPct(blackLitterman.volatility_pct)}，
          Sharpe {blackLitterman.portfolio_sharpe ?? "--"}。{blackLitterman.summary || ""}
        </div>
      ) : null}
      {policy ? (
        <div className="backtest-research-note">
          RL Shadow：{policy.summary || "仅研究输出，不自动交易。"} 样本 {String(policy.shadow_reinforcement_learning?.sample_count ?? "--")}。
        </div>
      ) : null}
      <DataTable<StrategyCapacityItem>
        className="backtest-data-table capacity"
        rowKey="strategy_key"
        dataSource={capacity?.items ?? []}
        locale={{ emptyText: <Empty text="点击“评估容量”后显示 Kyle Lambda 与资金冲击曲线。" /> }}
        scroll={{ x: 1120 }}
        columns={[
          { title: "策略", dataIndex: "strategy_key", render: (value) => formatBacktestStrategy(value) },
          { title: "样本", render: (_value, item) => `${formatInteger(item.sample_count)} / ${formatInteger(item.symbol_count)}` },
          { title: "成交额", dataIndex: "avg_daily_amount", align: "right", render: (value) => formatMoneyCompact(value) },
          ...[0, 1, 2].map((index) => ({
            title: ["50万", "100万", "500万"][index],
            render: (_value: unknown, item: StrategyCapacityItem) => {
              const point = item.curve[index];
              if (!point) return "--";
              return (
                <span className={capacityTone(point.capacity_status)}>
                  {point.capacity_status} · {formatPct(point.net_edge_pct)}
                  {point.almgren_chriss_cost_pct !== undefined ? ` / 分批${formatPct(point.almgren_chriss_cost_pct)}` : ""}
                </span>
              );
            },
          })),
          { title: "提示", render: (_value, item) => item.notes?.[0] || "容量评估完成" },
        ]}
      />
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
