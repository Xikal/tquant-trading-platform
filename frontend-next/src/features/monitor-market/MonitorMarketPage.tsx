import { createQuery } from "@tanstack/solid-query";
import { For, Show, createSignal, onCleanup } from "solid-js";
import { apiClient } from "../../shared/api/client";
import { queryKeys } from "../../shared/api/queryKeys";
import { Icon as SharedIcon } from "../../shared/ui/Icon";
import { nested, pickFirst, readArray, text } from "../shared/dataAccess";
import { PageScaffold } from "../shared/PageScaffold";
import { QueryState } from "../shared/queryState";
import { createMonitorMarketModel, type MarketPanelModel } from "./monitorMarketModel";
import "./monitor-market.css";

type DataMode = "empty" | "active";
type IconName =
  | "activity"
  | "alert"
  | "bar"
  | "briefcase"
  | "clock"
  | "cpu"
  | "database"
  | "flame"
  | "layers"
  | "line"
  | "refresh"
  | "shield"
  | "sliders"
  | "trendDown"
  | "trendUp";

export function MonitorMarketPage() {
  const [dataMode, setDataMode] = createSignal<DataMode>("active");
  const [isRefreshing, setIsRefreshing] = createSignal(false);
  let refreshTimer: number | undefined;
  onCleanup(() => {
    if (refreshTimer) window.clearTimeout(refreshTimer);
  });
  const query = createQuery(() => ({
    queryKey: queryKeys.monitorWorkspace("market"),
    queryFn: ({ signal }) => apiClient.monitorWorkspace("market", 10, { signal }),
  }));

  const handleRefresh = () => {
    setIsRefreshing(true);
    void query.refetch().finally(() => {
      if (refreshTimer) window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        setIsRefreshing(false);
      }, 360);
    });
  };

  return (
    <QueryState query={query}>
      {(data) => {
        const model = createMonitorMarketModel(data);
        const view = buildView(model);
        const active = () => dataMode() === "active";

        return (
          <PageScaffold page="monitor-market" class="market-sentiment-page">
            <section class="market-sentiment tq-page__full" aria-label="市场情绪与市场总闸监控">
              <header class="market-sentiment-header">
                <div class="market-sentiment-brand">
                  <span class="market-sentiment-brand__icon"><Icon name="cpu" /></span>
                  <div>
                    <h1>市场总闸 & 数据质量监控</h1>
                    <span>PRO-SYSTEM</span>
                  </div>
                </div>

                <div class="market-sentiment-controls">
                  <div class="market-sentiment-mode" role="tablist" aria-label="市场数据模式">
                    <button
                      type="button"
                      class={dataMode() === "empty" ? "market-sentiment-mode__item market-sentiment-mode__item--active market-sentiment-mode__item--empty" : "market-sentiment-mode__item"}
                      onClick={() => setDataMode("empty")}
                    >
                      空态预览
                    </button>
                    <button
                      type="button"
                      class={dataMode() === "active" ? "market-sentiment-mode__item market-sentiment-mode__item--active" : "market-sentiment-mode__item"}
                      onClick={() => setDataMode("active")}
                    >
                      实时数据
                    </button>
                  </div>
                  <button type="button" class="market-sentiment-refresh" onClick={handleRefresh}>
                    <Icon name="refresh" spin={isRefreshing()} />
                    <span>刷新</span>
                  </button>
                </div>
              </header>

              <main class="market-sentiment-main">
                <section class="market-sentiment-top-grid">
                  <MarketGateCard view={view} active={active()} />
                  <RuntimeCard view={view} />
                </section>

                <section class="market-sentiment-three-grid">
                  <BreadthPulseCard active={active()} view={view} />
                  <SectorLeaderCard active={active()} view={view} />
                  <EtfHedgeCard active={active()} view={view} />
                </section>

                <ReviewActionCard active={active()} view={view} />
              </main>

              <footer class="market-sentiment-footer">
                QUANT DATA PLATFORM © 2026 PRO TERMINAL · 投资有风险 入市需谨慎
              </footer>
            </section>
          </PageScaffold>
        );
      }}
    </QueryState>
  );
}

