import { useEffect, useId, useRef, useState } from "react";
import type { BacktestRunSummary } from "../../api/backtests";
import { strategiesApi, type StrategySignalReplayItem } from "../../api/strategies";
import { EmptyPlaceholder, ErrorBanner, SkeletonBlock } from "../../components/shared/Feedback";
import { DateField, NumberField, SearchField, SelectField, TextField } from "../../components/shared/FormFields";
import { useToast } from "../../components/shared/ToastContainer";
import type { AuthUser } from "../../types";
import {
  formatBacktestStrategies,
  formatDateTime,
  formatMoney,
  formatPct,
} from "../backtest/backtestDisplay";
import { BacktestResearchPanel, type BacktestResearchSection } from "../backtest/BacktestResearchPanel";
import { useBacktestDashboard, type BacktestDashboardActiveSection } from "../backtest/useBacktestDashboard";
import { useBacktestStrategyOptions } from "../backtest/useBacktestStrategyOptions";
import { useStrategyHub, type StrategyHubTab } from "./useStrategyHub";

const TABS: Array<{ key: StrategyHubTab; label: string; hint: string }> = [
  { key: "quick", label: "快速回测", hint: "先看策略能不能用" },
  { key: "signals", label: "信号复盘", hint: "查每只票为什么入选" },
  { key: "optimize", label: "参数优化", hint: "找更稳的参数" },
  { key: "validate", label: "样本外验证", hint: "防止只适合历史" },
  { key: "compare", label: "结果对比", hint: "选出最终方案" },
  { key: "capacity", label: "ML / 容量", hint: "看在线学习和资金承载" },
  { key: "history", label: "任务历史", hint: "看进度和结果" },
];

export function StrategyHubPage({ currentUser }: { currentUser: AuthUser }) {
  const hub = useStrategyHub();
  const dashboard = useBacktestDashboard(dashboardSectionForTab(hub.tab));
  const toast = useToast();

  function submitWithToast() {
    void hub.submit().then((ok) => {
      if (ok) {
        toast.pushToast({ tone: "success", title: "回测任务已提交", description: "可在右侧任务列表查看进度。" });
      }
    });
  }

  function quickSubmitWithToast() {
    void hub.submitQuickBacktest().then((ok) => {
      if (ok) {
        toast.pushToast({
          tone: "success",
          title: "一键回测已提交",
          description: "已进入策略历史，可在任务列表查看进度。",
        });
      }
    });
  }

  return (
    <section className="strategy-hub">
      <header className="panel strategy-hero">
        <div>
          <span className="strategy-kicker">Strategy Workbench · Phase 3</span>
          <h1>策略工作台</h1>
          <p>按“先体检、再复盘、再优化、最后验证”的顺序使用。普通用户先点一键快速回测，完成后只看收益、胜率、最大回撤和失败原因。</p>
        </div>
        <div className="strategy-hero-actions">
          <button type="button" onClick={() => void hub.load()} disabled={hub.loading === "load"}>
            {hub.loading === "load" ? "刷新中" : "刷新"}
          </button>
          <button type="button" className="primary" onClick={() => hub.setConfirmOpen(true)} disabled={hub.loading === "submit"}>
            提交快速回测
          </button>
        </div>
      </header>

      {hub.error ? <ErrorBanner message={`策略工作台加载失败：${hub.error}`} /> : null}
      {hub.notice ? <div className="panel strategy-notice">{hub.notice}</div> : null}

      <nav className="strategy-tabs" aria-label="策略工作台功能">
        {visibleTabsForUser(currentUser).map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={hub.tab === tab.key ? "active" : ""}
            onClick={() => hub.setTab(tab.key)}
          >
            <strong>{tab.label}</strong>
            <span>{tab.hint}</span>
          </button>
        ))}
      </nav>

      {hub.tab === "quick" ? (
        <div className="strategy-layout">
          <section className="panel strategy-form-panel">
            <PanelTitle title="快速回测配置" />
            <StrategyQuickGuide />
            <QuickBacktestForm hub={hub} onQuickSubmit={quickSubmitWithToast} />
          </section>
          <aside className="strategy-side">
            <section className="panel strategy-presets">
              <PanelTitle title="预设方案" />
              <div className="strategy-preset-list">
                {hub.presets.map((preset) => (
                  <button type="button" key={preset.key ?? preset.id ?? preset.name} onClick={() => hub.applyPreset(preset)}>
                    <strong>{preset.name}</strong>
                    <span>{preset.description}</span>
                  </button>
                ))}
                {!hub.presets.length && hub.loading === "load" ? <SkeletonBlock rows={3} title /> : null}
                {!hub.presets.length && hub.loading !== "load" ? <EmptyPlaceholder title="暂无预设" description="后端未返回预设配置。" /> : null}
              </div>
            </section>
            <section className="panel strategy-run-panel">
              <PanelTitle title="最近任务" />
              <RecentRuns runs={hub.runs} />
            </section>
          </aside>
        </div>
      ) : (
        hub.tab === "history" ? (
          <StrategyHistoryPanel runs={hub.runs} onRefresh={() => void hub.load()} />
        ) : (
          <StrategyBridge tab={hub.tab} currentUser={currentUser} dashboard={dashboard} />
        )
      )}

      {hub.confirmOpen ? (
        <ConfirmDialog
          loading={hub.loading === "submit"}
          title="确认提交快速回测"
          description={[
            `策略：${hub.selectedStrategyNames.join("、") || "未选择"}`,
            `区间：${hub.form.start_date} 至 ${hub.form.end_date}`,
            `资金：${formatMoney(Number(hub.form.initial_capital) || 0)}，成交模型：${executionModelText(hub.form.execution_model)}`,
            "任务异步执行，预计 2-5 分钟，可在策略历史查看进度。",
          ].join("；")}
          onCancel={() => hub.setConfirmOpen(false)}
          onConfirm={submitWithToast}
        />
      ) : null}
    </section>
  );
}

