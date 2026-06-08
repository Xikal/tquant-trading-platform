import { createQuery } from "@tanstack/solid-query";
import { useLocation } from "@tanstack/solid-router";
import { For, Show, createEffect, createMemo, createSignal, onCleanup } from "solid-js";
import { apiClient } from "../../shared/api/client";
import { queryKeys } from "../../shared/api/queryKeys";
import { Button } from "../../shared/ui/Button";
import { Modal } from "../../shared/ui/Modal";
import { readArray, readRecord, text } from "../shared/dataAccess";
import { PageScaffold } from "../shared/PageScaffold";
import { PaperMechaHud } from "./PaperMechaHud";
import { PaperOrderForm } from "./PaperOrderForm";
import { PaperWorkflowTabs } from "./PaperWorkflowTabs";
import { paperOrderDraftFromSearch, paperOrderDraftKey } from "./paperOrderDraft";
import "../../shared/styles/legacy-workspace/workspace-paper-mecha.css";
import "./paper-page.css";

export function PaperPage() {
  const location = useLocation();
  const [orderOpen, setOrderOpen] = createSignal(false);
  const [openedDraftKey, setOpenedDraftKey] = createSignal("");
  const [pulseTime, setPulseTime] = createSignal(formatClock());
  const [copiedUid, setCopiedUid] = createSignal(false);
  const [isRefreshing, setIsRefreshing] = createSignal(false);
  const [workflowMounted, setWorkflowMounted] = createSignal(false);
  let copyTimer: ReturnType<typeof setTimeout> | undefined;
  let refreshTimer: ReturnType<typeof setTimeout> | undefined;
  const query = createQuery(() => ({
    queryKey: queryKeys.paperWorkspace,
    queryFn: ({ signal }) => apiClient.paperWorkspace({ signal }),
  }));
  const root = () => readRecord(query.data);
  const account = () => readRecord(root().account);
  const positions = () => readArray<Record<string, unknown>>(root().positions);
  const orders = () => readArray<Record<string, unknown>>(root().orders);
  const riskEvents = () => readArray<Record<string, unknown>>(root().risk_events);
  const opportunityCount = createMemo(() => Math.max(1, readArray(root().recommendations).length || positions().filter((item) => Number(item.unrealized_pnl ?? item.pnl) > 0).length));
  const handoffDraft = createMemo(() => paperOrderDraftFromSearch(location().search));
  const handoffDraftKey = createMemo(() => paperOrderDraftKey(handoffDraft()));

  createEffect(() => {
    if (typeof window === "undefined") return;
    const timer = window.setInterval(() => setPulseTime(formatClock()), 1000);
    onCleanup(() => window.clearInterval(timer));
  });

  createEffect(() => {
    const nextDraftKey = handoffDraftKey();
    if (!nextDraftKey || nextDraftKey === openedDraftKey()) return;
    setOpenedDraftKey(nextDraftKey);
    setOrderOpen(true);
  });

  onCleanup(() => {
    if (copyTimer) clearTimeout(copyTimer);
    if (refreshTimer) clearTimeout(refreshTimer);
  });

  const handleCopyUid = () => {
    const uid = accountUid(root(), account());
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      void navigator.clipboard.writeText(uid);
    } else if (typeof document !== "undefined") {
      const node = document.createElement("textarea");
      node.value = uid;
      node.setAttribute("readonly", "true");
      document.body.appendChild(node);
      node.select();
      try {
        document.execCommand("copy");
      } catch {
        // Clipboard permission can be unavailable in local previews; the UID stays visible for manual copy.
      }
      document.body.removeChild(node);
    }
    setCopiedUid(true);
    if (copyTimer) clearTimeout(copyTimer);
    copyTimer = setTimeout(() => setCopiedUid(false), 1600);
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    void query.refetch().finally(() => {
      if (refreshTimer) clearTimeout(refreshTimer);
      refreshTimer = setTimeout(() => setIsRefreshing(false), 260);
    });
  };

  return (
    <PageScaffold page="paper" class="paper-page paper-console-page">
      <section class="paper-console-shell tq-page__full" aria-label="模拟盘控制台">
        <header class="paper-console-header">
          <div class="paper-console-brand">
            <span class="paper-console-brand__mark" aria-hidden="true">模</span>
            <h1>模拟盘控制台</h1>
          </div>
          <div class="paper-console-skip" title={recentSkipText(root())}>
            <span class="paper-console-skip__dot" aria-hidden="true" />
            <span>最近跳过：</span>
            <strong>{recentSkipText(root())}</strong>
          </div>
          <div class="paper-console-controls" aria-label="模拟盘控制项">
            <button type="button" class="paper-console-status-chip paper-console-status-chip--hot" onClick={() => setOrderOpen(true)}>
              <span>机会</span>
              <strong>{opportunityCount()}</strong>
            </button>
            <button type="button" class={`paper-console-status-chip${riskEvents().length ? " paper-console-status-chip--risk" : ""}`}>
              <span>风险</span>
              <strong>{riskEvents().length}</strong>
            </button>
            <div class="paper-console-pulse" aria-label={`脉冲 ${pulseTime()}`}>
              <ActivityIcon />
              <span>脉冲</span>
              <strong>{pulseTime()}</strong>
            </div>
            <button type="button" class="paper-console-uid" onClick={handleCopyUid}>
              <span>ID: {accountUid(root(), account())}</span>
              <CopyIcon />
              <Show when={copiedUid()}>
                <strong>已复制</strong>
              </Show>
            </button>
            <Button variant="primary" size="sm" class="paper-console-order" onClick={() => setOrderOpen(true)} data-testid="paper-open-order">
              模拟委托
            </Button>
            <Button
              variant="primary"
              iconOnly
              title="刷新模拟盘"
              aria-label="刷新模拟盘"
              class={`paper-console-refresh${isRefreshing() ? " paper-console-refresh--spinning" : ""}`}
              icon={<RefreshIcon />}
              onClick={handleRefresh}
              disabled={isRefreshing()}
            />
          </div>
        </header>

        <div class="paper-console-grid">
          <div class="paper-console-main-top">
            <section class="paper-account-card" aria-label="账户综合看板">
              <div class="paper-account-card__stripe" aria-hidden="true" />
              <div class="paper-section-head">
                <div>
                  <span class="paper-section-head__mark" aria-hidden="true" />
                  <h2>账户综合看板</h2>
                </div>
                <button type="button" class="paper-review-link">
                  <span>复盘历史:</span>
                  <strong>{reviewCount(root())} 条</strong>
                </button>
              </div>
              <PaperMetricCards account={account()} />
            </section>

            <section class="paper-holdings-card" aria-label="当前持仓">
              <div class="paper-section-head paper-section-head--compact">
                <div>
                  <span class="paper-section-head__mark" aria-hidden="true" />
                  <h2>当前持仓</h2>
                  <strong class="paper-count-pill">共 {positions().length} 只</strong>
                </div>
                <div class="paper-holdings-note">
                  <span class="paper-holdings-note__dot" aria-hidden="true" />
                  <span>首屏直接处理</span>
                  <i aria-hidden="true" />
                  <button type="button">一键清仓限制</button>
                </div>
              </div>
              <PaperPositionGrid positions={positions()} isPending={query.isPending} isError={query.isError} onOpenOrder={() => setOrderOpen(true)} />
            </section>
          </div>

          <aside class="paper-console-side" aria-label="模拟盘机甲舱">
            <PaperMechaHud root={root()} apiState={query.isError ? "error" : query.isPending ? "loading" : "ready"} />
          </aside>
        </div>

        <div class="paper-workflow-shell">
          <Show
            when={workflowMounted()}
            fallback={
              <PaperWorkflowLauncher
                root={root()}
                isPending={query.isPending}
                isError={query.isError}
                onOpen={() => setWorkflowMounted(true)}
              />
            }
          >
            <PaperWorkflowTabs root={root()} isPending={query.isPending} isError={query.isError} />
          </Show>
        </div>
      </section>
      <Modal open={orderOpen()} title="模拟委托" onClose={() => setOrderOpen(false)} width={860} class="paper-order-modal">
        <PaperOrderForm orders={orders()} positions={positions()} embedded initialDraft={handoffDraft()} draftKey={handoffDraftKey()} />
      </Modal>
    </PageScaffold>
  );
}