function MarketGateCard(props: { view: MarketView; active: boolean }) {
  const firepowerWidth = () => `${Math.max(0, Math.min(100, props.active ? props.view.firepower : 0))}%`;
  return (
    <article class="market-sentiment-card market-sentiment-card--gate">
      <div class="market-sentiment-glow" />
      <div class="market-sentiment-card__head">
        <div>
          <span class="market-sentiment-ping"><i /><b /></span>
          <h2><Icon name="shield" />市场状态总闸</h2>
        </div>
        <span>{props.view.syncStatus}</span>
      </div>

      <div class="market-sentiment-gate-grid">
        <div class={`market-sentiment-status-block${props.view.gateBlocked ? " market-sentiment-status-block--block" : " market-sentiment-status-block--pass"}`}>
          <div>
            <span>生产阀门</span>
            <b>{props.view.gateCode}</b>
          </div>
          <strong>{props.view.gateDecisionText}</strong>
          <p>{props.view.gateDecisionHint}</p>
        </div>

        <div class="market-sentiment-status-block">
          <div>
            <span>当前火力</span>
            <Icon name="flame" />
          </div>
          <strong class="market-sentiment-firepower">{props.active ? `${props.view.firepower}%` : "0%"}</strong>
          <p>{props.active ? props.view.firepowerLabel : "[冰点]"}</p>
          <i class="market-sentiment-mini-progress"><b style={{ width: firepowerWidth() }} /></i>
        </div>

        <div class="market-sentiment-status-block">
          <div>
            <span>操作姿态</span>
            <Icon name={props.view.gateBlocked ? "trendDown" : "trendUp"} />
          </div>
          <strong class="market-sentiment-posture">{props.view.posture}</strong>
          <p>{props.view.postureHint}</p>
        </div>
      </div>

      <div class="market-sentiment-interpretation">
        <p><strong>「状态：{props.view.marketState}」</strong>{props.view.marketRead}</p>
        <div class="market-sentiment-data-tags">
          <span>最后更新: <b>{props.view.dataUpdatedAt}</b></span>
          <span>缓存状态: <b>{props.view.cacheState}</b></span>
        </div>
        <div>
          <span>当前热点:</span>
          <For each={props.view.hotSectors}>
            {(sector, index) => (
              <>
                <b>{sector}</b>
                <Show when={index() < props.view.hotSectors.length - 1}><i>/</i></Show>
              </>
            )}
          </For>
          <em>强度: {props.view.hotStrength}</em>
        </div>
      </div>
    </article>
  );
}

function RuntimeCard(props: { view: MarketView }) {
  return (
    <article class="market-sentiment-card market-sentiment-card--runtime">
      <div class="market-sentiment-card__head">
        <div>
          <h3><Icon name="database" />运行时同步状态</h3>
        </div>
        <span class="market-sentiment-db-badge"><i />{props.view.databaseBackend}</span>
      </div>
      <div class="market-sentiment-runtime-grid">
        <RuntimeMetric label="已持仓自选" value={props.view.holdingCount} unit="标的" />
        <RuntimeMetric label="当前快照可操作" value={props.view.actionCount} unit="机会" tone="amber" />
        <RuntimeMetric label="需要避险" value={props.view.riskCount} unit="预警" tone="rose" />
        <RuntimeMetric label="平均质量分" value={props.view.averageScore} tone="emerald" mono />
      </div>
      <div class="market-sentiment-runtime-footer">
        <span><Icon name="clock" />生产榜/数据源:</span>
        <b>{props.view.boardRefreshCount}</b>
        <i>/</i>
        <strong>{props.view.dataUpdatedAt}</strong>
      </div>
    </article>
  );
}

function RuntimeMetric(props: { label: string; value: string; unit?: string; tone?: "amber" | "rose" | "emerald"; mono?: boolean }) {
  return (
    <div class="market-sentiment-runtime-metric">
      <span>{props.label}</span>
      <strong class={`${props.tone ? `market-sentiment-tone--${props.tone}` : ""}${props.mono ? " market-sentiment-mono" : ""}`}>
        {props.value}
        <Show when={props.unit}><small>{props.unit}</small></Show>
      </strong>
    </div>
  );
}