function QuickBacktestForm({
  hub,
  onQuickSubmit,
}: {
  hub: ReturnType<typeof useStrategyHub>;
  onQuickSubmit: () => void;
}) {
  return (
    <div className="strategy-form">
      <div className="strategy-one-click">
        <div>
          <strong>一键快速回测（最近 6 个月）</strong>
          <span>50 万初始资金 · 开盘价成交 · 当前生产策略集合</span>
        </div>
        <button type="button" className="primary" onClick={onQuickSubmit} disabled={hub.loading === "quick-submit"}>
          {hub.loading === "quick-submit" ? "提交中" : "立即提交"}
        </button>
      </div>
      <TextField label="任务名称" value={hub.form.name} onChange={(event) => hub.updateForm({ name: event.target.value })} />
      <DateField label="开始日期" value={hub.form.start_date} onChange={(event) => hub.updateForm({ start_date: event.target.value })} />
      <DateField label="结束日期" value={hub.form.end_date} onChange={(event) => hub.updateForm({ end_date: event.target.value })} />
      <NumberField label="初始资金" value={hub.form.initial_capital} onChange={(event) => hub.updateForm({ initial_capital: event.target.value })} />
      <SelectField
        label="成交模型"
        value={hub.form.execution_model}
        onChange={(event) => hub.updateForm({ execution_model: event.target.value as typeof hub.form.execution_model })}
        options={[
          { value: "open_price", label: "开盘价成交" },
          { value: "vwap", label: "VWAP 近似" },
          { value: "next_open", label: "次日开盘" },
          { value: "close_price", label: "收盘价成交" },
        ]}
      />
      <details className="strategy-advanced-fields">
        <summary>高级设置（使用推荐值即可）</summary>
        <div className="strategy-advanced-grid">
          <NumberField label="单票仓位上限" suffix="%" value={hub.form.max_position_pct} onChange={(event) => hub.updateForm({ max_position_pct: event.target.value })} />
          <NumberField label="最大持仓数" value={hub.form.max_positions} onChange={(event) => hub.updateForm({ max_positions: event.target.value })} />
          <TextField label="基准指数" value={hub.form.benchmark} onChange={(event) => hub.updateForm({ benchmark: event.target.value })} />
          <NumberField label="单笔下单上限" suffix="%" value={hub.form.max_single_order_pct} onChange={(event) => hub.updateForm({ max_single_order_pct: event.target.value })} />
          <NumberField label="单日最大亏损" suffix="%" value={hub.form.max_daily_loss_pct} onChange={(event) => hub.updateForm({ max_daily_loss_pct: event.target.value })} />
          <NumberField label="最低现金保留" value={hub.form.min_cash_reserve} onChange={(event) => hub.updateForm({ min_cash_reserve: event.target.value })} />
        </div>
      </details>
      <div className="strategy-picker">
        <div className="strategy-picker-head">
          <strong>策略选择</strong>
          <span>{hub.selectedStrategies.length} 个已选</span>
        </div>
        <div className="strategy-card-grid">
          {hub.strategies.map((strategy) => {
            const selected = hub.form.strategies.includes(strategy.key);
            return (
              <button
                type="button"
                key={strategy.key}
                className={selected ? "selected" : ""}
                onClick={() => hub.toggleStrategy(strategy.key)}
              >
                <strong>{strategy.display_name || strategy.name}</strong>
                <span>
                  {strategy.display_category || strategy.category} · {strategy.typical_holding_days}
                  {strategy.visibility === "backtest_only" ? " · 仅回测研究" : ""}
                </span>
                <small>{strategy.description}</small>
              </button>
            );
          })}
          {!hub.strategies.length && hub.loading === "load" ? <SkeletonBlock rows={5} title /> : null}
        </div>
      </div>
    </div>
  );
}

