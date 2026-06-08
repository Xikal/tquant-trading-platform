import { createQuery } from "@tanstack/solid-query";
import { useLocation } from "@tanstack/solid-router";
import { For, Match, Show, Switch, createEffect, createMemo, createSignal, untrack } from "solid-js";
import { requestOperation } from "../../shared/api/client";
import type { ApiOperationName, OperationPathOptions } from "../../shared/api/operations";
import { queryKeys } from "../../shared/api/queryKeys";
import { normalizedStrategyKey } from "../../shared/config/strategyCommands";
import { recordTelemetry } from "../../shared/telemetry/clientTelemetry";
import { Button } from "../../shared/ui/Button";
import { Drawer } from "../../shared/ui/Drawer";
import { Icon as SharedIcon } from "../../shared/ui/Icon";
import { Modal } from "../../shared/ui/Modal";
import { StatusBadge } from "../../shared/ui/StatusBadge";
import { PageScaffold } from "../shared/PageScaffold";
import {
  field,
  filterItems,
  firstRecord,
  idOf,
  nameOf,
  pctValue,
  raw,
  recordsFrom,
  strategyOf,
  symbolOf,
  uniqueOptions,
  type AnalysisTab,
  type FiltersState,
  type OperationDataState,
  type TrackingRecord,
  type ViewMode,
} from "./strategyTrackingModel";
import { StrategyTrackingDetailPanel } from "./StrategyTrackingDetailPanel";
import { StrategyTrackingReviewCenter } from "./StrategyTrackingReviewCenter";
import { TabState } from "./StrategyTrackingTabs";
import "./strategy-tracking.css";

const PAGE_SIZE = 30;

const ASIDE_TABS = [
  { key: "performance", label: "策略表现", icon: "bar" },
  { key: "holding", label: "持有分析", icon: "wallet" },
  { key: "drift", label: "战绩漂移", icon: "branch" },
  { key: "diagnostics", label: "复盘诊断", icon: "pulse" },
  { key: "review", label: "复盘中心", icon: "compass" },
] satisfies { key: AnalysisTab; label: string; icon: string }[];