function BreadthPulseCard(props: { active: boolean; view: MarketView }) {
  return (
    <article class="market-sentiment-card market-sentiment-card--compact">
      <CompactHead icon="activity" title="市场宽度与脉冲" badge={props.active ? "LIVE" : undefined} />
      <Show when={props.active} fallback={<EmptyState icon="bar" title="数据暂未形成" desc="保留结构等待监控 BFF 刷新" meta="宽度: -- | 脉冲: no_data" />}>
        <div class="market-sentiment-pulse-body">
          <div class="market-sentiment-inline-metric">
            <span>中位数涨幅</span>
            <strong>{props.view.medianChange}</strong>
          </div>
          <div class="market-sentiment-bars">
            <div>
              <For each={props.view.pulseBars}>
                {(height) => <i class={height > 55 ? "is-hot" : height > 30 ? "is-warm" : ""} style={{ height: `${height}%` }} />}
              </For>
            </div>
            <footer><span>09:30</span><span>脉冲监测</span><span>15:00</span></footer>
          </div>
        </div>
      </Show>
    </article>
  );
}

function SectorLeaderCard(props: { active: boolean; view: MarketView }) {
  return (
    <article class="market-sentiment-card market-sentiment-card--compact">
      <CompactHead icon="layers" title="板块与龙头确认" badge={`健康 ${props.active ? props.view.leaders.length : 0}/${props.active ? props.view.hotSectors.length : 0}`} tone="amber" />
      <Show when={props.active} fallback={<EmptyState icon="sliders" title="暂无板块/龙头确认数据" meta="板块: 0  等待扩散" />}>
        <div class="market-sentiment-leader-list">
          <For each={props.view.leaders}>
            {(item) => (
              <div class="market-sentiment-leader-row">
                <div>
                  <span>龙头</span>
                  <strong>{item.sector} · {item.name}</strong>
                </div>
                <b>{item.change}</b>
              </div>
            )}
          </For>
          <p>📌 <strong>{props.view.mainline}</strong>{props.view.leaderAdvice}</p>
        </div>
      </Show>
    </article>
  );
}

function EtfHedgeCard(props: { active: boolean; view: MarketView }) {
  return (
    <article class="market-sentiment-card market-sentiment-card--compact">
      <CompactHead icon="line" title="ETF T0 / 对冲" badge={`${props.active ? props.view.etfRows.length : 0} 个机会`} />
      <Show when={props.active && props.view.etfRows.length > 0} fallback={<EmptyState icon="layers" title="暂无 ETF 做T信号" desc="低吸/热点信号明确时展示，同步队列运行中" />}>
        <div class="market-sentiment-etf-list">
          <For each={props.view.etfRows}>
            {(item) => (
              <div>
                <header>
                  <strong>{item.symbol} · {item.name}</strong>
                  <span>{item.action}</span>
                </header>
                <footer>
                  <span>溢价: {item.premium}</span>
                  <span>波幅: {item.range}</span>
                </footer>
              </div>
            )}
          </For>
        </div>
      </Show>
    </article>
  );
}

function ReviewActionCard(props: { active: boolean; view: MarketView }) {
  return (
    <article class="market-sentiment-card market-sentiment-review">
      <div class="market-sentiment-card__head market-sentiment-card__head--review">
        <div>
          <h3><Icon name="alert" />午盘 / 收盘复盘分析与实战建议</h3>
        </div>
        <span class={props.active ? "is-published" : "is-empty"}>{props.active ? "已发布" : "暂无复盘"}</span>
      </div>
      <div class="market-sentiment-review-grid">
        <div class="market-sentiment-review-copy">
          <ReviewBlock title="午盘复盘" published={props.active} text={props.view.middayReview} fallback="全市场午盘复盘暂未生成。" />
          <ReviewBlock title="收盘复盘" published={props.active} text={props.view.closeReview} fallback="全市场收盘复盘暂未生成。" />
        </div>
        <div class="market-sentiment-action-box">
          <header>
            <strong><Icon name="briefcase" />风控动作</strong>
            <span>风险提示: {props.active ? props.view.riskCount : "0"}</span>
          </header>
          <p class={props.active ? "is-danger" : ""}>{props.active ? props.view.actionAdvice : "等待复盘生成，盘中按既有 Pulse 规则和风控执行。"}</p>
          <footer><span>安全等级:</span><strong>{props.view.safetyLevel}</strong></footer>
        </div>
      </div>
    </article>
  );
}

