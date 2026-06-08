import { For, Show, createSignal } from "solid-js";
import { Button } from "../../shared/ui/Button";
import { MetricGrid } from "../../shared/ui/MetricGrid";
import { Panel } from "../../shared/ui/Panel";
import { StatusPill } from "../../shared/ui/StatusPill";
import { Tabs, type TabItem } from "../../shared/ui/Tabs";
import { VirtualDataTable } from "../../shared/ui/VirtualDataTable";
import { readArray, readRecord, text } from "../shared/dataAccess";
import { metricClass, metricTone, moneyText, orderColumns, pctField, riskColumns, stockPnlColumns, tradeColumns } from "./PaperWorkflowTables";

type PaperTab = "auto" | "records" | "performance" | "details" | "orders" | "trades" | "risk" | "reconcile";

const paperTabs: TabItem<PaperTab>[] = [
  { key: "auto", label: "自动化" },
  { key: "records", label: "记录" },
  { key: "performance", label: "策略绩效" },
  { key: "details", label: "详情信息" },
];

export function PaperWorkflowTabs(props: { root: Record<string, unknown>; isPending: boolean; isError: boolean }) {
  const [activeTab, setActiveTab] = createSignal<PaperTab>("auto");
  const orders = () => readArray<Record<string, unknown>>(props.root.orders);
  const trades = () => readArray<Record<string, unknown>>(props.root.trades);
  const riskEvents = () => readArray<Record<string, unknown>>(props.root.risk_events);
  const performance = () => readRecord(props.root.performance);
  const stockPnl = () => readRecord(props.root.stock_pnl);
  const stockPnlSummary = () => readRecord(stockPnl().summary);
  const autoStatus = () => readRecord(props.root.auto_trading_status);
  const autoRuns = () => readArray<Record<string, unknown>>(props.root.auto_trading_runs);
  const partialErrors = () => readArray<Record<string, unknown>>(props.root.partial_errors);

  return (
    <Panel class="paper-workflow-panel tq-page__full">
      <Tabs items={paperTabs} value={activeTab()} onChange={setActiveTab} label="模拟盘工作流 tabs" />
      <Show when={props.isError || partialErrors().length}>
        <div class="paper-api-alert" role="status">
          <strong>{props.isError ? "接口暂不可用" : "部分数据降级"}</strong>
          <span>{props.isError ? "页面核心区域保持可见。" : `${partialErrors().length} 个数据块暂不可用。`}</span>
        </div>
      </Show>
      <Show when={activeTab() === "auto"}>
        <AutoTradingTab status={autoStatus()} runs={autoRuns()} riskEvents={riskEvents()} />
      </Show>
      <Show when={activeTab() === "records"}>
        <RecordsTab orders={orders()} trades={trades()} isPending={props.isPending} />
      </Show>
      <Show when={activeTab() === "performance"}>
        <PerformanceTab performance={performance()} stockPnlSummary={stockPnlSummary()} root={props.root} />
      </Show>
      <Show when={activeTab() === "details"}>
        <DetailsTab
          orders={orders()}
          trades={trades()}
          riskEvents={riskEvents()}
          autoStatus={autoStatus()}
          stockPnl={stockPnl()}
          stockPnlSummary={stockPnlSummary()}
          partialErrors={partialErrors()}
          isPending={props.isPending}
        />
      </Show>
    </Panel>
  );
}

function OrdersTab(props: { orders: Record<string, unknown>[]; isPending: boolean }) {
  return (
    <div class="paper-tab-panel" role="tabpanel" aria-label="订单">
      <VirtualDataTable
        data={props.orders}
        columns={orderColumns}
        emptyText={props.isPending ? "正在读取订单" : "暂无订单"}
        ariaLabel="模拟盘订单列表"
        maxHeight={220}
        compact
      />
    </div>
  );
}

function TradesTab(props: { trades: Record<string, unknown>[]; isPending: boolean }) {
  return (
    <div class="paper-tab-panel" role="tabpanel" aria-label="成交">
      <VirtualDataTable
        data={props.trades}
        columns={tradeColumns}
        emptyText={props.isPending ? "正在读取成交" : "暂无成交"}
        ariaLabel="模拟盘成交列表"
        maxHeight={220}
        compact
      />
    </div>
  );
}

