import type { BacktestResult, BacktestRun, LowBuyExecutionBacktestResult, LowBuyPriorityBoardResult, LowBuyTradeLifecycle, ReplayItem, StrategyValidationReport } from "../../types";
import { EditableGrid, EmptyState, MetricGrid, PanelTitle } from "./WorkspaceComponents";
import { ALL_PLAYBOOK_TABS } from "./workspaceConstants";
import { actionText, average, executionStatusText, formatNumber, formatPct, formatPrice, lifecycleStatusText, shortTime, strategyLabel, summarizeLifecycle, toneFromChange } from "./workspaceFormatters";
import type { BacktestDraft } from "./workspaceTypes";

export function ResearchPage({
  replays,
  priorityBoard,
  lifecycleItems,
  draft,
  setDraft,
  result,
  runs,
  executionBacktest,
  strategyValidation,
  loading,
  onRun,
  onValidate,
  onRefresh,
}: {
  replays: ReplayItem[];
  priorityBoard: LowBuyPriorityBoardResult | null;
  lifecycleItems: LowBuyTradeLifecycle[];
  draft: BacktestDraft;
  setDraft: (draft: BacktestDraft) => void;
  result: BacktestResult | null;
  runs: BacktestRun[];
  executionBacktest: LowBuyExecutionBacktestResult | null;
  strategyValidation: StrategyValidationReport | null;
  loading: string;
  onRun: () => void;
  onValidate: () => void;
  onRefresh: () => void;
}) {
  const avgPnl = average(replays.map((item) => item.pnl_pct));
  const lifecycleSummary = summarizeLifecycle(lifecycleItems);
  const topFamily = priorityBoard?.family_sections?.[0];
  return (
    <section className="page-grid research-grid">
      <div className="panel research-hero">
        <div>
          <PanelTitle title="信号复盘与样本外验证" actions={<button onClick={onRefresh} disabled={loading === "research"}>刷新复盘</button>} />
          <p className="hint">用复盘和样本外验证检查信号稳定性，核心只看胜率、盈亏比和回撤。样本少时不放大仓位。</p>
        </div>
        <MetricGrid
          className="summary-panel research-metrics"
          items={[
            { label: "最近运行", value: replays[0] ? shortTime(replays[0].created_at) : "--", tone: "neutral" },
            { label: "复盘样本", value: String(replays.length), tone: "neutral" },
            { label: "平均收益", value: formatPct(avgPnl), tone: toneFromChange(avgPnl) },
            { label: "策略族净胜优势", value: formatPct(topFamily?.performance?.net_win_rate, 1), tone: toneFromChange(topFamily?.performance?.net_win_rate) },
            { label: "真实成交率", value: executionBacktest ? formatPct(executionBacktest.filled_signals / Math.max(executionBacktest.evaluated_signals, 1) * 100, 1) : "--", tone: "neutral" },
            { label: "生命周期", value: lifecycleSummary, tone: "warn" },
          ]}
        />
      </div>
      <aside className="panel research-run">
        <PanelTitle title="运行回测" />
        <EditableGrid
          fields={[
            ["证券代码", draft.symbol, (value) => setDraft({ ...draft, symbol: value })],
            ["样本窗口", draft.lookback_bars, (value) => setDraft({ ...draft, lookback_bars: value })],
            ["底仓数量", draft.initial_position, (value) => setDraft({ ...draft, initial_position: value })],
            ["样本外窗口", draft.walk_forward_windows, (value) => setDraft({ ...draft, walk_forward_windows: value })],
            ["执行回测天数", draft.low_buy_lookback_days, (value) => setDraft({ ...draft, low_buy_lookback_days: value })],
            ["执行样本上限", draft.low_buy_limit, (value) => setDraft({ ...draft, low_buy_limit: value })],
          ]}
        />
        <label className="select-field">
          <span>低吸策略</span>
          <select value={draft.low_buy_strategy} onChange={(event) => setDraft({ ...draft, low_buy_strategy: event.target.value })}>
            {ALL_PLAYBOOK_TABS.map((tab) => <option value={tab.key} key={tab.key}>{tab.label}</option>)}
          </select>
        </label>
        <label className="select-field">
          <span>分钟周期</span>
          <select value={draft.bar_period} onChange={(event) => setDraft({ ...draft, bar_period: event.target.value as BacktestDraft["bar_period"] })}>
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
          </select>
        </label>
        <button className="primary full" onClick={onRun} disabled={loading === "backtest"}>运行回测</button>
        <button className="secondary full" onClick={onValidate} disabled={loading === "strategy-validation"}>验证策略组</button>
      </aside>
      <aside className="panel dark research-samples">
        <PanelTitle title="复盘样本 / 生命周期" />
        {replays.slice(0, 6).map((item) => (
          <div className="sample" key={item.id}>{item.symbol} · {item.outcome} · {formatPct(item.pnl_pct)}</div>
        ))}
        {lifecycleItems.slice(0, 5).map((item) => (
          <div className="sample" key={`${item.strategy_key}-${item.symbol}-${item.signal_trade_date}`}>
            {item.symbol} · {lifecycleStatusText(item.status)} · {strategyLabel(item.strategy_key)} · {formatPrice(item.entry_plan_low)}-{formatPrice(item.entry_plan_high)}
          </div>
        ))}
        {runs.slice(0, 5).map((item) => (
          <div className="sample" key={`run-${item.id}`}>
            回测 #{item.id} · {String(item.params?.symbol ?? item.name ?? "--")} · {shortTime(item.created_at)}
          </div>
        ))}
        {!replays.length ? <EmptyState text="暂无复盘样本。" /> : null}
      </aside>
      <div className="panel report research-report">
        <PanelTitle title={result ? `${result.symbol} 回测结果` : "回测结果"} />
        <p className="hint">分钟回测用于做T稳定性；真实执行回测用于低吸策略，不再用未来最高价触达目标替代胜率。</p>
        <MetricGrid
          items={[
            { label: "总交易", value: String(result?.total_trades ?? "--"), tone: "neutral" },
            { label: "胜率", value: formatPct(result?.win_rate), tone: "up" },
            { label: "平均收益", value: formatPct(result?.avg_pnl_pct), tone: toneFromChange(result?.avg_pnl_pct) },
            { label: "盈亏比", value: formatNumber(result?.profit_factor), tone: "neutral" },
            { label: "真实成交", value: executionBacktest ? `${executionBacktest.filled_signals}/${executionBacktest.evaluated_signals}` : "--", tone: "neutral" },
            { label: "净胜优势", value: formatPct(executionBacktest?.net_win_rate), tone: toneFromChange(executionBacktest?.net_win_rate) },
            { label: "净收益", value: formatPct(executionBacktest?.avg_net_return_pct), tone: toneFromChange(executionBacktest?.avg_net_return_pct) },
            { label: "止损率", value: formatPct(executionBacktest?.stop_loss_rate), tone: "down" },
            { label: "PBO", value: executionBacktest?.pbo ? formatNumber(executionBacktest.pbo.pbo) : "--", tone: (executionBacktest?.pbo?.pbo ?? 0) >= 0.9 ? "up" : "warn" },
            { label: "极端冲击", value: formatPct(executionBacktest?.crisis_scenario?.impact_pct), tone: "down" },
          ]}
        />
        <div className="stock-list compact">
          {strategyValidation ? (
            <div className="trade-card">
              {strategyValidation.summary} · 样本 {strategyValidation.total_filled_signals} · 窗口 {strategyValidation.lookback_days} 天
            </div>
          ) : null}
          {(strategyValidation?.items ?? []).slice(0, 5).map((item) => (
            <div className="trade-card" key={`validation-${item.strategy_key}`}>
              {strategyLabel(item.strategy_key)} · 成交 {item.filled_signals}/{item.evaluated_signals} · 净胜 {formatPct(item.net_win_rate_pct)} · 样本外 {formatPct(item.out_sample_return_pct)} · PBO {item.pbo_risk}
            </div>
          ))}
          {runs.slice(0, 6).map((item) => (
            <div className="trade-card" key={`backtest-run-${item.id}`}>
              历史回测 #{item.id} · {String(item.params?.symbol ?? item.name ?? "--")} · 胜率 {formatPct(numberFromResult(item.result, "win_rate"))} · 均收 {formatPct(numberFromResult(item.result, "avg_pnl_pct"))} · {shortTime(item.created_at)}
            </div>
          ))}
          {(executionBacktest?.items ?? []).slice(0, 5).map((item) => (
            <div className="trade-card" key={`${item.strategy_key}-${item.symbol}-${item.signal_trade_date}`}>
              {item.symbol} · {executionStatusText(item.status)} · {item.signal_trade_date} · 净收益 {formatPct(item.net_return_pct)} · {item.exit_reason || "等待退出"}
            </div>
          ))}
          {(result?.trades ?? []).slice(0, 8).map((trade, index) => (
            <div className="trade-card" key={`${trade.timestamp}-${index}`}>
              {trade.timestamp} · {actionText(trade.action)} · {formatPct(trade.pnl_pct)} · 分数 {formatNumber(trade.signal_score)}
            </div>
          ))}
          {!result ? <EmptyState text="运行一次回测后会展示交易明细。" /> : null}
        </div>
      </div>
    </section>
  );
}

function numberFromResult(result: Record<string, unknown>, key: string): number | undefined {
  const value = result[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