function PaperWorkflowLauncher(props: { root: Record<string, unknown>; isPending: boolean; isError: boolean; onOpen: () => void }) {
  const autoRuns = () => readArray<Record<string, unknown>>(props.root.auto_trading_runs);
  const riskEvents = () => readArray<Record<string, unknown>>(props.root.risk_events);
  const lastRun = () => autoRuns()[0] ?? {};
  return (
    <section class="paper-workflow-lazy" aria-label="模拟盘自动化入口">
      <div>
        <strong>自动化与复盘明细</strong>
        <span>
          {props.isPending
            ? "正在读取模拟盘数据"
            : props.isError
              ? "数据降级，点击查看本地复核面板"
              : `当前快照 ${autoRuns().length} 次动作 · 风险 ${riskEvents().length} 条 · 最近 ${text(lastRun().status ?? "idle")}`}
        </span>
      </div>
      <Button variant="primary" size="sm" onClick={props.onOpen}>
        展开工作流
      </Button>
    </section>
  );
}

function moneyText(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : "--";
}

function signedMoneyText(value: unknown): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  const sign = parsed > 0 ? "+" : parsed < 0 ? "-" : "";
  return `${sign}${moneyText(Math.abs(parsed))}`;
}

function percentFromPctField(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${parsed.toFixed(2)}%` : "--";
}

function metricTone(value: unknown): "neutral" | "up" | "down" {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed === 0) return "neutral";
  return parsed > 0 ? "up" : "down";
}

function PaperMetricCards(props: { account: Record<string, unknown> }) {
  const account = () => props.account;
  const todayValue = () => (account().today_pnl !== undefined ? signedMoneyText(account().today_pnl) : percentFromPctField(account().today_return_pct));
  const marketValue = () => Number(account().market_value);
  const totalAssets = () => Number(account().total_assets ?? account().total_equity);
  const positionRatio = () => {
    if (!Number.isFinite(marketValue()) || !Number.isFinite(totalAssets()) || totalAssets() === 0) return "--";
    return `${((marketValue() / totalAssets()) * 100).toFixed(1)}%`;
  };

  return (
    <div class="paper-console-metrics">
      <article class="paper-console-metric">
        <span>总资产 (CNY)</span>
        <strong>{moneyText(account().total_assets ?? account().total_equity)}</strong>
        <small><i class="paper-dot paper-dot--ok" aria-hidden="true" />实盘实时镜像</small>
      </article>
      <article class={`paper-console-metric paper-console-metric--${metricTone(account().unrealized_pnl)}`}>
        <span>浮动盈亏</span>
        <strong>{signedMoneyText(account().unrealized_pnl)}</strong>
        <small>{percentFromPctField(account().total_return_pct)} 策略平均值</small>
      </article>
      <article class={`paper-console-metric paper-console-metric--${metricTone(account().today_pnl ?? account().today_return_pct)}`}>
        <span>当日盈亏</span>
        <strong>{todayValue()}</strong>
        <small>{Number(account().today_pnl ?? account().today_return_pct) === 0 ? "暂无高频突破交易" : "交易变动已同步"}</small>
      </article>
      <article class="paper-console-metric">
        <span>总市值</span>
        <strong>{moneyText(account().market_value)}</strong>
        <small>仓位占比: <b>{positionRatio()}</b></small>
      </article>
    </div>
  );
}

function PaperPositionGrid(props: { positions: Record<string, unknown>[]; isPending: boolean; isError: boolean; onOpenOrder: () => void }) {
  return (
    <Show
      when={props.positions.length}
      fallback={<div class="paper-console-empty">{props.isPending ? "正在读取模拟盘持仓" : props.isError ? "持仓接口暂不可用" : "暂无模拟持仓"}</div>}
    >
      <div class="paper-console-positions" aria-label="模拟盘当前持仓">
        <For each={props.positions}>
          {(item) => <PaperPositionCard item={item} onOpenOrder={props.onOpenOrder} />}
        </For>
      </div>
    </Show>
  );
}

function PaperPositionCard(props: { item: Record<string, unknown>; onOpenOrder: () => void }) {
  const item = () => props.item;
  const pnl = () => item().unrealized_pnl_pct ?? item().pnl_pct ?? item().pnl ?? item().unrealized_pnl;
  const tone = () => positionTone(pnl());
  return (
    <article class={`paper-console-position paper-console-position--${tone()}`}>
      <div class="paper-console-position__head">
        <div>
          <h3>{text(item().name ?? item().stock_name ?? item().security_name, "未知标的")}</h3>
          <span>{text(item().symbol ?? item().code)}</span>
        </div>
        <strong>{signedPercentText(pnl())}</strong>
      </div>
      <div class="paper-console-position__qty">
        <div>
          <span>持股数量</span>
          <strong>{quantityText(item().quantity ?? item().shares ?? item().hold)}</strong>
        </div>
        <div>
          <span>当日可用</span>
          <strong>{quantityText(item().available_quantity ?? item().available ?? item().avail)}</strong>
        </div>
      </div>
      <div class="paper-console-position__price">
        <div>
          <span>成本</span>
          <strong>{decimalText(item().cost_basis ?? item().avg_cost ?? item().cost)}</strong>
        </div>
        <div>
          <span>最新</span>
          <strong>{decimalText(item().latest_price ?? item().last_price ?? item().current)}</strong>
        </div>
      </div>
      <div class="paper-console-position__actions" aria-label={`${text(item().symbol ?? item().code)} 操作`}>
        <button type="button" onClick={props.onOpenOrder}>快速清仓</button>
        <button type="button" onClick={props.onOpenOrder}>交易诊断</button>
      </div>
    </article>
  );
}

function formatClock(): string {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function recentSkipText(root: Record<string, unknown>): string {
  const autoRuns = readArray<Record<string, unknown>>(root.auto_trading_runs);
  const skipped = autoRuns.find((item) => item.status === "skipped") ?? readRecord(root.auto_trading_status).last_skip;
  const record = readRecord(skipped);
  const response = readRecord(record.response);
  const symbol = text(response.symbol ?? record.symbol ?? record.code, "");
  const reason = text(response.reason ?? response.summary ?? record.reason ?? record.error_message, "暂无跳过记录");
  return symbol ? `${symbol}: ${reason}` : reason;
}

function accountUid(root: Record<string, unknown>, account: Record<string, unknown>): string {
  return text(root.uid ?? root.user_id ?? account.uid ?? account.external_id, "915927066");
}

function reviewCount(root: Record<string, unknown>): number {
  return readArray(root.review_history).length || readArray(root.auto_trading_runs).length || 5;
}

function signedPercentText(value: unknown): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${parsed.toFixed(2)}%`;
}

function decimalText(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(3) : "--";
}

function quantityText(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) : text(value);
}

function positionTone(value: unknown): "positive" | "negative" | "neutral" {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed === 0) return "neutral";
  return parsed > 0 ? "positive" : "negative";
}

function ActivityIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 13h4l2-6 4 12 2-6h4" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="8" y="8" width="10" height="10" rx="2" />
      <path d="M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 6v5h-5" />
      <path d="M4 18v-5h5" />
      <path d="M18.6 9a7 7 0 0 0-11.4-2.4L4 10" />
      <path d="M5.4 15a7 7 0 0 0 11.4 2.4L20 14" />
    </svg>
  );
}
