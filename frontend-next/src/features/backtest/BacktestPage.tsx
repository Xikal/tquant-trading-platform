import { createQuery } from "@tanstack/solid-query";
import { createEffect, createMemo, createSignal, For, Match, Show, Switch } from "solid-js";
import { apiClient, requestOperation } from "../../shared/api/client";
import { EquitySparklineChart } from "../../shared/charts/EquitySparklineChart";
import { mutationClient } from "../../shared/api/mutations";
import { queryKeys } from "../../shared/api/queryKeys";
import type { BacktestRunDetailResponse, BacktestRunEquityResponse, BacktestRunTradesResponse } from "../../shared/api/types";
import { StatusPill } from "../../shared/ui/StatusPill";
import { ShadowActionPanel } from "../../shared/ui/ShadowActionPanel";
import { Tabs } from "../../shared/ui/Tabs";
import { pickFirst, readRecord, text } from "../shared/dataAccess";
import { backtestPayload } from "../shared/mutationPayloads";
import { PageScaffold } from "../shared/PageScaffold";
import {
  Badge,
  ChartMetric,
  ChartRangeControl,
  type ChartRange,
  ExitBadge,
  Field,
  Icon,
  InfoBox,
  MetricCompact,
  MetricTable,
  PanelHead,
  StatusDot,
  StepCard,
} from "./BacktestPrimitives";
import { dateRange, dateText, exitKind, listLength, navValue, num, pct, runStatus, sideKind, sideText } from "./backtestFormatters";
import {
  attributionRowsFromDetail,
  backtestRunId,
  backtestSubmitFields,
  detailPairs,
  equityValues,
  executionAssumptionRows,
  extractDetail,
  extractEquityPoints,
  extractRuns,
  extractTradeRows,
  logRowsFromDetail,
  oosRowsFromDetail,
  strategyOptionsFromMeta,
  researchFields,
  taskControlFields,
  type BacktestRecord,
  type BacktestStrategyOption,
} from "./backtestModel";
import "./backtest-slice.css";

type BacktestTab = "submit" | "overview" | "trades" | "etf" | "research";
type SubmitMode = "quick" | "expert";

const tabs: { key: BacktestTab; label: string }[] = [
  { key: "submit", label: "提交任务" },
  { key: "overview", label: "结果概览" },
  { key: "trades", label: "成交明细" },
  { key: "etf", label: "ETF T0" },
  { key: "research", label: "研究闭环" },
];

const marketValidationRows = [
  { state: "牛市", title: "趋势过滤测试", desc: "趋势过滤必须避免把顺势上涨误判为均值回归。", tone: "red" },
  { state: "震荡", title: "回归期望验收", desc: "重点观察 VWAP/布林回归后的期望收益和日内次数。", tone: "blue" },
  { state: "熊市", title: "亏损及止损控制", desc: "必须验证连续止损、单日亏损暂停和轻仓约束。", tone: "indigo" },
  { state: "退潮", title: "降频或禁止机制", desc: "市场宽度弱或龙头断层时应降为观察/禁止执行。", tone: "amber" },
  { state: "反弹", title: "指数联动确认", desc: "避免在急反弹里过早做反T，需跟踪指数联动确认。", tone: "green" },
];