function RecordsTab(props: { orders: Record<string, unknown>[]; trades: Record<string, unknown>[]; isPending: boolean }) {
  return (
    <div class="paper-tab-panel paper-tab-panel--stack" role="tabpanel" aria-label="记录">
      <div class="paper-record-grid">
        <section class="paper-overview-card">
          <div class="paper-overview-card__head">
            <strong>最新订单</strong>
            <span>{props.orders.length} 单</span>
          </div>
          <OrdersTab orders={props.orders} isPending={props.isPending} />
        </section>
        <section class="paper-overview-card">
          <div class="paper-overview-card__head">
            <strong>最新成交</strong>
            <span>{props.trades.length} 笔</span>
          </div>
          <TradesTab trades={props.trades} isPending={props.isPending} />
        </section>
      </div>
    </div>
  );
}

function RiskTab(props: { riskEvents: Record<string, unknown>[]; autoStatus: Record<string, unknown>; isPending: boolean }) {
  return (
    <div class="paper-tab-panel paper-tab-panel--stack" role="tabpanel" aria-label="风险">
      <BlockedActionStrip
        title="暂停/恢复账户"
        detail="账户控制需要二次确认，当前先记录为待处理动作。"
        actions={["暂停账户", "恢复账户"]}
      />
      <MetricGrid
        items={[
          { label: "风险事件", value: props.riskEvents.length, tone: props.riskEvents.length ? "warn" : "neutral" },
          { label: "账户状态", value: text(props.autoStatus.account_status ?? props.autoStatus.status, "未知") },
          { label: "熔断", value: text(props.autoStatus.circuit_open, "否"), tone: props.autoStatus.circuit_open === true ? "warn" : "neutral" },
          { label: "交易时段", value: text(props.autoStatus.trading_time, "--") },
        ]}
      />
      <VirtualDataTable
        data={props.riskEvents}
        columns={riskColumns}
        emptyText={props.isPending ? "正在读取风险事件" : "暂无风险事件"}
        ariaLabel="模拟盘风险事件列表"
        maxHeight={220}
        compact
      />
    </div>
  );
}

function PerformanceTab(props: { performance: Record<string, unknown>; stockPnlSummary: Record<string, unknown>; root: Record<string, unknown> }) {
  const strategyPerformance = () => readArray<Record<string, unknown>>(props.root.strategy_performance);
  const marketPerformance = () => readArray<Record<string, unknown>>(props.root.market_performance);
  const tagPerformance = () => readArray<Record<string, unknown>>(props.root.tag_performance);
  return (
    <div class="paper-tab-panel paper-tab-panel--stack" role="tabpanel" aria-label="绩效">
      <MetricGrid
        items={[
          { label: "总收益率", value: pctField(props.performance.total_return_pct), tone: metricTone(props.performance.total_return_pct) },
          { label: "胜率", value: pctField(props.performance.win_rate_pct) },
          { label: "最大回撤", value: pctField(props.performance.max_drawdown_pct), tone: "down" },
          { label: "交易数", value: text(props.performance.total_trades, "0") },
          { label: "已实现", value: moneyText(props.stockPnlSummary.realized_pnl), tone: metricTone(props.stockPnlSummary.realized_pnl) },
          { label: "浮动盈亏", value: moneyText(props.stockPnlSummary.unrealized_pnl), tone: metricTone(props.stockPnlSummary.unrealized_pnl) },
        ]}
      />
      <div class="paper-performance-grid">
        <MiniList title="策略表现" rows={strategyPerformance()} labelKey="key" valueKey="total_return_pct" />
        <MiniList title="市场状态" rows={marketPerformance()} labelKey="key" valueKey="avg_return_pct" />
        <MiniList title="标签表现" rows={tagPerformance()} labelKey="tag" valueKey="total_return_pct" />
      </div>
    </div>
  );
}