function CompactHead(props: { icon: IconName; title: string; badge?: string; tone?: "amber" }) {
  return (
    <div class="market-sentiment-compact-head">
      <h3><Icon name={props.icon} />{props.title}</h3>
      <Show when={props.badge}><span class={props.tone === "amber" ? "is-amber" : ""}>{props.badge}</span></Show>
    </div>
  );
}

function EmptyState(props: { icon: IconName; title: string; desc?: string; meta?: string }) {
  return (
    <div class="market-sentiment-empty">
      <span><Icon name={props.icon} /></span>
      <strong>{props.title}</strong>
      <Show when={props.desc}><p>{props.desc}</p></Show>
      <Show when={props.meta}><em>{props.meta}</em></Show>
    </div>
  );
}

function ReviewBlock(props: { title: string; published: boolean; text: string; fallback: string }) {
  return (
    <div class="market-sentiment-review-block">
      <header><strong>{props.title}</strong><span>{props.published ? "已发布" : "等待触发"}</span></header>
      <p class={props.published ? "" : "is-empty"}>{props.published ? props.text : props.fallback}</p>
    </div>
  );
}

function Icon(props: { name: IconName; spin?: boolean }) {
  return (
    <SharedIcon
      name={props.name}
      class="market-sentiment-icon"
      spin={props.spin}
      spinClass="market-sentiment-icon--spin"
    />
  );
}

type MarketLeader = { sector: string; name: string; change: string };
type MarketEtf = { symbol: string; name: string; action: string; premium: string; range: string };
type MarketView = {
  actionAdvice: string;
  actionCount: string;
  averageScore: string;
  boardRefreshCount: string;
  closeReview: string;
  dataUpdatedAt: string;
  databaseBackend: string;
  etfRows: MarketEtf[];
  firepower: number;
  firepowerLabel: string;
  gateCode: string;
  gateBlocked: boolean;
  gateDecisionText: string;
  gateDecisionHint: string;
  holdingCount: string;
  hotSectors: string[];
  hotStrength: string;
  leaderAdvice: string;
  leaders: MarketLeader[];
  mainline: string;
  marketRead: string;
  marketState: string;
  medianChange: string;
  middayReview: string;
  posture: string;
  postureHint: string;
  pulseBars: number[];
  riskCount: string;
  safetyLevel: string;
  syncStatus: string;
  cacheState: string;
};