export function BacktestPage() {
  const [selectedRunId, setSelectedRunId] = createSignal("");
  const [tab, setTab] = createSignal<BacktestTab>("submit");
  const [submitMode, setSubmitMode] = createSignal<SubmitMode>("quick");
  const [selectedStrategies, setSelectedStrategies] = createSignal<string[]>([]);
  const [chartRange, setChartRange] = createSignal<ChartRange>("6M");
  const [tradeSearch, setTradeSearch] = createSignal("");
  const [exitFilter, setExitFilter] = createSignal("ALL");
  const [tradePage, setTradePage] = createSignal(1);
  const [minuteData, setMinuteData] = createSignal("");
  const [etfRan, setEtfRan] = createSignal(false);
  const [heatmapOpen, setHeatmapOpen] = createSignal(false);

  const runsQuery = createQuery(() => ({
    queryKey: queryKeys.backtestRuns,
    queryFn: ({ signal }) => apiClient.backtestRuns(undefined, { signal }),
  }));
  const strategyMetaQuery = createQuery(() => ({
    queryKey: queryKeys.strategiesMeta,
    queryFn: ({ signal }) => apiClient.strategiesMeta({ signal }),
  }));
  const runs = createMemo(() => extractRuns(runsQuery.data));
  createEffect(() => {
    if (!selectedRunId() && runs().length) setSelectedRunId(backtestRunId(runs()[0]));
  });

  const detailQuery = createQuery(() => ({
    queryKey: queryKeys.backtestRunDetail(selectedRunId()),
    enabled: Boolean(selectedRunId()),
    queryFn: ({ signal }) => requestOperation<BacktestRunDetailResponse>("backtestRunDetail", { path: { run_id: selectedRunId() } }, { signal }),
  }));
  const equityQuery = createQuery(() => ({
    queryKey: queryKeys.backtestRunEquity(selectedRunId()),
    enabled: Boolean(selectedRunId()),
    queryFn: ({ signal }) => requestOperation<BacktestRunEquityResponse>("backtestRunEquity", { path: { run_id: selectedRunId() } }, { signal }),
  }));
  const tradesQuery = createQuery(() => ({
    queryKey: queryKeys.backtestRunTrades(selectedRunId()),
    enabled: Boolean(selectedRunId()),
    queryFn: ({ signal }) => requestOperation<BacktestRunTradesResponse>("backtestRunTrades", { path: { run_id: selectedRunId() } }, { signal }),
  }));

  const selectedRun = createMemo(() => runs().find((run) => backtestRunId(run) === selectedRunId()) ?? runs()[0] ?? {});
  const detail = createMemo(() => {
    const resolved = extractDetail(detailQuery.data);
    return Object.keys(resolved).length ? resolved : selectedRun();
  });
  const equity = createMemo(() => extractEquityPoints(equityQuery.data));
  const trades = createMemo(() => extractTradeRows(tradesQuery.data));
  const chartValues = createMemo(() => equityValues(equity()));
  const strategyOptions = createMemo(() => strategyOptionsFromMeta(strategyMetaQuery.data, runs()));
  createEffect(() => {
    if (selectedStrategies().length || !strategyOptions().length) return;
    setSelectedStrategies(strategyOptions().slice(0, 5).map((item) => item.key));
  });
  const runningCount = createMemo(() => runs().filter((run) => runStatus(run) === "running").length);
  const completedCount = createMemo(() => runs().filter((run) => runStatus(run) === "completed").length);
  const filteredTrades = createMemo(() => {
    const query = tradeSearch().trim().toLowerCase();
    return trades().filter((trade) => {
      const reason = String(pickFirst(trade, ["exit_reason", "reason", "signal"]) ?? "");
      const symbol = String(trade.symbol ?? "");
      const strategy = String(trade.strategy ?? trade.strategy_name ?? "");
      const matchesQuery = !query || symbol.toLowerCase().includes(query) || strategy.toLowerCase().includes(query) || reason.toLowerCase().includes(query);
      const normalizedExit = exitKind(reason);
      const matchesExit = exitFilter() === "ALL" || normalizedExit === exitFilter();
      return matchesQuery && matchesExit;
    });
  });
  const tradePageSize = 10;
  const totalTradePages = createMemo(() => Math.max(1, Math.ceil(filteredTrades().length / tradePageSize)));
  const pagedTrades = createMemo(() => filteredTrades().slice((tradePage() - 1) * tradePageSize, tradePage() * tradePageSize));

  createEffect(() => {
    tradeSearch();
    exitFilter();
    setTradePage(1);
  });

  function toggleStrategy(strategy: string, checked: boolean) {
    setSelectedStrategies((current) => checked ? Array.from(new Set([...current, strategy])) : current.filter((item) => item !== strategy));
  }

  function openRun(run: BacktestRecord) {
    setSelectedRunId(backtestRunId(run));
    setTab("overview");
  }

  return (
    <PageScaffold page="backtest" class="backtest-page backtest-terminal-page">
      <section class="backtest-terminal-top tq-page__full" aria-label="回测页概览">
        <div class="backtest-terminal-title">
          <span class="backtest-terminal-icon"><Icon name="trend" /></span>
          <div>
            <h1>回测页</h1>
            <p>任务: <strong>{runs().length}</strong> / 运行中: <strong>{runningCount()}</strong> / 已完成: <strong>{completedCount()}</strong> / 成交: <strong>{trades().length || "--"}</strong></p>
          </div>
        </div>
        <div class="backtest-terminal-alerts">
          <Badge tone="red">任务 ({runs().length})</Badge>
          <Badge tone="amber">异常 ({runs().filter((run) => runStatus(run) === "other").length})</Badge>
          <Badge tone="slate">更新 {text(pickFirst(selectedRun(), ["updated_at", "finished_at", "created_at"]), "--")}</Badge>
          <Badge tone="slate">{selectedRunId() || "等待任务"}</Badge>
        </div>
      </section>

      <section class="backtest-terminal-tabs tq-page__full">
        <Tabs items={tabs} value={tab()} onChange={setTab} label="回测页签" variant="segmented" />
        <div class="backtest-current-view">
          <span>当前视图: {tabs.find((item) => item.key === tab())?.label} {selectedRunId() ? `(任务 #${selectedRunId()})` : ""}</span>
          <button type="button" onClick={() => setTab(tab())}><Icon name="refresh" /> 刷新</button>
        </div>
      </section>

      <div class="backtest-terminal-body tq-page__full">
        <Switch>
          <Match when={tab() === "submit"}>
            <SubmitView
              runs={runs()}
              selectedRunId={selectedRunId()}
              strategyOptions={strategyOptions()}
              selectedStrategies={selectedStrategies()}
              submitMode={submitMode()}
              setSubmitMode={setSubmitMode}
              toggleStrategy={toggleStrategy}
              selectAllStrategies={(select) => setSelectedStrategies(select ? strategyOptions().map((item) => item.key) : [])}
              openRun={openRun}
            />
          </Match>
          <Match when={tab() === "overview"}>
            <OverviewView
              detail={detail()}
              equityCount={equity().length}
              chartValues={chartValues()}
              chartRange={chartRange()}
              setChartRange={setChartRange}
              tradesCount={trades().length}
            />
          </Match>
          <Match when={tab() === "trades"}>
            <TradesView
              trades={pagedTrades()}
              total={filteredTrades().length}
              page={tradePage()}
              totalPages={totalTradePages()}
              search={tradeSearch()}
              exitFilter={exitFilter()}
              setSearch={setTradeSearch}
              setExitFilter={setExitFilter}
              setPage={setTradePage}
            />
          </Match>
          <Match when={tab() === "etf"}>
            <EtfView
              minuteData={minuteData()}
              setMinuteData={setMinuteData}
              etfRan={etfRan()}
              setEtfRan={setEtfRan}
              heatmapOpen={heatmapOpen()}
              setHeatmapOpen={setHeatmapOpen}
            />
          </Match>
          <Match when={tab() === "research"}>
            <ResearchView selectedRunId={selectedRunId()} detail={detail()} />
          </Match>
        </Switch>
      </div>

      <footer class="backtest-terminal-footer tq-page__full">
        <span>量化引擎分析工作站 v2.5</span>
        <span><i /> 请求: {runsQuery.isFetching || detailQuery.isFetching || equityQuery.isFetching || tradesQuery.isFetching ? "同步中" : "已完成"}</span>
        <span>API 状态: {runsQuery.isError || detailQuery.isError || equityQuery.isError || tradesQuery.isError ? "部分失败" : "按响应展示"}</span>
      </footer>
    </PageScaffold>
  );
}

