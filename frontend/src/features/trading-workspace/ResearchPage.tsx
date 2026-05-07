import type { BacktestResult, BacktestRun, LowBuyExecutionBacktestResult, LowBuyPriorityBoardResult, LowBuyTradeLifecycle, ReplayItem, StrategyValidationReport } from "../../types";
import { NumberField, SearchField, SelectField } from "../../components/shared/FormFields";
import { EmptyState, MetricGrid, PanelTitle } from "./WorkspaceComponents";
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
  strategyTabs,
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
  strategyTabs?: Array<{ key: string; label: string }>;
}) {
  const avgPnl = average(replays.map((item) => item.pnl_pct));
  const lifecycleSummary = summarizeLifecycle(lifecycleItems);
  const topFamily = priorityBoard?.family_sections?.[0];
  const strategyOptions = strategyTabs?.length ? strategyTabs : ALL_PLAYBOOK_TABS;
  return (
    <section className="page-grid research-grid">
      <div className="panel research-hero">
        <div>
          <PanelTitle title="信号复盘与样本外验证" actions={<button onClick={onRefresh} disabled={loading === "research"}>刷新复盘</button>} />
          <p className="hint">用复盘和样本外验证检查信号稳定性，核心只看胜率、赚亏比和回撤。样本少时不放大仓位。</p>
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
        <div className="compact-form-grid">
          <SearchField label="证券代码" value={draft.symbol} placeholder="输入代码或名称" onChange={(value) => setDraft({ ...draft, symbol: value })} />
          <NumberField
            label="回看天数"
            suffix="天"
            hint="用于盘中做T复盘，提交时会按分钟周期换算为K线数量。"
            value={draft.lookback_bars}
            onChange={(event) => setDraft({ ...draft, lookback_bars: event.target.value })}
          />
          <NumberField label="初始仓位" suffix="股" value={draft.initial_position} onChange={(event) => setDraft({ ...draft, initial_position: event.target.value })} />
          <NumberField label="滚动验证次数" value={draft.walk_forward_windows} onChange={(event) => setDraft({ ...draft, walk_forward_windows: event.target.value })} />
          <NumberField label="低吸复盘天数" value={draft.low_buy_lookback_days} onChange={(event) => setDraft({ ...draft, low_buy_lookback_days: event.target.value })} />
          <NumberField label="样本上限" value={draft.low_buy_limit} onChange={(event) => setDraft({ ...draft, low_buy_limit: event.target.value })} />
        </div>
        <SelectField
          label="低吸策略"
          value={draft.low_buy_strategy}
          options={strategyOptions.map((tab) => ({ value: tab.key, label: tab.label }))}
          onChange={(event) => setDraft({ ...draft, low_buy_strategy: event.target.value })}
        />
        <SelectField
          label="K线周期"
          value={draft.bar_period}
          options={[
            { value: "1m", label: "1分钟走势" },
            { value: "5m", label: "5分钟走势" },
            { value: "15m", label: "15分钟走势" },
          ]}
          onChange={(event) => setDraft({ ...draft, bar_period: event.target.value as BacktestDraft["bar_period"] })}
        />
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
            { label: "赚亏比", value: formatNumber(result?.profit_factor), tone: "neutral" },
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