export function buildView(model: MarketPanelModel): MarketView {
  const board = model.board;
  const root = model.root;
  const snapshot = model.snapshot;
  const gateDecision = text(board.market_gate_decision ?? board.gate_decision, "block");
  const marketState = text(board.market_state_category_text ?? board.market_state_text ?? model.breadth.state_text, "--");
  const marketRead = text(board.market_state_text ?? board.market_read ?? model.breadth.summary, "--");
  const firepower = percentNumber(board.market_firepower_multiplier ?? board.firepower ?? 0);
  const hotSectors = stringList(board.hot_industries ?? snapshot.hot_industries ?? model.breadth.hot_industries ?? model.sectorStrength.hot_industries).slice(0, 3);
  const leaders = buildLeaders(model);
  const etfRows = buildEtfs(model);
  const reviewTexts = buildReviews(model);
  const priorityItems = readArray<Record<string, unknown>>(board.items ?? board.priority_items ?? board.stocks ?? snapshot.priority_items);
  const riskItems = priorityItems.filter((item) => {
    const lane = `${item.lane ?? item.action_lane ?? item.action ?? item.risk_level ?? ""}`;
    return lane.includes("risk") || lane.includes("高") || lane.includes("避险");
  });
  const buyItems = priorityItems.filter((item) => {
    const lane = `${item.lane ?? item.action_lane ?? item.action ?? ""}`;
    return lane.includes("buy") || lane.includes("买") || lane.includes("observe") || lane.includes("观察");
  });
  const scores = priorityItems
    .map((item) => Number(pickFirst(item, ["score", "production_score", "quality_score", "final_score"])))
    .filter((value) => Number.isFinite(value));

  return {
    actionAdvice: text(board.action_advice ?? board.risk_action_text, "等待市场总闸刷新后再给出操作建议。"),
    actionCount: String(buyItems.length || text(board.buy_count ?? board.observe_count, "0")),
    averageScore: scores.length ? (scores.reduce((sum, value) => sum + value, 0) / scores.length).toFixed(1) : text(board.average_quality_score, "--"),
    boardRefreshCount: text(board.refresh_count ?? nested(root, "instrument_sync_status.refresh_count"), "0"),
    closeReview: reviewTexts.close,
    dataUpdatedAt: bestUpdatedAt(model),
    databaseBackend: text(model.runtime.database_backend ?? nested(root, "runtime.database_backend"), "MYSQL").toUpperCase(),
    etfRows,
    firepower,
    firepowerLabel: firepower <= 5 ? "[冰点]" : firepower < 35 ? "[低火力]" : "[活跃]",
    gateCode: gateDecision.includes("block") || gateDecision.includes("阻断") || marketState.includes("退潮") ? "BLOCK" : gateDecision.includes("reduce") || gateDecision.includes("谨慎") ? "REDUCE" : "PASS",
    gateBlocked: gateDecision.includes("block") || gateDecision.includes("阻断") || marketState.includes("退潮"),
    gateDecisionText: gateDecisionText(gateDecision, marketState),
    gateDecisionHint: gateDecisionHint(gateDecision, marketState),
    holdingCount: text(board.holding_watch_count ?? nested(root, "paper.holding_count"), "0"),
    hotSectors,
    hotStrength: text(board.hot_strength_text ?? model.breadth.state_text ?? model.breadth.data_quality_text, "--"),
    leaderAdvice: text(model.sectorStrength.leader_advice, "等待板块与龙头确认数据。"),
    leaders,
    mainline: text(nested(model.sectorStrength, "mainline.name") ?? model.sectorStrength.mainline, leaders[0]?.sector ?? "暂无主线"),
    marketRead,
    marketState,
    medianChange: signedPercent(model.breadth.stock_median_change ?? model.breadth.median_change_pct ?? model.breadth.median_pct ?? board.market_median_change_pct, "--"),
    middayReview: reviewTexts.midday,
    posture: text(board.directional_bias_text ?? board.market_direction_text, "谨慎 · 等确认"),
    postureHint: text(board.posture_hint, "不适合追高/低吸"),
    pulseBars: pulseBars(model),
    riskCount: String(riskItems.length || text(board.risk_count ?? board.warning_count, "0")),
    safetyLevel: text(board.safety_level, "LEVEL-ALPHA 3"),
    syncStatus: syncStatus(model),
    cacheState: cacheStateText(model),
  };
}

function gateDecisionText(gateDecision: string, marketState: string): string {
  const raw = `${gateDecision} ${marketState}`.toLowerCase();
  if (raw.includes("block") || raw.includes("阻断") || raw.includes("退潮") || raw.includes("weak")) return "禁止开仓";
  if (raw.includes("reduce") || raw.includes("谨慎") || raw.includes("warning") || raw.includes("震荡")) return "只观察";
  return "允许小仓";
}

function gateDecisionHint(gateDecision: string, marketState: string): string {
  const text = gateDecisionText(gateDecision, marketState);
  if (text === "禁止开仓") return "市场或数据闸门未通过，只允许复盘观察";
  if (text === "只观察") return "允许看盘和轻量跟踪，暂不主动加仓";
  return "可按策略小仓试错，仍需确认买点与止损";
}