function SubmitView(props: {
  runs: BacktestRecord[];
  selectedRunId: string;
  strategyOptions: BacktestStrategyOption[];
  selectedStrategies: string[];
  submitMode: SubmitMode;
  setSubmitMode: (mode: SubmitMode) => void;
  toggleStrategy: (strategy: string, checked: boolean) => void;
  selectAllStrategies: (select: boolean) => void;
  openRun: (run: BacktestRecord) => void;
}) {
  const selectedStrategyLabels = () => props.selectedStrategies
    .map((key) => props.strategyOptions.find((item) => item.key === key)?.label ?? key)
    .join("、");
  const latestRun = () => props.runs[0] ?? {};
  const assumptionRows = () => executionAssumptionRows(latestRun());
  const fieldDefaults = () => ({
    strategy: props.selectedStrategies[0] ?? "",
    start: latestRun().start_date,
    end: latestRun().end_date,
    capital: latestRun().initial_cash,
    benchmark: latestRun().benchmark_symbol ?? latestRun().benchmark,
    dataVersion: latestRun().data_version,
    strategyVersion: latestRun().strategy_version,
    feeModelVersion: latestRun().fee_model_version,
  });
  return (
    <div class="backtest-submit-layout">
      <section class="backtest-card backtest-submit-card">
        <PanelHead icon="plus" title="提交回测任务" action={
          <div class="backtest-mode-switch" role="group" aria-label="提交模式">
            <button type="button" class={props.submitMode === "quick" ? "is-active" : ""} onClick={() => props.setSubmitMode("quick")}>快速模式</button>
            <button type="button" class={props.submitMode === "expert" ? "is-active" : ""} onClick={() => props.setSubmitMode("expert")}>专家模式</button>
          </div>
        } />
        <p class="backtest-muted">
          {props.submitMode === "quick" ? "只需要选择策略和日期，系统会用默认仓位、滑点和费用跑出结果。" : "专家模式允许配置手续费率、限制滑点和单标的最大持仓，用于贴近实盘的研究回测。"}
        </p>
        <div class="backtest-form-grid">
          <Field label="任务名称" value={text(latestRun().name, "等待后端任务")} wide />
          <Field label="日期范围" value={dateRange(latestRun())} />
          <Field label="初始资金 (元)" value={num(latestRun().initial_cash ?? latestRun().initial_capital)} />
          <Field label="基准指数" value={text(latestRun().benchmark_symbol ?? latestRun().benchmark, "--")} />
          <Field label="执行模型" value={text(latestRun().engine_version, "--")} />
        </div>
        <Show when={props.submitMode === "expert"}>
          <div class="backtest-expert-grid">
            <For each={assumptionRows()}>
              {(row) => <Field label={row.label} value={row.value} />}
            </For>
          </div>
        </Show>
        <div class="backtest-strategy-head">
          <span>策略多选 (勾选加入回测池)</span>
          <button type="button" onClick={() => props.selectAllStrategies(props.selectedStrategies.length !== props.strategyOptions.length)}>
            {props.selectedStrategies.length === props.strategyOptions.length ? "清空" : "全选"}
          </button>
        </div>
        <div class="backtest-strategy-grid">
          <Show when={props.strategyOptions.length} fallback={<div class="backtest-empty">暂无后端策略选项，等待 `/api/strategies/meta` 或历史回测任务返回。</div>}>
            <For each={props.strategyOptions}>
              {(strategy) => (
              <label class="backtest-strategy-tile">
                <input type="checkbox" checked={props.selectedStrategies.includes(strategy.key)} onChange={(event) => props.toggleStrategy(strategy.key, event.currentTarget.checked)} />
                <span>{strategy.label}</span>
              </label>
              )}
            </For>
          </Show>
        </div>
        <div class="backtest-readonly-note">
          <StatusPill label="策略来源" value={props.strategyOptions.length ? "后端契约" : "缺失"} tone={props.strategyOptions.length ? "info" : "warn"} />
          <span>{selectedStrategyLabels() || "未选择策略"}</span>
        </div>
        <ShadowActionPanel
          embedded
          title="回测提交"
          actionLabel="提交回测"
          resultTitle="回测状态"
          class="backtest-terminal-shadow"
          fields={backtestSubmitFields(fieldDefaults())}
          confirmText="回测参数已进入二次确认"
          onSubmit={async (draft) => {
            const result = await mutationClient.createBacktestRun(backtestPayload({ ...draft, strategies: props.selectedStrategies.join(",") }));
            return result.mode === "live" ? "提交回测已发送" : "提交回测已记录";
          }}
        />
      </section>

      <section class="backtest-card backtest-queue-card">
        <PanelHead icon="database" title="运行列表" badge={`任务执行队列 (${props.runs.length} 条)`} />
        <div class="backtest-task-queue">
          <Show when={props.runs.length} fallback={<div class="backtest-empty">暂无回测任务</div>}>
            <For each={props.runs}>
              {(run) => (
                <article class={`backtest-task-row${backtestRunId(run) === props.selectedRunId ? " is-active" : ""}`}>
                  <div>
                    <strong>{text(run.name, `Task_#${backtestRunId(run) || "--"}`)}</strong>
                    <span>策略数: {listLength(run.strategy_keys ?? run.strategies ?? run.strategy_key)} | {text(run.benchmark_symbol ?? run.benchmark, "沪深300")} | {dateRange(run)}</span>
                  </div>
                  <div>
                    <StatusDot status={runStatus(run)} />
                    <button type="button" onClick={() => props.openRun(run)}>查看分析</button>
                  </div>
                </article>
              )}
            </For>
          </Show>
        </div>
        <div class="backtest-queue-foot">
          <span><Icon name="cpu" /> 队列深度: {text(latestRun().queue_depth, "--")}</span>
          <span>预估等待: {text(latestRun().estimated_wait_seconds, "--")} 秒</span>
        </div>
      </section>
    </div>
  );
}