function StrategyQuickGuide() {
  return (
    <div className="strategy-guide-grid" aria-label="策略工作台使用步骤">
      <article>
        <b>1. 先点一键回测</b>
        <span>用最近 6 个月快速判断生产策略是否还有正期望。</span>
      </article>
      <article>
        <b>2. 看三项结果</b>
        <span>收益、胜率、最大回撤。运行中任务完成后才会显示。</span>
      </article>
      <article>
        <b>3. 再做优化验证</b>
        <span>只有结果可用时，再进入参数优化和样本外验证。</span>
      </article>
    </div>
  );
}

function RecentRuns({ runs }: { runs: BacktestRunSummary[] }) {
  if (!runs.length) {
    return <EmptyPlaceholder title="暂无回测任务" description="提交快速回测后会显示最近任务。" />;
  }
  return (
    <div className="strategy-run-list">
      {runs.map((run) => (
        <article key={run.id}>
          <div>
            <strong>{run.name}</strong>
            <span>{formatBacktestStrategies(run.strategies)}</span>
          </div>
          <div>
            <b className={`strategy-status ${run.status}`}>{statusText(run.status)}</b>
            <small>{formatDateTime(run.created_at)}</small>
          </div>
          <div className="strategy-run-metrics">
            <span>收益 {runMetricPct(run, "total_return_pct")}</span>
            <span>胜率 {runMetricPct(run, "win_rate_pct")}</span>
            <span>资产 {runEquityText(run)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function StrategyHistoryPanel({ runs, onRefresh }: { runs: BacktestRunSummary[]; onRefresh: () => void }) {
  const summary = summarizeRuns(runs);
  return (
    <section className="panel strategy-history">
      <div className="strategy-panel-title">
        <div>
          <h2>策略历史</h2>
          <span>集中追踪最近回测、验证和策略任务，避免在多个页面来回查找。</span>
        </div>
        <button type="button" onClick={onRefresh}>刷新历史</button>
      </div>
      <div className="strategy-history-summary">
        <article>
          <span>最近任务</span>
          <strong>{runs.length}</strong>
        </article>
        <article>
          <span>完成任务</span>
          <strong>{summary.completed}</strong>
        </article>
        <article>
          <span>平均收益</span>
          <strong>{formatPct(summary.avgReturnPct)}</strong>
        </article>
        <article>
          <span>平均胜率</span>
          <strong>{formatPct(summary.avgWinRatePct)}</strong>
        </article>
      </div>
      {runs.length ? (
        <div className="strategy-history-table" role="table" aria-label="策略历史任务">
          <div className="strategy-history-row head" role="row">
            <span>任务</span>
            <span>策略</span>
            <span>状态</span>
            <span>收益</span>
            <span>胜率</span>
            <span>创建时间</span>
          </div>
          {runs.map((run) => (
            <article className="strategy-history-row" role="row" key={run.id}>
              <strong>{run.name || `任务 #${run.id}`}</strong>
              <span>{formatBacktestStrategies(run.strategies)}</span>
              <b className={`strategy-status ${run.status}`}>{statusText(run.status)}</b>
              <span>{runMetricPct(run, "total_return_pct")}</span>
              <span>{runMetricPct(run, "win_rate_pct")}</span>
              <span>{formatDateTime(run.created_at)}</span>
            </article>
          ))}
        </div>
      ) : (
        <EmptyPlaceholder title="暂无策略历史" description="提交快速回测后会自动出现在这里。" />
      )}
    </section>
  );
}

function StrategyBridge({
  tab,
  currentUser,
  dashboard,
}: {
  tab: Exclude<StrategyHubTab, "quick" | "history">;
  currentUser: AuthUser;
  dashboard: ReturnType<typeof useBacktestDashboard>;
}) {
  const metaMap: Record<Exclude<StrategyHubTab, "quick" | "history">, [string, string]> = {
    signals: ["信号复盘", "输入代码或选择策略，查看最近哪些票入选、为什么入选、买点和止损是否清楚。"],
    optimize: ["参数优化", "快速回测有价值后再用。它会找更稳的评分、仓位、止损和持有天数。"],
    validate: ["样本外验证", "检查策略是不是只在历史里好看。样本外不通过，就不要上生产。"],
    compare: ["结果对比", "把多个已完成回测放在一起，看收益、回撤、Sharpe，选择最终方案。"],
    capacity: ["ML 在线学习 / 容量", "查看模拟盘平仓样本是否进入训练池，并评估策略在不同资金规模下是否还能承载。"],
  };
  const meta = metaMap[tab];
  if (tab === "signals") {
    return <StrategySignalReplayPanel title={meta[0]} />;
  }
  if (tab === "optimize" && !canOptimize(currentUser)) {
    return <PermissionPanel title="需要参数优化权限" description="当前账号可以查看回测和信号复盘，但不能创建参数优化任务。" />;
  }
  if (tab === "validate" && !canValidate(currentUser)) {
    return <PermissionPanel title="需要研究员权限" description="当前账号可以查看回测和信号复盘，但不能创建样本外验证任务。" />;
  }
  if (tab === "capacity" && !isAdmin(currentUser)) {
    return <PermissionPanel title="需要管理员权限" description="ML 在线学习、手动增量训练和容量评估会读取训练样本与模型状态，仅管理员可操作。" />;
  }
  const sectionMap: Record<Exclude<StrategyHubTab, "quick" | "history" | "signals">, BacktestResearchSection> = {
    optimize: "optimization",
    validate: "validation",
    compare: "compare",
    capacity: "capacity",
  };
  return (
    <div className="strategy-bridge">
      <section className="panel strategy-bridge-header">
        <h2>{meta[0]}</h2>
        <p>{meta[1]}</p>
      </section>
      <StrategyResearchFocus section={sectionMap[tab]} dashboard={dashboard} />
    </div>
  );
}

function StrategySignalReplayPanel({ title }: { title: string }) {
  const [symbol, setSymbol] = useState("");
  const [strategy, setStrategy] = useState("first_board");
  const [items, setItems] = useState<StrategySignalReplayItem[]>([]);
  const [lookbackDays, setLookbackDays] = useState("60");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requestSeqRef = useRef(0);
  const strategyOptions = useBacktestStrategyOptions();

  function loadReplay(nextSymbol: string, nextLimit: number) {
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError("");
    void strategiesApi.listSignalReplay(strategy, nextSymbol, nextLimit, Number(lookbackDays) || 60)
      .then((result) => {
        if (requestSeqRef.current === requestSeq) setItems(result.items ?? []);
      })
      .catch((err) => {
        if (requestSeqRef.current === requestSeq) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (requestSeqRef.current === requestSeq) setLoading(false);
      });
  }

  useEffect(() => {
    loadReplay("", 12);
    return () => {
      requestSeqRef.current += 1;
    };
  }, [strategy, lookbackDays]);
  const runReplayQuery = () => {
    loadReplay(symbol, 24);
  };
  return (
    <section className="panel strategy-signals-panel">
      <div className="strategy-panel-title">
        <div>
          <h2>{title}</h2>
          <span>先选策略，再按股票代码查询。这里只看历史信号，不会提交新回测。</span>
        </div>
      </div>
      <div className="strategy-signal-grid">
        <SearchField label="标的搜索" value={symbol} placeholder="输入代码或名称" onChange={setSymbol} />
        <SelectField
          label="策略"
          value={strategy}
          onChange={(event) => setStrategy(event.target.value)}
          options={strategyOptions.map(([value, label]) => ({ value, label }))}
        />
        <NumberField
          label="交易日窗口"
          suffix="个交易日"
          value={lookbackDays}
          min={1}
          max={120}
          onChange={(event) => setLookbackDays(event.target.value)}
        />
        <button type="button" className="primary" onClick={runReplayQuery} disabled={loading}>
          {loading ? "查询中" : "查询信号"}
        </button>
      </div>
      {error ? <ErrorBanner message={`信号复盘查询失败：${error}`} /> : null}
      <SignalReplayRows items={items} symbol={symbol} strategy={strategy} loading={loading} lookbackDays={Number(lookbackDays) || 60} />
    </section>
  );
}

function SignalReplayRows({
  items,
  symbol,
  strategy,
  loading,
  lookbackDays,
}: {
  items: StrategySignalReplayItem[];
  symbol: string;
  strategy: string;
  loading: boolean;
  lookbackDays: number;
}) {
  if (loading) {
    return <SkeletonBlock rows={4} title />;
  }
  if (!items.length) {
    return (
      <EmptyPlaceholder
        title="暂无信号复盘"
        description={symbol ? `${symbol} 在 ${strategy} 最近 ${lookbackDays} 个交易日内无信号记录，可扩大窗口或切换策略。` : `该策略最近 ${lookbackDays} 个交易日内无信号记录，可扩大窗口或切换策略。`}
      />
    );
  }
  return (
    <div className="strategy-signal-table" role="table" aria-label="策略信号复盘">
      <div className="strategy-signal-row head" role="row">
        <span>日期</span>
        <span>标的</span>
        <span>状态</span>
        <span>评分</span>
        <span>买点/止损</span>
        <span>摘要</span>
      </div>
      {items.map((item) => (
        <article className="strategy-signal-row" role="row" key={`${item.latest_trade_date}-${item.strategy_key}-${item.symbol}`}>
          <span>{item.latest_trade_date}</span>
          <strong>{item.name || item.symbol}<small>{item.symbol}</small></strong>
          <span>{item.buy_signal_text || item.buy_signal_state}</span>
          <b>{Number(item.score || 0).toFixed(1)}</b>
          <span>{item.entry_zone || "--"} / {typeof item.stop_loss === "number" ? item.stop_loss.toFixed(3) : "--"}</span>
          <span>{item.summary || item.reasons?.[0] || "已读取物化信号"}</span>
        </article>
      ))}
    </div>
  );
}

function StrategyResearchFocus({
  section,
  dashboard,
}: {
  section: BacktestResearchSection;
  dashboard: ReturnType<typeof useBacktestDashboard>;
}) {
  return (
    <BacktestResearchPanel
      state={dashboard.research}
      actions={dashboard.researchActions}
      sections={[section]}
    />
  );
}

function ConfirmDialog({
  loading,
  title,
  description,
  onCancel,
  onConfirm,
}: {
  loading: boolean;
  title: string;
  description: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const titleId = useId();
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    cancelRef.current?.focus();
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab") return;
      const targets = [cancelRef.current, confirmRef.current].filter(Boolean) as HTMLButtonElement[];
      if (!targets.length) return;
      const currentIndex = targets.indexOf(document.activeElement as HTMLButtonElement);
      const nextIndex = event.shiftKey
        ? (currentIndex <= 0 ? targets.length - 1 : currentIndex - 1)
        : (currentIndex >= targets.length - 1 ? 0 : currentIndex + 1);
      event.preventDefault();
      targets[nextIndex]?.focus();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);
  return (
    <div className="strategy-dialog-backdrop" role="presentation">
      <section className="strategy-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <h2 id={titleId}>{title}</h2>
        <p>{description}</p>
        <div className="strategy-dialog-actions">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={loading}>取消</button>
          <button ref={confirmRef} type="button" className="primary" onClick={onConfirm} disabled={loading}>
            {loading ? "提交中" : "确认提交"}
          </button>
        </div>
      </section>
    </div>
  );
}

function PermissionPanel({ title, description }: { title: string; description: string }) {
  return (
    <section className="panel strategy-access-panel">
      <h2>{title}</h2>
      <p>{description}</p>
    </section>
  );
}

function userRoles(user: AuthUser): Set<string> {
  return new Set((user.roles ?? []).map((role) => role.trim().toLowerCase()).filter(Boolean));
}

function isAdmin(user: AuthUser): boolean {
  const roles = userRoles(user);
  return roles.has("admin") || roles.has("administrator");
}

function canOptimize(user: AuthUser): boolean {
  return isAdmin(user) || userRoles(user).has("backtest_optimizer");
}

function canValidate(user: AuthUser): boolean {
  const roles = userRoles(user);
  return isAdmin(user) || roles.has("backtest_optimizer") || roles.has("backtest_research");
}

function visibleTabsForUser(user: AuthUser) {
  return TABS.filter((tab) => tab.key !== "capacity" || isAdmin(user));
}

function PanelTitle({ title }: { title: string }) {
  return (
    <div className="strategy-panel-title">
      <h2>{title}</h2>
    </div>
  );
}

function dashboardSectionForTab(tab: StrategyHubTab): BacktestDashboardActiveSection {
  if (tab === "quick") return "quick";
  if (tab === "history") return "history";
  if (tab === "optimize") return "optimization";
  if (tab === "validate") return "validation";
  if (tab === "compare") return "compare";
  if (tab === "capacity") return "none";
  return "none";
}

function executionModelText(value: string): string {
  if (value === "vwap") return "VWAP 近似";
  if (value === "next_open") return "次日开盘";
  if (value === "close_price") return "收盘价成交";
  return "开盘价成交";
}

function statusText(status: string): string {
  if (status === "running") return "运行中";
  if (status === "queued" || status === "pending") return "排队";
  if (status === "completed" || status === "succeeded") return "完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "取消";
  return status || "--";
}

function summarizeRuns(runs: BacktestRunSummary[]) {
  const completedRuns = runs.filter((run) => run.status === "completed" || run.status === "succeeded");
  const avgReturnPct = average(completedRuns.map((run) => run.summary?.total_return_pct));
  const avgWinRatePct = average(completedRuns.map((run) => run.summary?.win_rate_pct));
  return {
    completed: completedRuns.length,
    avgReturnPct,
    avgWinRatePct,
  };
}

function runMetricPct(run: BacktestRunSummary, key: "total_return_pct" | "win_rate_pct"): string {
  const value = run.summary?.[key];
  if (typeof value === "number" && Number.isFinite(value)) return formatPct(value);
  if (run.status === "running" || run.status === "queued" || run.status === "pending") return "完成后显示";
  if (run.status === "failed") return "失败";
  return "暂无结果";
}

function runEquityText(run: BacktestRunSummary): string {
  if (typeof run.final_equity === "number" && Number.isFinite(run.final_equity) && run.final_equity > 0) {
    return formatMoney(run.final_equity);
  }
  if (run.status === "running" || run.status === "queued" || run.status === "pending") return "计算中";
  return "--";
}

function average(values: Array<number | null | undefined>): number | undefined {
  const filtered = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!filtered.length) return undefined;
  return filtered.reduce((sum, value) => sum + value, 0) / filtered.length;
}