function buildLeaders(model: MarketPanelModel): MarketLeader[] {
  const rows = model.sectorRows.slice(0, 4).map((row) => {
    const sector = text(pickFirst(row, ["sector_name", "sector", "industry_name", "industry"]), "");
    const name = text(pickFirst(row, ["leader_name", "leader", "stock_name", "name", "leader_symbol", "symbol", "top_symbol"]), "");
    const change = signedPercent(pickFirst(row, ["leader_change_pct", "change_pct", "pct_chg", "relative_strength"]), "--");
    return { sector, name, change };
  }).filter((item) => item.sector || item.name);
  return rows;
}

function buildEtfs(model: MarketPanelModel): MarketEtf[] {
  const rows = model.etfRows.slice(0, 3).map((row) => ({
    symbol: text(pickFirst(row, ["symbol", "code"]), "--"),
    name: text(pickFirst(row, ["name", "etf_name"]), "--"),
    action: text(pickFirst(row, ["action", "direction", "side"]), "--"),
    premium: signedPercent(pickFirst(row, ["premium_pct", "spread_pct", "edge_pct"]), "--"),
    range: signedPercent(pickFirst(row, ["range_pct", "volatility_pct", "amplitude_pct"]), "--"),
  }));
  return rows;
}

function buildReviews(model: MarketPanelModel): { midday: string; close: string } {
  const rows = model.reviewRows;
  const midday = rows.find((row) => reportSlot(row).includes("midday") || reportSlot(row).includes("午"));
  const close = rows.find((row) => reportSlot(row).includes("close") || reportSlot(row).includes("收"));
  return {
    midday: reportText(midday, "午盘复盘暂未生成。等待市场 BFF 返回真实复盘后展示。"),
    close: reportText(close, "收盘复盘暂未生成。等待收盘后生成。"),
  };
}

function reportSlot(row: Record<string, unknown>): string {
  return `${row.report_slot ?? row.slot ?? row.title ?? row.name ?? ""}`.toLowerCase();
}

function reportText(row: Record<string, unknown> | undefined, fallback: string): string {
  if (!row) return fallback;
  return text(pickFirst(row, ["overall_summary", "summary", "content", "suggestion", "status_text"]), fallback);
}

function pulseBars(model: MarketPanelModel): number[] {
  const values = model.breadthValues.map((value) => Math.max(5, Math.min(90, Math.round(Number(value) || 0))));
  return values.slice(0, 13);
}

function stringList(value: unknown): string[] {
  return readArray(value).map((item) => text(item, "")).filter(Boolean);
}

function percentNumber(value: unknown): number {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return 0;
  return Math.round(raw > 1 ? raw : raw * 100);
}

function signedPercent(value: unknown, fallback: string): string {
  if (value === undefined || value === null || value === "") return fallback;
  if (typeof value === "string") return value.includes("%") ? value : `${value}%`;
  const raw = Number(value);
  if (!Number.isFinite(raw)) return fallback;
  const pct = raw > 1 || raw < -1 ? raw : raw * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(Math.abs(pct) < 10 ? 2 : 1)}%`;
}

function bestUpdatedAt(model: MarketPanelModel): string {
  return text(
    pickFirst(model.breadth, ["updated_at", "generated_at"]) ??
      pickFirst(model.pulse, ["updated_at", "generated_at"]) ??
      pickFirst(model.sectorStrength, ["updated_at", "generated_at"]) ??
      pickFirst(model.snapshot, ["updated_at", "as_of_date"]) ??
      model.root.generated_at,
    "--",
  );
}

function syncStatus(model: MarketPanelModel): string {
  const partials = readArray(model.root.partial_errors);
  if (model.root.stale === true) return "BFF: STALE";
  if (partials.length > 0) return `BFF: PARTIAL ${partials.length}`;
  return "BFF: ACTIVE";
}

function cacheStateText(model: MarketPanelModel): string {
  const partials = readArray(model.root.partial_errors);
  if (model.root.stale === true) return "使用缓存";
  if (partials.length > 0) return "部分缓存";
  return "实时数据";
}