function OverviewView(props: { detail: BacktestRecord; equityCount: number; chartValues: number[]; chartRange: ChartRange; setChartRange: (range: ChartRange) => void; tradesCount: number }) {
  const summary = () => readRecord(props.detail.summary ?? props.detail.result);
  const totalReturn = () => pickFirst(summary(), ["total_return", "total_return_pct"]) ?? pickFirst(props.detail, ["total_return", "total_return_pct"]);
  const maxDrawdown = () => pickFirst(summary(), ["max_drawdown", "max_drawdown_pct"]) ?? pickFirst(props.detail, ["max_drawdown", "max_drawdown_pct"]);
  const winRate = () => pickFirst(summary(), ["win_rate", "win_rate_pct"]) ?? pickFirst(props.detail, ["win_rate", "win_rate_pct"]);
  const profitFactor = () => pickFirst(summary(), ["profit_factor", "pf"]) ?? pickFirst(props.detail, ["profit_factor", "pf"]);
  const pairs = () => detailPairs(props.detail).filter((item) => item.value !== "--").slice(0, 7);
  const attributionRows = () => attributionRowsFromDetail(props.detail);
  const logRows = () => logRowsFromDetail(props.detail);
  const preview = () => readRecord(props.detail.execution_model_preview);
  return (
    <div class="backtest-overview-layout">
      <section class="backtest-overview-left">
        <div class="backtest-card">
          <PanelHead title={`详情摘要 #${text(props.detail.id ?? props.detail.run_id, "--")}`} badge={text(props.detail.engine_version, "conservative_slippage")} />
          <div class="backtest-tag-cloud">
            <For each={strategyKeysForDisplay(props.detail)}>
              {(strategy) => <Badge tone="blue">{strategy}</Badge>}
            </For>
            <Show when={!strategyKeysForDisplay(props.detail).length}>
              <Badge tone="slate">暂无后端策略标签</Badge>
            </Show>
          </div>
          <div class="backtest-warning-grid">
            <InfoBox tone={Number(totalReturn()) < 0 ? "amber" : "green"} title={Number(totalReturn()) < 0 ? "不建议使用：组合收益未达标" : "研究可继续：组合收益通过初筛"} desc="当前回测结果只作为研究展示，不直接进入生产排序。" meta={`Sharpe ${text(pickFirst(summary(), ["sharpe", "sharpe_ratio"]), "--")}`} />
            <InfoBox
              tone="blue"
              title={`执行模型预览：${text(preview().status ?? preview().stage, "未返回")}`}
              desc={`事实源仍是 ${text(preview().final_fact_source, "portfolio_backtest_metrics")}；replacement_enabled=${String(Boolean(preview().replacement_enabled))}`}
              meta={text(preview().reason ?? preview().message, "Preview · 非事实源")}
            />
          </div>
          <MetricTable totalReturn={totalReturn()} maxDrawdown={maxDrawdown()} winRate={winRate()} tradesCount={props.tradesCount} profitFactor={profitFactor()} />
          <div class="backtest-detail-pairs">
            <For each={pairs()}>
              {(item) => (
                <div>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              )}
            </For>
          </div>
        </div>
        <div class="backtest-card">
          <PanelHead icon="bar" title="分组归因分析" badge="按特征自动分组" />
          <div class="backtest-attribution-list">
            <Show when={attributionRows().length} fallback={<div class="backtest-empty">后端暂未返回归因分组，当前不展示示例归因。</div>}>
              <For each={attributionRows()}>
                {(row) => (
                <div class="backtest-attribution-row">
                  <div><i class={`tone-${row.tone}`} /><span>{row.label}</span></div>
                  <div>
                    <span>信号: <strong>{row.signal}</strong></span>
                    <span>交易: <strong>{row.trades}</strong></span>
                    <strong class={(row.winRate ?? 0) >= 0.6 ? "is-up" : ""}>胜率 {row.winRate === null ? "--" : pct(row.winRate)}</strong>
                  </div>
                </div>
                )}
              </For>
            </Show>
          </div>
        </div>
      </section>
      <section class="backtest-overview-right">
        <div class="backtest-card backtest-chart-card">
          <PanelHead icon="trend" title="净值曲线" badge="双坐标系交互图" action={<ChartRangeControl value={props.chartRange} onChange={props.setChartRange} />} />
          <div class="backtest-chart-metrics">
            <ChartMetric label="策略最终净值" value={navValue(props.chartValues)} tone={Number(totalReturn()) < 0 ? "red" : "green"} />
            <ChartMetric label="基准最终净值" value="1.0000" />
            <ChartMetric label="最大回撤值" value={pct(maxDrawdown())} tone="red" />
          </div>
          <EquitySparklineChart title="回测权益曲线" values={props.chartValues} height={286} />
          <div class="backtest-chart-foot">
            <span><Icon name="info" /> 曲线点 {props.equityCount} / 图表点 {props.chartValues.length}</span>
            <span>{dateRange(props.detail)}</span>
          </div>
        </div>
        <div class="backtest-card">
          <PanelHead icon="terminal" title="执行队列状态检测 (最新4条)" badge="系统日志" />
          <div class="backtest-log-list">
            <Show when={logRows().length} fallback={<div class="backtest-empty">后端暂未返回执行日志或质量说明。</div>}>
              <For each={logRows()}>
                {(row) => (
                <div>
                  <span>{row.time}</span>
                  <strong class={`tone-${row.tone}`}>{row.level}</strong>
                  <p>{row.message}</p>
                  <em>{row.source}</em>
                </div>
                )}
              </For>
            </Show>
          </div>
        </div>
      </section>
    </div>
  );
}