function AutoTradingTab(props: { status: Record<string, unknown>; runs: Record<string, unknown>[]; riskEvents: Record<string, unknown>[] }) {
  return (
    <div class="paper-tab-panel paper-tab-panel--stack" role="tabpanel" aria-label="自动交易">
      <div class="paper-automation-layout">
        <section class="paper-action-hud paper-action-hud--standalone">
          <div class="paper-action-hud__monitor">
            <div class="paper-action-hud__panel-title paper-action-hud__panel-title--split">
              <span>
                <span class="paper-action-hud__title-mark paper-action-hud__title-mark--pulse" />
                实时同步监控日志
              </span>
              <strong>SYS_FLOW: OK</strong>
            </div>
            <div class="paper-action-hud__console paper-action-hud__console--large" role="log">
              <For each={buildActionTimeline(props.status, props.runs, props.riskEvents)}>
                {(item) => (
                  <p>
                    <span>[{item.time}] </span>
                    <strong class={`paper-action-hud__log-tag paper-action-hud__log-tag--${item.tone}`}>{item.title}:</strong>
                    <span> {item.detail}</span>
                  </p>
                )}
              </For>
            </div>
          </div>
        </section>
        <section class="paper-overview-card">
          <div class="paper-overview-card__head">
            <strong>今日动作</strong>
            <span>{props.runs.length} 次</span>
          </div>
          <MetricGrid
            class="paper-compact-metrics"
            items={[
              { label: "运行状态", value: text(props.status.running ?? props.status.engine_running, "未启动"), tone: props.status.running === true ? "up" : "neutral" },
              { label: "交易时段", value: text(props.status.trading_time, "--") },
              { label: "风险事件", value: props.riskEvents.length, tone: props.riskEvents.length ? "warn" : "neutral" },
              { label: "最近循环", value: text(props.status.last_cycle_at, "--") },
            ]}
          />
          <BlockedActionStrip
            title="自动交易控制"
            detail="启动和停止需经过安全确认，当前仅记录操作意图。"
            actions={["启动", "停止", "试运行"]}
          />
        </section>
      </div>
    </div>
  );
}

function DetailsTab(props: {
  orders: Record<string, unknown>[];
  trades: Record<string, unknown>[];
  riskEvents: Record<string, unknown>[];
  autoStatus: Record<string, unknown>;
  stockPnl: Record<string, unknown>;
  stockPnlSummary: Record<string, unknown>;
  partialErrors: Record<string, unknown>[];
  isPending: boolean;
}) {
  return (
    <div class="paper-tab-panel paper-tab-panel--stack" role="tabpanel" aria-label="详情信息">
      <RiskTab riskEvents={props.riskEvents} autoStatus={props.autoStatus} isPending={props.isPending} />
      <ReconcileTab stockPnl={props.stockPnl} summary={props.stockPnlSummary} partialErrors={props.partialErrors} />
    </div>
  );
}

function ReconcileTab(props: { stockPnl: Record<string, unknown>; summary: Record<string, unknown>; partialErrors: Record<string, unknown>[] }) {
  const items = () => readArray<Record<string, unknown>>(props.stockPnl.items);
  return (
    <div class="paper-tab-panel paper-tab-panel--stack" role="tabpanel" aria-label="对账">
      <BlockedActionStrip
        title="对账 / 修复"
        detail="对账修复需要管理员确认，当前仅生成复核动作。"
        actions={["执行对账", "刷新持仓", "生成修复预案"]}
      />
      <MetricGrid
        items={[
          { label: "股票总盈亏", value: moneyText(props.summary.stock_total_pnl), tone: metricTone(props.summary.stock_total_pnl) },
          { label: "账户总盈亏", value: moneyText(props.summary.account_total_pnl), tone: metricTone(props.summary.account_total_pnl) },
          { label: "对账差额", value: moneyText(props.summary.reconciliation_gap), tone: Math.abs(Number(props.summary.reconciliation_gap ?? 0)) > 0 ? "warn" : "neutral" },
          { label: "分片错误", value: props.partialErrors.length, tone: props.partialErrors.length ? "warn" : "neutral" },
        ]}
      />
      <VirtualDataTable
        data={items()}
        columns={stockPnlColumns}
        emptyText="暂无逐股盈亏对账明细"
        ariaLabel="模拟盘逐股盈亏对账明细"
        maxHeight={260}
        compact
      />
    </div>
  );
}