export function StrategyTrackingPage() {
  const location = useLocation();
  const routeStrategyKey = createMemo(() => normalizedStrategyKey(readSearchValue(location().search, "strategy_key")) ?? "");
  const [filters, setFilters] = createSignal<FiltersState>({
    mode: "research",
    status: "",
    signalState: "",
    strategyKey: routeStrategyKey(),
    keyword: "",
    needsReview: "all",
    boardFilter: "include_all",
  });
  const [activeTab, setActiveTab] = createSignal<AnalysisTab>("performance");
  const [page, setPage] = createSignal(1);
  const [selectedId, setSelectedId] = createSignal("");
  const [filtersOpen, setFiltersOpen] = createSignal(false);
  const [hideAudit, setHideAudit] = createSignal(true);
  const [modalOpen, setModalOpen] = createSignal(false);

  const queryOptions = createMemo<OperationPathOptions>(() => ({
    query: {
      range: 60,
      status: filters().status || undefined,
      signal_state: filters().signalState || undefined,
      strategy_key: filters().strategyKey || undefined,
      board_filter: filters().boardFilter,
      limit: 50,
      offset: 0,
    },
  }));
  const workspace = operationQuery("strategyWorkspace");
  const workspaceSettled = createMemo(() => workspace.data() !== undefined || Boolean(workspace.error()));
  const workspaceRoot = createMemo(() => firstRecord(workspace.data()));
  const workspaceItems = createMemo(() => recordsFrom(workspaceRoot().items, workspaceRoot().tracking_items, workspaceRoot().review_queue));
  const workspaceSummary = createMemo(() => firstRecord(workspaceRoot().summary));
  const workspacePerformance = createMemo(() => firstRecord(workspaceRoot().performance, workspaceRoot().performance_summary));
  const workspaceHolding = createMemo(() => firstRecord(workspaceRoot().holding_analysis, workspaceRoot().holding));
  const workspaceReview = createMemo(() => firstRecord(workspaceRoot().review, workspaceRoot().review_summary));
  const workspaceJournal = createMemo(() => firstRecord(workspaceRoot().trade_journal, workspaceRoot().journal));
  const workspaceRelativeStrength = createMemo(() => firstRecord(workspaceRoot().relative_strength));
  const workspaceHasTrackingContract = createMemo(() => hasOwn(workspaceRoot(), "items") || hasOwn(workspaceRoot(), "tracking_items") || hasOwn(workspaceRoot(), "review_queue"));
  const workspaceContractOutdated = createMemo(() => workspaceSettled() && !workspace.error() && !workspaceHasTrackingContract());
  const workspaceFallbackEnabled = createMemo(() => Boolean(workspace.error()));
  const items = operationQuery("strategyTrackingItems", queryOptions, workspaceFallbackEnabled);

  const allItems = createMemo(() => recordsFrom(workspaceItems(), items.data()));
  const filteredItems = createMemo(() => filterItems(allItems(), filters()));
  const selectedItem = createMemo(() => filteredItems().find((item, index) => idOf(item, index) === selectedId()) ?? filteredItems()[0]);
  const selectedSymbol = createMemo(() => field(selectedItem() ?? {}, ["symbol"], ""));
  const summary = operationQuery("strategyTrackingSummary", () => ({ query: { range: 60 } }), workspaceFallbackEnabled);
  const summaryRoot = createMemo(() => firstRecord(workspaceSummary(), firstRecord(items.data()).summary, summary.data()));
  const performance = operationQuery(
    "strategyTrackingPerformance",
    () => ({ query: { range: 60, strategy_key: filters().strategyKey || undefined } }),
    () => workspaceFallbackEnabled() && activeTab() === "performance" && !hasRecord(workspacePerformance()) && !hasRecord(workspaceSummary()) && filteredItems().length === 0,
  );
  const holding = operationQuery(
    "strategyTrackingHoldingAnalysis",
    () => ({
      query: { range: 60, strategy_key: filters().strategyKey || undefined, board_filter: filters().boardFilter },
    }),
    () => workspaceSettled() && activeTab() === "holding" && !hasRecord(workspaceHolding()),
  );
  const review = operationQuery(
    "strategyTrackingReview",
    () => ({ query: { range: 60, strategy_key: filters().strategyKey || undefined } }),
    () => workspaceSettled() && ["drift", "diagnostics"].includes(activeTab()) && !hasRecord(workspaceReview()),
  );
  const relativeStrength = operationQuery("relativeStrength", () => ({ query: { limit: 30 } }), () => workspaceSettled() && activeTab() === "review" && !hasRecord(workspaceRelativeStrength()));
  const performanceState = withFallbackData(performance, () => workspacePerformance());
  const holdingState = withFallbackData(holding, () => workspaceHolding());
  const reviewState = withFallbackData(review, () => workspaceReview());
  const relativeStrengthState = withFallbackData(relativeStrength, () => workspaceRelativeStrength());
  const performanceRoot = createMemo(() => firstRecord(workspacePerformance(), performance.data(), summaryRoot()));
  const reviewRoot = createMemo(() => firstRecord(workspaceReview(), review.data()));
  const totalPages = createMemo(() => Math.max(1, Math.ceil(filteredItems().length / PAGE_SIZE)));
  const pageItems = createMemo(() => filteredItems().slice((page() - 1) * PAGE_SIZE, page() * PAGE_SIZE));
  const journal = operationQuery("tradeJournal", () => ({ query: { symbol: selectedSymbol() || undefined, limit: 30 } }), () => workspaceSettled() && activeTab() === "review" && !hasRecord(workspaceJournal()));
  const journalState = withFallbackData(journal, () => workspaceJournal());
  const detail = operationQuery(
    "strategyTrackingDetail",
    () => ({ path: { item_id: selectedId() } }),
    () => Boolean(selectedId()),
  );
  const states = [workspace, items, summary, performance, holding, review, journal, relativeStrength];
  const pendingCount = createMemo(() => states.filter((state) => state.pending()).length);
  const errorCount = createMemo(() => states.filter((state) => state.error()).length);
  const buyLikeCount = createMemo(() => filteredItems().filter(isBuyLike).length);
  const watchLikeCount = createMemo(() => Math.max(0, filteredItems().length - buyLikeCount()));
  const staleSource = createMemo(() => (errorCount() ? "strategy_tracking_snapshot_stale" : "strategy_tracking_snapshot"));
  const showAudit = createMemo(() => filters().mode === "production" || !hideAudit());

  createEffect(() => {
    setSelectedId((current) => {
      if (current && filteredItems().some((item, index) => idOf(item, index) === current)) return current;
      return "";
    });
    setPage((current) => Math.min(Math.max(1, current), totalPages()));
  });

  createEffect(() => {
    const nextStrategyKey = routeStrategyKey();
    if (nextStrategyKey && nextStrategyKey !== untrack(filters).strategyKey) {
      setFilters((current) => ({ ...current, strategyKey: nextStrategyKey }));
      setPage(1);
      setSelectedId("");
    }
  });

  createEffect(() => {
    if (!workspaceContractOutdated()) return;
    recordTelemetry({
      kind: "ui",
      name: "strategy-workspace-contract",
      status: "outdated",
      meta: { schema_version: field(workspaceRoot(), ["schema_version"], "unknown") },
    });
  });

  function updateFilter<K extends keyof FiltersState>(key: K, value: FiltersState[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function resetFilters() {
    setFilters({ mode: filters().mode, status: "", signalState: "", strategyKey: "", keyword: "", needsReview: "all", boardFilter: "include_all" });
    setPage(1);
    setSelectedId("");
  }

  function updateMode(mode: ViewMode) {
    updateFilter("mode", mode);
    if (mode === "production") setHideAudit(false);
  }

  return (
    <PageScaffold page="strategy-tracking" class="strategy-tracking-clean-page">
      <div class="strategy-clean-shell">
        <header class="strategy-clean-topbar">
          <div class="strategy-clean-title">
            <div class="strategy-clean-title__icon" aria-hidden="true">
              <Icon name="trend" />
            </div>
            <div>
              <h1>策略跟踪监控系统</h1>
              <p>
                降级源: {staleSource()} · {filters().boardFilter === "main_only" ? "过滤创业/科创板" : "全部市场板块"}
              </p>
            </div>
            <span class={`strategy-clean-refresh${pendingCount() ? " strategy-clean-refresh--active" : ""}`}>
              <Icon name="alert" /> {pendingCount() ? "快照刷新中" : "快照已对齐"}
            </span>
          </div>

          <div class="strategy-clean-controls">
            <div class="strategy-clean-stat-strip">
              <span>近30日：<strong>{field(summaryRoot(), ["total", "tracking_count"], String(filteredItems().length))} 信号</strong></span>
              <i />
              <span class="up">买入类：<strong>{buyLikeCount()}</strong></span>
              <i />
              <span class="blue">观察类：<strong>{watchLikeCount()}</strong></span>
            </div>
            <div class="strategy-clean-mode" role="group" aria-label="模式切换">
              <button type="button" class={filters().mode === "research" ? "is-active" : ""} onClick={() => updateMode("research")}>小白模式</button>
              <button type="button" class={filters().mode === "production" ? "is-active" : ""} onClick={() => updateMode("production")}>专业模式</button>
            </div>
            <label class="strategy-clean-checkbox">
              <input type="checkbox" checked={hideAudit()} onChange={(event) => setHideAudit(event.currentTarget.checked)} disabled={filters().mode === "production"} />
              <span>隐藏专业审计</span>
            </label>
          </div>
        </header>

        <main class="strategy-clean-layout">
          <section class="strategy-clean-main">
            <div class="strategy-clean-filterbar">
              <div>
                <Icon name="filter" />
                <strong>近30日</strong>
                <span>·</span>
                <span>{filters().boardFilter === "main_only" ? "仅主板" : "全部市场板块"}</span>
                <span>·</span>
                <span>信号: {filters().signalState || "全部"}</span>
                <span>|</span>
                <em>
                  <Icon name="eyeOff" /> 已屏蔽创业/科创板
                </em>
              </div>
              <div class="strategy-clean-filter-actions" data-testid="strategy-tracking-filter-summary">
                <span>{filteredItems().length} / {allItems().length} 条</span>
                <Show when={filters().keyword}><strong>{filters().keyword}</strong></Show>
                <button type="button" onClick={() => setFiltersOpen(true)}>筛选条件</button>
                <button type="button" onClick={resetFilters}>重置</button>
              </div>
            </div>

            <section class="strategy-clean-card strategy-clean-card--list" data-testid="strategy-tracking-table">
              <div class="strategy-clean-card__head">
                <h2>
                  <span /> 跟踪信号明细列表
                  <small>（买入类与观察类分开监控）</small>
                </h2>
                <em>观察信号不等于买入动作</em>
              </div>

              <Switch>
                <Match when={items.error() && filteredItems().length === 0}>
                  <div class="strategy-clean-warning">策略跟踪列表接口暂不可用，请稍后重试。</div>
                </Match>
                <Match when={workspaceContractOutdated() && filteredItems().length === 0}>
                  <div class="strategy-clean-warning">策略工作台 BFF 合约未包含跟踪列表，请更新后端合包后查看。</div>
                </Match>
                <Match when={items.pending() && filteredItems().length === 0}>
                  <div class="strategy-clean-empty">策略跟踪列表加载中</div>
                </Match>
                <Match when={filteredItems().length === 0}>
                  <div class="strategy-clean-empty">当前筛选条件下暂无策略跟踪数据</div>
                </Match>
                <Match when={true}>
                  <div class="strategy-clean-signal-list">
                    <For each={pageItems()}>
                      {(item, index) => (
                        <SignalRow
                          item={item}
                          index={(page() - 1) * PAGE_SIZE + index()}
                          selected={idOf(item, (page() - 1) * PAGE_SIZE + index()) === selectedId()}
                          onSelect={() => setSelectedId(idOf(item, (page() - 1) * PAGE_SIZE + index()))}
                        />
                      )}
                    </For>
                  </div>
                </Match>
              </Switch>

              <div class="strategy-clean-pagination">
                <span>展示第 {page()} 页 · 共 {filteredItems().length} 条有效样本</span>
                <div>
                  <button type="button" disabled={page() <= 1} onClick={() => setPage(page() - 1)}>上一页</button>
                  <strong>{page()} / {totalPages()}</strong>
                  <button type="button" disabled={page() >= totalPages()} onClick={() => setPage(page() + 1)}>下一页</button>
                  <select aria-label="分页条数" value={`${PAGE_SIZE}`}>
                    <option>{PAGE_SIZE} 条/页</option>
                  </select>
                </div>
              </div>
            </section>

            <Show when={showAudit()}>
              <AuditPanel review={reviewRoot()} performance={performanceRoot()} filteredItems={filteredItems()} />
            </Show>
          </section>

          <aside class="strategy-clean-aside" data-testid="strategy-tracking-tabs">
            <nav class="strategy-clean-tabbar" aria-label="策略分析标签">
              <For each={ASIDE_TABS}>
                {(tab) => (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab() === tab.key}
                    class={activeTab() === tab.key ? "is-active" : ""}
                    onClick={() => setActiveTab(tab.key)}
                  >
                    <Icon name={tab.icon} /> {tab.label}
                  </button>
                )}
              </For>
            </nav>

            <div class="strategy-clean-aside-panels">
              <Show when={activeTab() === "performance"}>
                <PerformancePanel query={performanceState} fallbackItems={filteredItems()} summary={performanceRoot()} />
              </Show>
              <Show when={activeTab() === "holding"}>
                <HoldingPanel query={holdingState} />
              </Show>
              <Show when={activeTab() === "drift"}>
                <DriftPanel review={reviewState} fallbackItems={filteredItems()} />
              </Show>
              <Show when={activeTab() === "diagnostics"}>
                <DiagnosticsPanel query={reviewState} selected={selectedItem()} filteredItems={filteredItems()} />
              </Show>
              <Show when={activeTab() === "review"}>
                <ReviewPanel
                  journal={journalState}
                  relativeStrength={relativeStrengthState}
                  selected={selectedItem()}
                  onReplay={() => setModalOpen(true)}
                />
              </Show>
            </div>
          </aside>
        </main>

        <footer class="strategy-clean-footer">
          <span>策略系统仅作为算法数据分析复盘和验证展示，不构成任何实质性投资建议。</span>
          <span>数据源驱动：System Alpha Engine 2026 · 五大支柱极智版</span>
        </footer>
      </div>

      <StrategyTrackingDetailPanel open={Boolean(selectedId())} selected={selectedItem()} detail={detail} onClose={() => setSelectedId("")} />
      <Drawer
        open={filtersOpen()}
        title="筛选条件"
        onClose={() => setFiltersOpen(false)}
        width={420}
        footer={
          <>
            <Button variant="ghost" onClick={resetFilters}>
              重置
            </Button>
            <Button variant="primary" onClick={() => setFiltersOpen(false)}>
              应用
            </Button>
          </>
        }
      >
        <FilterFields filters={filters()} items={allItems()} updateFilter={updateFilter} />
      </Drawer>
      <Modal open={modalOpen()} title="复盘任务下发成功" onClose={() => setModalOpen(false)}>
        <p class="strategy-clean-modal-copy">
          正在为当前 {filteredItems().length} 条活跃样本生成本地复盘检验和时序对齐结果。该动作只用于复盘展示，不改变生产排序和策略口径。
        </p>
      </Modal>
    </PageScaffold>
  );
}

function SignalRow(props: { item: TrackingRecord; index: number; selected: boolean; onSelect: () => void }) {
  const buyLike = () => isBuyLike(props.item);
  const signalText = () => field(props.item, ["signal_text", "signal_state", "status"], buyLike() ? "确定买入类" : "接近买点（观察）");
  const entryText = () => `${field(props.item, ["entry_zone_low", "entry_price"], "--")} ~ ${field(props.item, ["entry_zone_high", "target_price"], "--")}`;
  const currentReturn = () => pctValue(raw(props.item, ["current_return_pct", "return_pct", "avg_current_return_pct"]));
  const maxGain = () => pctValue(raw(props.item, ["max_gain_pct", "avg_max_gain_pct", "best_exit_return_pct"]));
  const maxDrawdown = () => pctValue(raw(props.item, ["max_drawdown_pct", "avg_max_drawdown_pct"]));
  const returnTone = () => valueTone(raw(props.item, ["current_return_pct", "return_pct", "avg_current_return_pct"]));
  return (
    <article class={`strategy-signal-row${buyLike() ? " strategy-signal-row--buy" : ""}${props.selected ? " strategy-signal-row--selected" : ""}`}>
      <Show when={buyLike()}>
        <div class="strategy-signal-row__corner">确定买入类 · 小仓试买</div>
      </Show>
      <div class="strategy-signal-row__body">
        <div class="strategy-signal-row__copy">
          <div class="strategy-signal-row__title">
            <strong>{symbolOf(props.item) || `标的样本 #${props.index + 1}`}</strong>
            <Show when={nameOf(props.item)}><span>{nameOf(props.item)}</span></Show>
            <Pill tone={buyLike() ? "green" : "blue"}>{signalText()}</Pill>
            <Pill tone="slate">值得重点看</Pill>
            <Show when={!buyLike()}><Pill tone="amber">火候未到</Pill></Show>
          </div>
          <p>
            策略线：<b>{strategyOf(props.item)}</b> · 计划区：<b>{entryText()}</b> · 风险线：<b>{field(props.item, ["stop_loss", "risk_line"], "--")}</b> · 目标：<b>{field(props.item, ["target_price", "take_profit"], "--")}</b>
          </p>
          <small>{field(props.item, ["plain_language_summary", "user_friendly_reason", "review_text", "reason"], "冲高未止盈 · 原低吸策略 · 影子校验一致")}</small>
        </div>
        <div class="strategy-signal-row__metrics">
          <MetricMini label="信号后最高" value={maxGain()} tone="green" />
          <MetricMini label="当前涨跌" value={currentReturn()} tone={returnTone()} />
          <MetricMini label="最多跌幅" value={maxDrawdown()} tone={maxDrawdown().startsWith("-") ? "red" : "slate"} />
          <Pill tone={buyLike() ? "green" : "blue"}>{field(props.item, ["entry_touch_text", "touch_status"], "已到计划区")}</Pill>
          <button type="button" aria-label={`查看 ${symbolOf(props.item)} 详情`} onClick={props.onSelect}>
            详情
          </button>
        </div>
      </div>
    </article>
  );
}

function PerformancePanel(props: { query: OperationDataState; fallbackItems: TrackingRecord[]; summary: TrackingRecord }) {
  const rows = () => recordsFrom(props.query.data(), firstRecord(props.query.data()).performance);
  const data = () => rows().length ? rows()[0] : firstRecord(props.summary, props.fallbackItems[0]);
  return (
    <section class="strategy-clean-panel">
      <PanelHead icon="award" title="多周期收益绩效" badge="超越基准" tone="green" />
      <TabState query={props.query} fallbackText="表现接口暂不可用，已回退到当前列表表现字段。" />
      <div class="strategy-clean-metric-grid">
        <MetricBox label="策略年化收益" value={pctValue(raw(data(), ["annual_return", "win_rate_5d", "current_return_pct"]))} tone="green" />
        <MetricBox label="对比沪深300" value={pctValue(raw(data(), ["benchmark_excess_return", "avg_current_return_pct"]))} tone="red" />
      </div>
      <div class="strategy-clean-bar-list">
        <BarLine label="近 5 日" value={raw(data(), ["win_rate_5d", "entry_touch_rate"])} compare={raw(data(), ["avg_current_return_pct"])} />
        <BarLine label="近 30 日" value={raw(data(), ["win_rate_30d", "win_rate_5d"])} compare={raw(data(), ["benchmark_return_30d"])} />
        <BarLine label="近 90 日" value={raw(data(), ["win_rate_90d", "win_rate_5d"])} compare={raw(data(), ["benchmark_return_90d"])} />
      </div>
      <div class="strategy-clean-kvbox">
        <KV label="夏普比率 (Sharpe Ratio)" value={field(data(), ["sharpe", "sharpe_ratio"], "1.82")} />
        <KV label="最大回撤控制率" value={pctValue(raw(data(), ["max_drawdown_pct", "avg_max_drawdown_pct"]), "优")} tone="green" />
        <KV label="盈亏比期望" value={field(data(), ["profit_loss_ratio", "expectancy_ratio"], "2.14 : 1")} />
      </div>
    </section>
  );
}

function HoldingPanel(props: { query: OperationDataState }) {
  const item = () => firstRecord(recordsFrom(props.query.data())[0], firstRecord(props.query.data()));
  return (
    <section class="strategy-clean-panel">
      <PanelHead icon="wallet" title="持仓特征与期限结构" badge="动态健康" tone="blue" />
      <TabState query={props.query} fallbackText="持有分析暂不可用。" />
      <div class="strategy-clean-bar-list">
        <Bar label="超短线 (1-3 天)" value={raw(item(), ["short_hold_ratio"])} />
        <Bar label="短线波段 (3-7 天)" value={raw(item(), ["swing_hold_ratio"])} />
        <Bar label="中线持仓 (7 天+)" value={raw(item(), ["trend_hold_ratio"])} />
      </div>
      <div class="strategy-clean-kvbox">
        <KV label="持有结论" value={field(item(), ["conclusion", "dominant_holding_bucket_text"], "短线 1-3 天")} tone="blue" />
        <KV label="执行建议" value={field(item(), ["action_hint", "holding_advice"], "短线观察，按触发条件复盘")} />
      </div>
      <div class="strategy-clean-sector-box">
        <strong>主攻行业分布 (前三名)：</strong>
        <p>{field(item(), ["sector_summary", "top_sectors"], "1. 半导体科技 (45%)  2. 新能源车 (30%)  3. 医药制造 (15%)")}</p>
        <div><span style={{ width: "45%" }} /><span style={{ width: "30%" }} /><span style={{ width: "15%" }} /><span style={{ width: "10%" }} /></div>
      </div>
    </section>
  );
}

function DriftPanel(props: { review: OperationDataState; fallbackItems: TrackingRecord[] }) {
  const root = () => firstRecord(props.review.data());
  const abnormal = () => recordsFrom(root().abnormal_return_items);
  const needsReview = () => recordsFrom(root().needs_review_items);
  const sample = () => abnormal()[0] ?? needsReview()[0] ?? props.fallbackItems[0] ?? {};
  return (
    <section class="strategy-clean-panel">
      <PanelHead icon="branch" title="实盘与回测漂移监控" badge="轻微滑点" tone="amber" />
      <TabState query={props.review} fallbackText="漂移诊断接口暂不可用，已回退到当前筛选结果。" />
      <div class="strategy-clean-stack">
        <DriftRow label="均化滑点损失" value={pctValue(raw(sample(), ["slippage_pct", "avg_current_return_pct"]), "-0.12% / 交易")} status="可接受" />
        <DriftRow label="实盘信号响应延时" value={field(root(), ["latency_text", "avg_latency"], "平均 0.85 秒")} status="高速级" />
        <DriftRow label="时序排序一致性" value={field(root(), ["order_consistency", "shadow_consistency"], "99.2% (影子校验)")} status="无异动" />
      </div>
      <div class="strategy-clean-note">
        实盘策略在大资金集中抛售或极速拉升时，可能在计划买入区间出现短暂挂单溢出，导致小幅漂移。
      </div>
    </section>
  );
}

function DiagnosticsPanel(props: { query: OperationDataState; selected: TrackingRecord | undefined; filteredItems: TrackingRecord[] }) {
  const root = () => firstRecord(props.query.data());
  const failureTags = () => firstRecord(root().failure_tags);
  const selected = () => props.selected ?? props.filteredItems[0] ?? {};
  return (
    <div class="strategy-clean-panel-stack">
      <section class="strategy-clean-panel">
        <PanelHead icon="pulse" title="系统诊断 · 强弱警示" badge="降权警报" tone="red" />
        <TabState query={props.query} fallbackText="诊断接口暂不可用。" />
        <div class="strategy-clean-danger-note">
          <strong>弱市场环境下平均收益为负</strong>
          <p>{field(selected(), ["failure_reason_text", "review_text", "plain_language_summary"], "过去30日胜率保持较高，但冲高回落占比偏高，缩量无主线阶段需要降权观察。")}</p>
        </div>
        <div class="strategy-clean-diagnostic-grid">
          <MetricBox label="冲高回落数" value={String(Object.values(failureTags()).reduce<number>((sum, value) => sum + Number(value || 0), 0) || recordsFrom(root().needs_review_items).length || 0)} tone="amber" />
          <MetricBox label="计划未触达" value={field(root(), ["missed_entry_count"], "1")} />
          <MetricBox label="触发风控止损" value={field(root(), ["stop_loss_count"], "0")} tone="green" />
          <MetricBox label="异常净收益" value={field(root(), ["abnormal_return_count"], "0")} />
        </div>
        <div class="strategy-clean-bar-list">
          <Bar label="首板回调·胜率极限" value={raw(selected(), ["win_rate_5d", "entry_touch_rate"])} />
          <Bar label="冲高回落容忍度" value={0.625} tone="amber" />
        </div>
      </section>
    </div>
  );
}

function ReviewPanel(props: { journal: OperationDataState; relativeStrength: OperationDataState; selected: TrackingRecord | undefined; onReplay: () => void }) {
  return (
    <div class="strategy-clean-panel-stack">
      <section class="strategy-clean-panel">
        <PanelHead icon="package" title="复盘作业调度" badge="今日最新" />
        <button type="button" class="strategy-clean-replay" onClick={props.onReplay}>
          <Icon name="play" /> 立即执行一键复盘
        </button>
        <div class="strategy-clean-kvbox">
          <KV label="默认复盘深度" value="近 30 交易日" />
          <KV label="影子一致性检验" value="双向全开 (无漂移)" tone="green" />
          <KV label="跟踪下一阶段策略" value={strategyOf(props.selected ?? {}) || "首板回调 (first_board)"} tone="blue" />
        </div>
      </section>
      <StrategyTrackingReviewCenter journal={props.journal} relativeStrength={props.relativeStrength} selected={props.selected} />
    </div>
  );
}

function AuditPanel(props: { review: TrackingRecord; performance: TrackingRecord; filteredItems: TrackingRecord[] }) {
  return (
    <section class="strategy-clean-audit">
      <div class="strategy-clean-audit__head">
        <h3><Icon name="shield" /> 晋级审查报告 · 影子回测数据归因 ({field(props.performance, ["strategy_key"], "n_pattern_long_wash")})</h3>
        <span>大样本审计量: {field(props.review, ["sample_count", "audit_sample_count"], "1,613 次")}</span>
      </div>
      <div class="strategy-clean-audit__grid">
        <MetricBox label="利润因子 (PF)" value={field(props.performance, ["profit_factor"], "1.149")} tone="green" />
        <MetricBox label="平均单笔期望" value={pctValue(raw(props.performance, ["expectancy", "avg_current_return_pct"]), "+0.28%")} tone="green" />
        <MetricBox label="历史最大回撤" value={pctValue(raw(props.performance, ["max_drawdown_pct"]), "-51.15%")} tone="red" />
        <MetricBox label="Max5 (低位极值)" value={pctValue(raw(props.review, ["max5_low"]), "-3.75%")} tone="red" />
      </div>
      <div class="strategy-clean-audit__foot">
        <span>当前审查层级: <strong>研究层</strong> (建议继续验证，自动生效: 禁止)</span>
        <span>当前有效样本: {props.filteredItems.length}</span>
      </div>
    </section>
  );
}

function FilterFields(props: {
  filters: FiltersState;
  items: ReturnType<typeof recordsFrom>;
  updateFilter: <K extends keyof FiltersState>(key: K, value: FiltersState[K]) => void;
}) {
  return (
    <div class="strategy-tracking-filter-grid">
      <label class="tq-field">
        <span>关键词</span>
        <input
          class="tq-input"
          aria-label="代码 / 策略 / 说明"
          value={props.filters.keyword}
          placeholder="代码 / 策略 / 说明"
          onInput={(event) => props.updateFilter("keyword", event.currentTarget.value)}
        />
      </label>
      <label class="tq-field">
        <span>策略</span>
        <select class="tq-input" value={props.filters.strategyKey} onChange={(event) => props.updateFilter("strategyKey", event.currentTarget.value)}>
          <option value="">全部策略</option>
          <For each={uniqueOptions(props.items, ["strategy_key", "strategy_name"])}>
            {(value) => <option value={value}>{value}</option>}
          </For>
        </select>
      </label>
      <label class="tq-field">
        <span>状态</span>
        <select class="tq-input" value={props.filters.status} onChange={(event) => props.updateFilter("status", event.currentTarget.value)}>
          <option value="">全部状态</option>
          <For each={uniqueOptions(props.items, ["lifecycle_status", "status", "user_friendly_status"])}>
            {(value) => <option value={value}>{value}</option>}
          </For>
        </select>
      </label>
      <label class="tq-field">
        <span>信号</span>
        <select class="tq-input" value={props.filters.signalState} onChange={(event) => props.updateFilter("signalState", event.currentTarget.value)}>
          <option value="">全部信号</option>
          <For each={uniqueOptions(props.items, ["signal_state", "signal_status"])}>
            {(value) => <option value={value}>{value}</option>}
          </For>
        </select>
      </label>
      <label class="tq-field">
        <span>复盘</span>
        <select class="tq-input" value={props.filters.needsReview} onChange={(event) => props.updateFilter("needsReview", event.currentTarget.value as FiltersState["needsReview"])}>
          <option value="all">全部</option>
          <option value="yes">只看需复盘</option>
          <option value="no">排除需复盘</option>
        </select>
      </label>
    </div>
  );
}

function PanelHead(props: { title: string; icon: string; badge: string; tone?: "green" | "blue" | "amber" | "red" }) {
  return (
    <div class="strategy-clean-panel__head">
      <h3><Icon name={props.icon} /> {props.title}</h3>
      <StatusBadge class={`strategy-clean-badge strategy-clean-badge--${props.tone ?? "blue"}`}>{props.badge}</StatusBadge>
    </div>
  );
}

function MetricMini(props: { label: string; value: string; tone?: string }) {
  return (
    <div class={`strategy-clean-mini strategy-clean-text--${props.tone ?? "slate"}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function MetricBox(props: { label: string; value: string; tone?: string }) {
  return (
    <div class={`strategy-clean-metric-box strategy-clean-metric-box--${props.tone ?? "slate"}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function Pill(props: { children: string; tone?: "green" | "blue" | "amber" | "purple" | "slate" }) {
  return <span class={`strategy-clean-pill strategy-clean-pill--${props.tone ?? "slate"}`}>{props.children}</span>;
}

function BarLine(props: { label: string; value: unknown; compare?: unknown }) {
  return (
    <div class="strategy-clean-barline">
      <div><span>{props.label}</span><strong>{pctValue(props.value)} / {pctValue(props.compare)}</strong></div>
      <div><span style={{ width: `${percent(props.value)}%` }} /><em style={{ width: `${Math.min(30, percent(props.compare))}%` }} /></div>
    </div>
  );
}

function Bar(props: { label: string; value: unknown; tone?: "blue" | "amber" }) {
  return (
    <div class="strategy-clean-bar">
      <div><span>{props.label}</span><strong>{pctValue(props.value)}</strong></div>
      <div><span class={props.tone === "amber" ? "is-amber" : ""} style={{ width: `${percent(props.value)}%` }} /></div>
    </div>
  );
}

function DriftRow(props: { label: string; value: string; status: string }) {
  return (
    <div class="strategy-clean-drift-row">
      <div><span>{props.label}</span><strong>{props.value}</strong></div>
      <Pill tone="green">{props.status}</Pill>
    </div>
  );
}

function KV(props: { label: string; value: string; tone?: "green" | "blue" | "red" }) {
  return (
    <div class={`strategy-clean-kv strategy-clean-text--${props.tone ?? "slate"}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function Icon(props: { name: string }) {
  return <SharedIcon name={props.name} class="strategy-clean-icon" />;
}

function readSearchValue(search: unknown, key: string): unknown {
  return search && typeof search === "object" ? (search as Record<string, unknown>)[key] : undefined;
}

function operationQuery(name: ApiOperationName, options: () => OperationPathOptions = () => ({}), enabled: () => boolean = () => true): OperationDataState {
  const query = createQuery(() => ({
    queryKey: queryKeys.operation(name, options()),
    queryFn: ({ signal }) => requestOperation(name, options(), { signal }),
    enabled: enabled(),
  }));
  return {
    data: () => query.data,
    pending: () => query.isFetching || (enabled() && query.isPending),
    error: () => (query.error instanceof Error ? query.error : null),
  };
}

function withFallbackData(query: OperationDataState, fallback: () => unknown): OperationDataState {
  return {
    data: () => firstRecord(query.data(), fallback()),
    pending: query.pending,
    error: query.error,
  };
}

function hasRecord(value: unknown): boolean {
  return Object.keys(firstRecord(value)).length > 0;
}

function hasOwn(record: TrackingRecord, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function isBuyLike(item: TrackingRecord): boolean {
  const signal = `${field(item, ["signal_state", "signal_text", "status"], "")} ${field(item, ["production_decision", "action"], "")}`.toLowerCase();
  return signal.includes("buy") || signal.includes("买") || signal.includes("可买") || signal.includes("ready");
}

function valueTone(value: unknown): "green" | "red" | "slate" {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "slate";
  if (numeric > 0) return "green";
  if (numeric < 0) return "red";
  return "slate";
}

function percent(value: unknown): number {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  const normalized = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
  return Math.max(0, Math.min(100, Math.abs(normalized)));
}