function TradesView(props: {
  trades: BacktestRecord[];
  total: number;
  page: number;
  totalPages: number;
  search: string;
  exitFilter: string;
  setSearch: (value: string) => void;
  setExitFilter: (value: string) => void;
  setPage: (value: number) => void;
}) {
  return (
    <section class="backtest-card backtest-trades-card">
      <div class="backtest-trades-head">
        <div>
          <h2><Icon name="clipboard" /> 实盘成交明细</h2>
          <p>共回测过滤得到 <strong>{props.total}</strong> 笔平仓成交记录</p>
        </div>
        <div class="backtest-trade-kpis">
          <MetricCompact label="回测周期总胜率" value={tradeWinRate(props.trades)} tone={tradeWinRateTone(props.trades)} />
          <MetricCompact label="平均单笔收益" value={avgTradeReturn(props.trades)} tone={avgTradeReturnTone(props.trades)} />
          <MetricCompact label="总成交净额" value={`¥${num(sumTrades(props.trades, ["net_amount", "amount", "notional"]))}`} />
        </div>
      </div>
      <div class="backtest-trade-filters">
        <label>
          <Icon name="search" />
          <input value={props.search} placeholder="搜索代码、标的或策略特征..." onInput={(event) => props.setSearch(event.currentTarget.value)} />
        </label>
        <select value={props.exitFilter} onChange={(event) => props.setExitFilter(event.currentTarget.value)}>
          <option value="ALL">全部退出机制</option>
          <option value="take_profit">止盈 (take_profit)</option>
          <option value="stop_loss">止损 (stop_loss)</option>
          <option value="max_holding_days">最大持股天数 (max_holding)</option>
        </select>
        <span><i class="dot-up" />绿色代表正收益 <i class="dot-down" />红色代表负收益</span>
      </div>
      <div class="backtest-table-wrap">
        <table class="backtest-data-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>标的代码</th>
              <th>方向</th>
              <th class="num">数量 (股)</th>
              <th class="num">成交价</th>
              <th class="num">成交净额</th>
              <th>所属策略</th>
              <th class="num">策略收益</th>
              <th>退出原因</th>
            </tr>
          </thead>
          <tbody>
            <Show when={props.trades.length} fallback={<tr><td colspan="9" class="backtest-empty-cell">暂无符合过滤条件的交易明细。</td></tr>}>
              <For each={props.trades}>
                {(trade) => (
                  <tr>
                    <td>{dateText(pickFirst(trade, ["trade_date", "date", "created_at", "timestamp"]))}</td>
                    <td><strong>{text(trade.symbol)}</strong></td>
                    <td><span class={`side-${sideKind(trade.side ?? trade.action)}`}>{sideText(trade.side ?? trade.action)}</span></td>
                    <td class="num">{num(trade.quantity ?? trade.shares)}</td>
                    <td class="num">{num(trade.price ?? trade.fill_price)}</td>
                    <td class="num">¥{num(trade.net_amount ?? trade.amount ?? trade.notional)}</td>
                    <td><span class="backtest-table-chip">{text(trade.strategy ?? trade.strategy_name, "低吸策略")}</span></td>
                    <td class={`num ${Number(trade.return_pct ?? trade.pnl_pct ?? 0) >= 0 ? "is-up" : "is-down"}`}>{pct(trade.return_pct ?? trade.pnl_pct)}</td>
                    <td><ExitBadge value={text(trade.exit_reason ?? trade.reason ?? trade.signal)} /></td>
                  </tr>
                )}
              </For>
            </Show>
          </tbody>
        </table>
      </div>
      <div class="backtest-pagination">
        <span>显示第 {props.trades.length ? (props.page - 1) * 10 + 1 : 0} 到 {(props.page - 1) * 10 + props.trades.length} 条记录，共 {props.total} 条</span>
        <div>
          <button type="button" disabled={props.page <= 1} onClick={() => props.setPage(props.page - 1)}>上一页</button>
          <strong>{props.page} / {props.totalPages}</strong>
          <button type="button" disabled={props.page >= props.totalPages} onClick={() => props.setPage(props.page + 1)}>下一页</button>
        </div>
      </div>
    </section>
  );
}