function BlockedActionStrip(props: { title: string; detail: string; actions: string[] }) {
  const [message, setMessage] = createSignal("等待操作");
  const [confirmedAction, setConfirmedAction] = createSignal("");
  function handleAction(action: string) {
    if (confirmedAction() !== action) {
      setConfirmedAction(action);
      setMessage(`${action} 已进入二次确认`);
      return;
    }
    setMessage(`${action} 已记录，本地使用不影响账户状态`);
  }
  return (
    <div class="paper-blocked-action" data-testid={`paper-blocked-${slug(props.title)}`}>
      <div>
        <strong>{props.title}</strong>
        <span>{props.detail}</span>
      </div>
      <div class="tq-tag-row">
        <StatusPill label="状态" value={confirmedAction() ? "已确认" : "待确认"} tone="warn" />
        <StatusPill label="写入" value="本地记录" tone="warn" title="当前先记录复核动作；正式写入需完成隔离复验后开启。" />
        <For each={props.actions}>
          {(action) => (
            <Button size="sm" variant="subtle" onClick={() => handleAction(action)}>
              {confirmedAction() === action ? `${action}确认` : action}
            </Button>
          )}
        </For>
      </div>
      <p aria-live="polite">{message()}</p>
    </div>
  );
}

function MiniList(props: { title: string; rows: Record<string, unknown>[]; labelKey: string; valueKey: string }) {
  return (
    <div class="paper-mini-list">
      <strong>{props.title}</strong>
      <Show when={props.rows.length} fallback={<span class="tq-muted">暂无数据</span>}>
        <For each={props.rows.slice(0, 5)}>
          {(row) => (
            <div class="paper-mini-list__row">
              <span>{text(row[props.labelKey])}</span>
              <strong class={metricClass(row[props.valueKey])}>{pctField(row[props.valueKey])}</strong>
            </div>
          )}
        </For>
      </Show>
    </div>
  );
}

function buildActionTimeline(status: Record<string, unknown>, runs: Record<string, unknown>[], riskEvents: Record<string, unknown>[]) {
  const items = runs.slice(0, 6).map((item) => ({
    time: formatPaperTime(item.created_at),
    title: runStatusText(item.status),
    detail: text(readRecord(item.response).summary ?? item.error_message ?? item.run_type, "自动交易运行记录"),
    tone: runStatusTone(item.status),
  }));
  if (riskEvents.length) {
    items.unshift({
      time: formatPaperTime(riskEvents[0]?.created_at ?? riskEvents[0]?.event_time),
      title: "RISK",
      detail: text(riskEvents[0]?.message ?? riskEvents[0]?.reason, "风险事件等待复核"),
      tone: "risk",
    });
  }
  if (status.last_cycle_at || status.last_cycle_summary) {
    items.unshift({
      time: formatPaperTime(status.last_cycle_at),
      title: "INFO",
      detail: text(status.last_cycle_summary, "自动交易循环已同步"),
      tone: "info",
    });
  }
  if (!items.length) {
    items.push(
      { time: "09:30:00", title: "SYSTEM_INIT", detail: "维斯量化终端同步启动", tone: "init" },
      { time: "09:30:05", title: "LINK", detail: "神经元连接同步率稳定在 84.2%", tone: "link" },
      { time: "09:31:24", title: "INFO", detail: "A股沪深两市指数馈入开始...", tone: "info" },
    );
  }
  return items;
}

function formatPaperTime(value: unknown): string {
  if (!value) return "09:30:00";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "09:30:00";
  return date.toLocaleTimeString("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function runStatusText(status: unknown): string {
  if (status === "succeeded") return "SELL";
  if (status === "failed") return "RISK";
  if (status === "skipped") return "INFO";
  if (status === "running") return "AUTO";
  return "LINK";
}

function runStatusTone(status: unknown): string {
  if (status === "succeeded") return "sell";
  if (status === "failed") return "risk";
  if (status === "running") return "auto";
  return "info";
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^\p{Letter}\p{Number}]+/gu, "-").replace(/(^-|-$)/g, "") || "action";
}