function EtfView(props: {
  minuteData: string;
  setMinuteData: (value: string) => void;
  etfRan: boolean;
  setEtfRan: (value: boolean) => void;
  heatmapOpen: boolean;
  setHeatmapOpen: (value: boolean) => void;
}) {
  const lineCount = () => minuteLineCount(props.minuteData);
  const canRun = () => lineCount() >= 26;
  const runLabel = () => (props.etfRan ? "已接收分钟线" : "等待分钟线");
  return (
    <div class="backtest-etf-layout">
      <section class="backtest-card backtest-etf-input">
        <PanelHead icon="activity" title="ETF T0 分钟回测" badge={`${lineCount()} / 26 根分钟线`} />
        <p class="backtest-muted">研究工具：只重放传入分钟线，不写模拟盘账本。上线前继续看样本外、参数稳定性、手续费和滑点敏感性。</p>
        <div class="backtest-form-grid is-compact">
          <Field label="ETF代码" value="手工粘贴分钟线后识别" />
          <Field label="名称" value="待识别" />
          <Field label="数量" value="100000" />
          <Field label="日内次数" value="8" />
          <Field label="最少分钟线" value="26" />
        </div>
        <label class="backtest-textarea-field">
          <span>分钟线原始数据</span>
          <textarea value={props.minuteData} rows="5" placeholder="粘贴 ETF 分钟线数据。每行一条，格式如：时间,开,高,低,收,成交量..." onInput={(event) => props.setMinuteData(event.currentTarget.value)} />
        </label>
        <div class="backtest-action-row">
          <button type="button" class="primary" disabled={!canRun()} onClick={() => props.setEtfRan(canRun())}><Icon name="play" /> 运行分钟回测</button>
        </div>
      </section>
      <section class="backtest-etf-results">
        <div class="backtest-card">
          <PanelHead icon="list" title="分钟回测结果" badge={runLabel()} />
          <Show when={props.etfRan} fallback={<div class="backtest-empty large">粘贴 ETF 分钟线后运行，结果会显示费用、净收益、基线和逐笔成交。</div>}>
            <div class="backtest-etf-kpis">
              <MetricCompact label="已接收分钟线" value={`${lineCount()} 根`} tone="blue" />
              <MetricCompact label="费用(扣佣+过户)" value="待计算" />
              <MetricCompact label="T0 净收益" value="待计算" />
              <MetricCompact label="最终日内胜率" value="待计算" />
            </div>
            <div class="backtest-empty large">分钟线已接收。正式收益、滑点、费用和逐笔成交需要接入真实 ETF T0 计算结果后展示。</div>
          </Show>
        </div>
        <div class="backtest-card">
          <PanelHead icon="grid" title="日内参数稳定性热力图" badge="Parameter Heatmap" action={<button class="backtest-link-button" type="button" onClick={() => props.setHeatmapOpen(true)}>生成/重算</button>} />
          <Show when={props.heatmapOpen} fallback={<div class="backtest-empty">运行参数热力图后显示 VWAP 偏离、RSI、利润因子、回撤和基础门槛。</div>}>
            <div class="backtest-empty">暂无真实参数热力图结果。请先接入 ETF T0 计算输出，避免展示示例收益。</div>
          </Show>
          <div class="backtest-readonly-note">
            <StatusPill label="ETF T0" value="本地研究" tone="warn" />
            <StatusPill label="写入" value="不入生产" tone="warn" />
            <StatusPill label="口径" value="只读研究" />
            <span>不会进入生产排序，不影响 priority_board 或 production_score。</span>
          </div>
        </div>
      </section>
    </div>
  );
}

function minuteLineCount(value: string): number {
  return value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).length;
}

function strategyKeysForDisplay(detail: BacktestRecord): string[] {
  const raw = detail.strategy_keys ?? detail.strategies ?? detail.strategy_key;
  if (Array.isArray(raw)) return raw.map((item) => text(item, "")).filter(Boolean).slice(0, 6);
  return text(raw, "").split(/[,\n，、]/).map((item) => item.trim()).filter(Boolean).slice(0, 6);
}

function sumTrades(trades: BacktestRecord[], keys: string[]): number {
  return trades.reduce((sum, trade) => {
    const value = Number(pickFirst(trade, keys));
    return Number.isFinite(value) ? sum + value : sum;
  }, 0);
}

function tradeWinRate(trades: BacktestRecord[]): string {
  if (!trades.length) return "--";
  const wins = trades.filter((trade) => Number(trade.return_pct ?? trade.pnl_pct) > 0).length;
  return pct(wins / trades.length);
}

function tradeWinRateTone(trades: BacktestRecord[]): string {
  if (!trades.length) return "slate";
  const wins = trades.filter((trade) => Number(trade.return_pct ?? trade.pnl_pct) > 0).length;
  return wins / trades.length >= 0.5 ? "green" : "red";
}

function avgTradeReturn(trades: BacktestRecord[]): string {
  if (!trades.length) return "--";
  const values = trades.map((trade) => Number(trade.return_pct ?? trade.pnl_pct)).filter((value) => Number.isFinite(value));
  if (!values.length) return "--";
  return pct(values.reduce((sum, value) => sum + value, 0) / values.length);
}

function avgTradeReturnTone(trades: BacktestRecord[]): string {
  if (!trades.length) return "slate";
  const values = trades.map((trade) => Number(trade.return_pct ?? trade.pnl_pct)).filter((value) => Number.isFinite(value));
  if (!values.length) return "slate";
  return values.reduce((sum, value) => sum + value, 0) / values.length >= 0 ? "green" : "red";
}

function ResearchView(props: { selectedRunId: string; detail: BacktestRecord }) {
  const oosRows = () => oosRowsFromDetail(props.detail);
  const summary = () => readRecord(props.detail.summary ?? props.detail.result);
  return (
    <div class="backtest-research-layout">
      <section class="backtest-card">
        <PanelHead icon="refresh" title="Research Loop · Phase2 回测研究闭环" badge="只读验收" />
        <div class="backtest-step-grid">
          <StepCard step="STEP 1" title="优化参数" desc="分钟回测及热力图校验" active />
          <StepCard step="STEP 2" title="样本外验证" desc="2026q2-v1 真实集压测" />
          <StepCard step="STEP 3" title="多任务横评" desc="与其它版本进行归因复盘" />
          <StepCard step="STEP 4" title="准入生产" desc="只读候选通过入账" />
        </div>
        <div class="backtest-blue-note">闭环阶段优先看收益、胜率、最大回撤和样本外通过率。指标未达成时严禁直接部署。</div>
      </section>
      <div class="backtest-research-columns">
        <section class="backtest-card">
          <PanelHead icon="shield" title="五类市场验证 (自动分段)" badge="市场状态必须验收" />
          <div class="backtest-market-list">
            <For each={marketValidationRows}>
              {(row) => (
                <div>
                  <strong class={`tone-${row.tone}`}>{row.state}</strong>
                  <span>{row.title}</span>
                  <p>{row.desc}</p>
                </div>
              )}
            </For>
          </div>
        </section>
        <section class="backtest-card">
          <PanelHead icon="award" title="真实样本外验证" badge="2026q2-v1" />
          <p class="backtest-muted">样本外使用 manifest 中真实标注市场状态，不使用自动等分；结果只作为研究观察、小仓模拟、可进入生产候选的只读阶段门槛。</p>
          <div class="backtest-oos-kpis">
            <MetricCompact label="验证质量" value={text(summary().validation_quality ?? summary().verdict, oosRows().length ? "已返回窗口" : "未返回")} tone={oosRows().length ? "blue" : "amber"} />
            <MetricCompact label="状态覆盖率" value={text(summary().regime_coverage ?? summary().state_coverage, "--")} tone="blue" />
            <MetricCompact label="数据缺失率" value={pct(summary().missing_bar_ratio ?? summary().data_missing_ratio)} />
            <MetricCompact label="标的覆盖率" value={pct(summary().symbol_coverage_ratio)} />
            <MetricCompact label="最近阶段" value={text(summary().stage ?? summary().latest_stage, "--")} tone="amber" />
            <MetricCompact label="最近结论" value={text(summary().latest_verdict ?? summary().verdict, "--")} tone="amber" />
          </div>
          <table class="backtest-data-table compact">
            <thead><tr><th>状态</th><th>置信区间</th><th class="num">置信度</th><th>来源说明</th></tr></thead>
            <tbody>
              <Show when={oosRows().length} fallback={<tr><td colspan="4" class="backtest-empty-cell">后端暂未返回样本外窗口，当前不展示示例验证结果。</td></tr>}>
                <For each={oosRows()}>
                  {(row) => <tr><td class={`tone-text-${row.tone}`}>{row.state}</td><td>{row.range}</td><td class="num">{row.confidence}</td><td>{row.note}</td></tr>}
                </For>
              </Show>
            </tbody>
          </table>
        </section>
      </div>
      <div class="backtest-research-actions">
        <ShadowActionPanel
          embedded
          title="回测任务控制"
          actionLabel="取消任务"
          resultTitle="任务控制状态"
          class="backtest-terminal-shadow"
          fields={taskControlFields(props.selectedRunId)}
          confirmText="任务控制已进入二次确认"
          onSubmit={async (draft) => {
            const result = await mutationClient.cancelBacktestRun(draft.run_id || props.selectedRunId || "0", { reason: draft.reason, source: "frontend-next-shadow" });
            return result.mode === "live" ? "取消任务已发送" : "取消任务已记录";
          }}
        />
        <ShadowActionPanel
          embedded
          title="验证与优化"
          actionLabel="记录验证/优化"
          resultTitle="验证状态"
          class="backtest-terminal-shadow"
          fields={researchFields(props.selectedRunId)}
          confirmText="验证/优化已进入二次确认"
          beforeFields={
            <div class="tq-tag-row backtest-shadow-tags">
              <StatusPill label="验证" value="本地记录" tone="warn" />
              <StatusPill label="优化" value="本地记录" tone="warn" />
              <StatusPill label="对比" value="只读" />
            </div>
          }
          onSubmit={() => "验证/优化已记录，等待安全确认"}
        />
      </div>
    </div>
  );
}
