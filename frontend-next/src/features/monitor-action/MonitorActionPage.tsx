import { createQuery } from "@tanstack/solid-query";
import { useLocation, useNavigate } from "@tanstack/solid-router";
import { For, Show, createEffect, createMemo, createSignal, untrack } from "solid-js";
import { apiClient } from "../../shared/api/client";
import { queryKeys } from "../../shared/api/queryKeys";
import { Icon as SharedIcon } from "../../shared/ui/Icon";
import { readArray, text, nested, pickFirst } from "../shared/dataAccess";
import { PageScaffold } from "../shared/PageScaffold";
import { QueryState } from "../shared/queryState";
import {
  createMonitorActionModel,
  type MonitorActionModel,
  type MonitorLane,
  type MonitorPriorityItem,
} from "./monitorActionModel";
import "./monitor-action.css";

type ToastState = { message: string; tone?: "ok" | "warn" };
type HoldingDraft = {
  name: string;
  symbol: string;
  costPrice: string;
  currentPrice: string;
  riskLevel: "低" | "中" | "高";
  deduct: string;
  advisePosition: string;
  expected: string;
  score: string;
};

export function MonitorActionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const routeSymbol = createMemo(() => symbolFromSearch(location().search));
  const [lane, setLane] = createSignal<MonitorLane>("all");
  const [selectedSymbol, setSelectedSymbol] = createSignal<string | undefined>(routeSymbol() || undefined);
  const [isAccordionOpen, setAccordionOpen] = createSignal(false);
  const [toast, setToast] = createSignal<ToastState | undefined>();
  const [modalOpen, setModalOpen] = createSignal(false);
  const [editingIndex, setEditingIndex] = createSignal<number | undefined>();
  const [modalDraft, setModalDraft] = createSignal<HoldingDraft | undefined>();
  const [localHoldings, setLocalHoldings] = createSignal<HoldingDraft[]>([]);
  let toastTimer: number | undefined;

  const query = createQuery(() => ({
    queryKey: queryKeys.monitorWorkspace("action"),
    queryFn: ({ signal }) => apiClient.monitorWorkspace("action", 18, { signal }),
  }));

  createEffect(() => {
    const nextSymbol = routeSymbol();
    if (nextSymbol && nextSymbol !== untrack(selectedSymbol)) setSelectedSymbol(nextSymbol);
  });

  return (
    <QueryState query={query}>
      {(data) => {
        const model = createMonitorActionModel(data, selectedSymbol);
        const visibleItems = createMemo(() => model.laneItems(lane()));
        const selected = createMemo(() => model.selected());
        const watchCards = createMemo(() => holdingCards(model, localHoldings()));
        const snapshotDate = createMemo(() => text(model.board.latest_trade_date ?? model.snapshot.latest_trade_date ?? model.root.generated_at));
        const snapshotTime = createMemo(() => timePart(model.board.updated_at ?? model.snapshot.updated_at ?? model.root.generated_at));
        const hotIndustries = createMemo(() => readArray<string>(model.board.hot_industries ?? model.snapshot.hot_industries).slice(0, 3));
        const blockRate = createMemo(() => blockRatio(model.priorityItems));
        const buyCount = createMemo(() => countLane(model.priorityItems, "buy_now"));
        const observeCount = createMemo(() => countLane(model.priorityItems, "observe"));
        const riskCount = createMemo(() => countLane(model.priorityItems, "risk"));
        const marketState = createMemo(() => compactState(model.marketStatus.badge));
        const marketRead = createMemo(() => compactMarketRead(model.marketStatus.primary));
        const direction = createMemo(() => text(model.board.directional_bias_text ?? model.board.market_direction_text, "未返回"));
        const dataState = createMemo(() => model.marketStatus.dataState || text(model.board.data_quality_text ?? model.dataQuality.status, "后台刷新中"));
        const portfolioRisk = createMemo(() => text(nested(model.board, "portfolio_risk.risk_level"), "未返回"));

        return (
          <PageScaffold page="monitor" class="monitor-action-page monitor-action-page--artifact">
            <div class="monitor-artifact__main">
              <section class="monitor-card monitor-card--live">
                <div class="monitor-alert monitor-alert--amber">
                  <MonitorIcon name="info" />
                  <div>
                    <strong>{selected()?.name || "重点标的"}监控警示：</strong>
                    <span>{selected()?.summary || "当前交易日信号处于刷新中，切勿按历史旧数据操作，待确认。"}</span>
                  </div>
                </div>

                <div class="monitor-kpi-grid">
                  <MetricTile
                    label="发布日买入/观察"
                    badge="机会分布"
                    badgeTone="green"
                    primary={`可买 ${buyCount()}`}
                    secondary={`观察 ${observeCount()}`}
                    hint="首屏查看可买和观察列表分布"
                    tone="blue"
                  />
                  <MetricTile
                    label="持仓风险控制"
                    badge="高风区"
                    badgeTone="red"
                    primary={`高风险 ${riskCount()}`}
                    secondary={`block:${blockRate()}%`}
                    hint={riskCount() ? "后端返回风险候选，请先复核风险闸门" : "后端未返回高风险候选"}
                    tone="red"
                  />
                  <MetricTile
                    label="大盘量化状态"
                    badge={marketState()}
                    badgeTone={model.marketStatus.tone}
                    primary={marketRead()}
                    secondary={compactMarketRead(model.marketStatus.secondary)}
                    hint={model.marketStatus.hint}
                    tone="amber"
                  />
                </div>
              </section>

              <section class="monitor-card monitor-card--strategy">
                <div class="monitor-strategy-body">
                  <div class="monitor-alert monitor-alert--blue">
                    <MonitorIcon name="bell" />
                    <div>
                      <strong>只做提醒，不参与生产排序</strong>
                      <span>（仅观察。信号极少，可能连续多天没有。继续作为强前排观察池）</span>
                    </div>
                  </div>

                  <div class="monitor-info-grid monitor-info-grid--five">
                    <InfoTile label="发布日方向" value={direction()} strong />
                    <InfoTile label="市场状态" value={marketState()} tone={model.marketStatus.tone === "green" ? "green" : "amber"} title={model.marketStatus.primary} />
                    <InfoTile label="热点板块" value={hotIndustries().join(" / ") || "暂无"} title={hotIndustries().join(" / ")} />
                    <InfoTile label="宽度情绪" value={text(model.board.breadth_text ?? model.board.market_breadth_text, "--")} tone="green" />
                    <InfoTile label="组合风险" value={portfolioRisk()} tone="green" />
                  </div>

                  <div class="monitor-info-grid monitor-info-grid--three">
                    <SystemTile label="快照日期" value={snapshotDate()} meta={snapshotTime()} />
                    <SystemTile label="数据状态" value={dataState()} meta={text(model.board.data_source_label, "--")} tone="amber" />
                    <SystemTile label="发布日分屏指标" value={`确认 ${buyCount()} / 观察 ${observeCount()} / 榜单 ${model.priorityItems.length}`} meta={`block / ${blockRate()}%`} />
                  </div>

                  <div class="monitor-accordion">
                    <button type="button" class="monitor-accordion__button" onClick={() => setAccordionOpen((value) => !value)}>
                      <span class="monitor-dot" />
                      <span>控制核心决策阀门</span>
                      <span class="monitor-accordion__meta">
                        <span>硬跳过 {riskCount()}</span>
                        <span>废权 0</span>
                        <MonitorIcon name="chevron-down" rotate={isAccordionOpen()} />
                      </span>
                    </button>
                    <Show when={isAccordionOpen()}>
                      <div class="monitor-accordion__body">
                        <p>
                          <strong>运行环境：</strong>
                          优先序列正在后台重建排练。避坑过滤仅作废权标识，不改变初始策略指标。
                        </p>
                      </div>
                    </Show>
                  </div>

                  <div class="monitor-warning-stack">
                    <WarningBox
                      tone="red"
                      icon="alert"
                      title={buyCount() > 0 ? "存在可行动信号：先确认关键位和仓位" : "当前无确认买入：市场风控已收紧"}
                      body={
                        buyCount() > 0
                          ? "按服务端生产优先榜读取，不改变生产排序。执行前仍需核对风险闸门和成交量。"
                          : "后端未返回确认买入候选。当前仅显示观察和复盘信息，不推导额外市场判断。"
                      }
                    />
                    <WarningBox
                      tone="amber"
                      icon="clock"
                      title={model.board.snapshot_warning ? text(model.board.snapshot_warning) : "优先榜快照已进入离线复盘区"}
                      body="按后端快照状态展示。若发布日为空或 stale，仅做离线复盘对比。"
                    />
                  </div>

                  <div class="monitor-rank-list" data-testid="monitor-priority-order-table">
                    <div class="monitor-rank-list__head">
                      <div class="monitor-tab-group" aria-label="策略分层">
                        <button type="button" class={tabClass(lane(), "all")} onClick={() => setLane("all")}>原低吸策略</button>
                        <button type="button" class={tabClass(lane(), "observe")} onClick={() => setLane("observe")}>前排加权</button>
                        <button type="button" class={tabClass(lane(), "buy_now")} onClick={() => setLane("buy_now")}>前排极精选</button>
                      </div>
                      <div class="monitor-card__actions">
                        <button type="button" class="monitor-btn monitor-btn--amber" onClick={() => showToast("榜单研判解析载入中...")}>
                          <MonitorIcon name="file" />
                          <span>解读榜单</span>
                        </button>
                        <button type="button" class="monitor-btn monitor-btn--neutral" onClick={() => void navigate({ to: "/next/playbook" })}>
                          <span>选股宝典</span>
                          <MonitorIcon name="chevron" />
                        </button>
                      </div>
                    </div>
                    <Show when={visibleItems().length > 0} fallback={<EmptyLine text="暂无生产候选。" />}>
                      <For each={visibleItems()}>
                        {(item) => (
                          <article class="monitor-rank-row" data-symbol={item.symbol}>
                            <button type="button" class="monitor-rank-row__main" onClick={() => selectSymbol(item.symbol)}>
                              <span class="monitor-rank-row__order">{String(item.order + 1).padStart(2, "0")}</span>
                              <span class="monitor-rank-row__name">
                                <strong>{item.name || item.symbol}</strong>
                                <small>#{item.symbol}</small>
                              </span>
                              <span class="monitor-rank-row__strategy">{item.strategy}</span>
                              <span class="monitor-rank-row__score">分:{item.score}</span>
                              <span class={riskBadgeClass(item)}>{item.risk || item.action}</span>
                            </button>
                            <div class="monitor-rank-row__facts">
                              <Fact label="推荐日" value={item.recommendDate} strong />
                              <Fact label="现价" value={item.price} />
                              <Fact label="建议买入区间" value={item.entryRange} />
                              <Fact label="买入信号" value={item.signal} strong />
                              <Fact label="止损" value={item.stopLoss} />
                              <Fact label="仓位" value={item.position || "--"} />
                            </div>
                            <div class="monitor-rank-row__detail">
                              <span>{item.detailLines[0] || item.summary || item.keyLevel || "后端未返回更多说明"}</span>
                              <button type="button" class="monitor-detail-btn" onClick={() => openAnalysis(item.symbol)}>
                                详情
                                <MonitorIcon name="chevron" />
                              </button>
                            </div>
                          </article>
                        )}
                      </For>
                    </Show>
                  </div>
                </div>
              </section>
            </div>

            <aside class="monitor-artifact__side">
              <section class="monitor-card monitor-card--holdings">
                <header class="monitor-card__header">
                  <div class="monitor-card__title-row">
                    <span class="monitor-icon-chip monitor-icon-chip--indigo"><MonitorIcon name="briefcase" /></span>
                    <h3>我的持仓监测</h3>
                  </div>
                  <button type="button" class="monitor-btn monitor-btn--primary" onClick={() => openHoldingModal()}>
                    <MonitorIcon name="plus" />
                    <span>录入</span>
                  </button>
                </header>

                <div class="monitor-holding-alert">
                  <span><span class="monitor-live-dot" />{selected()?.name || "重点标的"}：等待发布日信号确认</span>
                  <button type="button" onClick={() => showToast("信号仍在重新校准", "warn")}>刷新确认</button>
                </div>

                <div class="monitor-holding-list">
                  <Show when={watchCards().length > 0} fallback={<EmptyLine text="暂无自选持仓。" />}>
                    <For each={watchCards()}>
                      {(item, index) => (
                        <HoldingCard
                          item={item}
                          index={index()}
                          onDetail={() => openAnalysis(item.symbol)}
                          onEdit={() => openHoldingModal(item, index())}
                          onRemove={() => removeHolding(item, index())}
                        />
                      )}
                    </For>
                  </Show>
                </div>

                <div class="monitor-system-normal">System running normal</div>
              </section>
            </aside>

            <Show when={toast()}>
              {(state) => (
                <div class={`monitor-toast monitor-toast--${state().tone ?? "ok"}`} role="status">
                  <MonitorIcon name="check" />
                  <span>{state().message}</span>
                </div>
              )}
            </Show>

            <Show when={modalOpen()}>
              <HoldingModal
                draft={modalDraft() ?? createHoldingDraft(model.selected())}
                existing={editingIndex() === undefined ? undefined : localHoldings()[editingIndex() ?? -1]}
                onClose={() => setModalOpen(false)}
                onSave={(draft) => saveHolding(draft)}
              />
            </Show>
          </PageScaffold>
        );
      }}
    </QueryState>
  );

  function showToast(message: string, tone: ToastState["tone"] = "ok") {
    if (toastTimer !== undefined) window.clearTimeout(toastTimer);
    setToast({ message, tone });
    toastTimer = window.setTimeout(() => setToast(undefined), 2200);
  }

  function openHoldingModal(item?: HoldingCardView, index?: number) {
    setEditingIndex(index !== undefined && localHoldings()[index] ? index : undefined);
    setModalDraft(item ? holdingViewToDraft(item) : undefined);
    setModalOpen(true);
  }

  function saveHolding(draft: HoldingDraft) {
    setLocalHoldings((items) => {
      const index = editingIndex();
      if (index === undefined) return [...items, draft];
      const next = [...items];
      next[index] = draft;
      return next;
    });
    setModalOpen(false);
    showToast(`已保存更新: ${draft.name || draft.symbol}`);
  }

  function removeHolding(item: HoldingCardView, index: number) {
    setLocalHoldings((items) => {
      if (items[index]) return items.filter((_, itemIndex) => itemIndex !== index);
      return items;
    });
    showToast(`已移除持仓: ${item.name || item.symbol}`, "warn");
  }

  function openAnalysis(symbol?: string) {
    if (!symbol) return undefined;
    return navigate({ to: "/next/analysis", search: { symbol } });
  }

  function selectSymbol(symbol: string) {
    setSelectedSymbol(symbol);
    void navigate({ to: "/next/monitor", search: { symbol }, replace: true });
  }
}

function MetricTile(props: {
  label: string;
  badge: string;
  badgeTone: "green" | "red" | "amber";
  primary: string;
  secondary: string;
  hint: string;
  tone: "blue" | "red" | "amber";
}) {
  return (
    <article class={`monitor-metric monitor-metric--${props.tone}`}>
      <div class="monitor-metric__top">
        <span>{props.label}</span>
        <strong class={`monitor-badge monitor-badge--${props.badgeTone}`}>{props.badge}</strong>
      </div>
      <div class="monitor-metric__value">
        <span>{props.primary}</span>
        <Show when={props.secondary}>
          <small>{props.secondary}</small>
        </Show>
      </div>
      <p>{props.hint}</p>
    </article>
  );
}

function InfoTile(props: { label: string; value: string; tone?: "green" | "amber"; title?: string; strong?: boolean }) {
  return (
    <article class="monitor-info-tile" title={props.title}>
      <span>{props.label}</span>
      <strong class={`${props.tone ? `monitor-text--${props.tone}` : ""}${props.strong ? " monitor-info-tile__pill" : ""}`}>{props.value}</strong>
    </article>
  );
}

function SystemTile(props: { label: string; value: string; meta: string; tone?: "amber" }) {
  return (
    <article class="monitor-system-tile">
      <div>
        <span>{props.label}</span>
        <strong class={props.tone ? `monitor-text--${props.tone}` : ""}>{props.value}</strong>
      </div>
      <small>{props.meta}</small>
    </article>
  );
}

function WarningBox(props: { tone: "red" | "amber"; icon: MonitorIconName; title: string; body: string }) {
  return (
    <article class={`monitor-warning monitor-warning--${props.tone}`}>
      <MonitorIcon name={props.icon} />
      <div>
        <strong>{props.title}</strong>
        <span>{props.body}</span>
      </div>
    </article>
  );
}

function Fact(props: { label: string; value: string; strong?: boolean }) {
  return (
    <span class={`monitor-rank-fact${props.strong ? " monitor-rank-fact--strong" : ""}`}>
      <small>{props.label}</small>
      <strong>{props.value || "--"}</strong>
    </span>
  );
}

type HoldingCardView = {
  name: string;
  symbol: string;
  costPrice: string;
  currentPrice: string;
  change: string;
  riskLevel: "低" | "中" | "高";
  deduct: string;
  advisePosition: string;
  expected: string;
  score: string;
  raw?: Record<string, unknown>;
};

function HoldingCard(props: {
  item: HoldingCardView;
  index: number;
  onDetail: () => void;
  onEdit: () => void;
  onRemove: () => void;
}) {
  const item = () => props.item;
  const changeNum = () => Number(String(item().change).replace("%", ""));
  return (
    <article class={`monitor-holding-card${item().riskLevel === "高" ? " monitor-holding-card--risk" : ""}`}>
      <div class="monitor-holding-card__title">
        <div>
          <strong>{item().name || item().symbol}</strong>
          <span>#{item().symbol}</span>
          <small>成本 {item().costPrice}</small>
        </div>
        <em>分:{item().score}</em>
      </div>
      <div class="monitor-holding-card__quote">
        <span>{item().currentPrice}</span>
        <strong class={changeNum() >= 0 ? "monitor-text--red" : "monitor-text--green"}>{signedPct(item().change)}</strong>
        <em class={item().riskLevel === "高" ? "monitor-risk-label monitor-risk-label--high" : "monitor-risk-label"}>风:{item().riskLevel}</em>
        <small>扣:{item().deduct}%</small>
      </div>
      <div class="monitor-position-row">
        <span>建议仓位:</span>
        <div class="monitor-position-bar"><i style={{ width: item().advisePosition }} /></div>
        <strong>{item().advisePosition}</strong>
      </div>
      <div class="monitor-holding-card__actions">
        <button type="button" onClick={props.onDetail}>详情</button>
        <button type="button" onClick={props.onEdit}>编辑</button>
        <button type="button" onClick={props.onRemove}>移除</button>
        <span>预期:{item().expected}%</span>
      </div>
    </article>
  );
}

function HoldingModal(props: {
  draft: HoldingDraft;
  existing?: HoldingDraft;
  onClose: () => void;
  onSave: (draft: HoldingDraft) => void;
}) {
  const [draft, setDraft] = createSignal<HoldingDraft>(props.existing ?? props.draft);
  const update = (key: keyof HoldingDraft, value: string) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  return (
    <div class="monitor-modal" role="dialog" aria-modal="true" aria-label="录入持仓">
      <div class="monitor-modal__panel">
        <header>
          <strong>录入 / 修改持仓股票</strong>
          <button type="button" onClick={props.onClose} aria-label="关闭"><MonitorIcon name="x" /></button>
        </header>
        <div class="monitor-modal__body">
          <Field label="股票名称" value={draft().name} onInput={(value) => update("name", value)} placeholder="例如: 顺钠股份" />
          <div class="monitor-modal__grid">
            <Field label="代码" value={draft().symbol} onInput={(value) => update("symbol", value)} placeholder="如: 000533" />
            <Field label="质量分" value={draft().score} onInput={(value) => update("score", value)} placeholder="0" />
          </div>
          <div class="monitor-modal__grid">
            <Field label="成本价" value={draft().costPrice} onInput={(value) => update("costPrice", value)} placeholder="13.539" />
            <Field label="当前价" value={draft().currentPrice} onInput={(value) => update("currentPrice", value)} placeholder="11.310" />
          </div>
          <div class="monitor-modal__grid">
            <label class="monitor-field">
              <span>风险评级</span>
              <select value={draft().riskLevel} onInput={(event) => update("riskLevel", event.currentTarget.value)}>
                <option value="低">低</option>
                <option value="中">中</option>
                <option value="高">高</option>
              </select>
            </label>
            <Field label="扣期 (%)" value={draft().deduct} onInput={(value) => update("deduct", value)} placeholder="0.0" />
          </div>
          <div class="monitor-modal__grid">
            <Field label="建议仓位" value={draft().advisePosition} onInput={(value) => update("advisePosition", value)} placeholder="如: 0%" />
            <Field label="预期回报" value={draft().expected} onInput={(value) => update("expected", value)} placeholder="如: 0.00" />
          </div>
        </div>
        <footer>
          <button type="button" class="monitor-btn monitor-btn--ghost" onClick={props.onClose}>取消</button>
          <button type="button" class="monitor-btn monitor-btn--primary" onClick={() => props.onSave(draft())}>记录意图</button>
        </footer>
      </div>
    </div>
  );
}

function Field(props: { label: string; value: string; placeholder: string; onInput: (value: string) => void }) {
  return (
    <label class="monitor-field">
      <span>{props.label}</span>
      <input value={props.value} placeholder={props.placeholder} onInput={(event) => props.onInput(event.currentTarget.value)} />
    </label>
  );
}

function EmptyLine(props: { text: string }) {
  return <div class="monitor-empty-line">{props.text}</div>;
}

type MonitorIconName =
  | "activity"
  | "refresh"
  | "database"
  | "info"
  | "file"
  | "chevron"
  | "bell"
  | "chevron-down"
  | "alert"
  | "clock"
  | "briefcase"
  | "plus"
  | "check"
  | "x";

function MonitorIcon(props: { name: MonitorIconName; spin?: boolean; rotate?: boolean }) {
  return (
    <SharedIcon
      name={props.name}
      class={`monitor-icon${props.rotate ? " monitor-icon--rotate" : ""}`}
      spin={props.spin}
      spinClass="monitor-icon--spin"
    />
  );
}

function tabClass(active: MonitorLane, tab: MonitorLane) {
  return `monitor-tab${active === tab ? " monitor-tab--active" : ""}`;
}

function riskBadgeClass(item: MonitorPriorityItem) {
  const raw = `${item.risk} ${item.action}`.toLowerCase();
  const tone = raw.includes("风险") || raw.includes("block") || raw.includes("avoid") ? "red" : raw.includes("买") || raw.includes("buy") ? "green" : "amber";
  return `monitor-mini-badge monitor-mini-badge--${tone}`;
}

function countLane(items: MonitorPriorityItem[], lane: MonitorLane): number {
  return items.filter((item) => item.lane === lane).length;
}

function blockRatio(items: MonitorPriorityItem[]) {
  if (!items.length) return 0;
  return Math.round((countLane(items, "risk") / items.length) * 100);
}

function holdingCards(model: MonitorActionModel, localHoldings: HoldingDraft[]): HoldingCardView[] {
  const local = localHoldings.map(draftToHoldingView);
  const remote = (model.watchItems.length ? model.watchItems : model.priorityItems.slice(0, 3)).map(itemToHoldingView);
  return [...local, ...remote].slice(0, 8);
}

function itemToHoldingView(item: MonitorPriorityItem): HoldingCardView {
  const raw = item.raw;
  return {
    name: item.name,
    symbol: item.symbol,
    costPrice: text(pickFirst(raw, ["cost_price", "avg_cost", "costPrice", "price"]), item.price),
    currentPrice: item.price,
    change: text(pickFirst(raw, ["change_pct", "pct_chg", "change"]), item.change || "0"),
    riskLevel: parseRiskLevel(item.risk),
    deduct: text(pickFirst(raw, ["deduct_pct", "risk_deduction", "deduct"]), "0.00"),
    advisePosition: normalizePosition(item.position),
    expected: text(pickFirst(raw, ["expected_return_pct", "expected_pct", "expected"]), "0.00"),
    score: item.score,
    raw,
  };
}

function draftToHoldingView(draft: HoldingDraft): HoldingCardView {
  return {
    name: draft.name,
    symbol: draft.symbol,
    costPrice: draft.costPrice,
    currentPrice: draft.currentPrice,
    change: calculateChange(draft.costPrice, draft.currentPrice),
    riskLevel: draft.riskLevel,
    deduct: draft.deduct,
    advisePosition: draft.advisePosition,
    expected: draft.expected,
    score: draft.score,
  };
}

function createHoldingDraft(selected?: MonitorPriorityItem): HoldingDraft {
  const view = selected ? itemToHoldingView(selected) : undefined;
  return view ? holdingViewToDraft(view) : {
    name: "",
    symbol: "",
    costPrice: "",
    currentPrice: "",
    riskLevel: "低",
    deduct: "0.00",
    advisePosition: "0%",
    expected: "0.00",
    score: "0",
  };
}

function holdingViewToDraft(view: HoldingCardView): HoldingDraft {
  return {
    name: view.name,
    symbol: view.symbol,
    costPrice: view.costPrice,
    currentPrice: view.currentPrice,
    riskLevel: view.riskLevel,
    deduct: view.deduct,
    advisePosition: view.advisePosition,
    expected: view.expected,
    score: view.score,
  };
}

function parseRiskLevel(value: string): "低" | "中" | "高" {
  if (value.includes("高") || value.toLowerCase().includes("risk") || value.toLowerCase().includes("block")) return "高";
  if (value.includes("中") || value.includes("谨慎")) return "中";
  return "低";
}

function normalizePosition(value: string): string {
  const raw = value.trim();
  if (!raw || raw === "--") return "0%";
  const match = raw.match(/(\d+(?:\.\d+)?)\s*%/);
  if (match) return `${match[1]}%`;
  const parsed = Number(raw);
  if (Number.isFinite(parsed)) return `${Math.min(100, Math.max(0, parsed <= 1 ? parsed * 100 : parsed)).toFixed(0)}%`;
  return "0%";
}

function calculateChange(costText: string, priceText: string): string {
  const cost = Number(costText);
  const price = Number(priceText);
  if (!Number.isFinite(cost) || !Number.isFinite(price) || cost <= 0) return "0.00";
  return (((price - cost) / cost) * 100).toFixed(2);
}

function signedPct(value: string): string {
  const normalized = String(value || "0").replace("%", "");
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return value || "0.00%";
  return `${parsed >= 0 ? "+" : ""}${parsed.toFixed(2)}%`;
}

function timePart(value: unknown): string {
  const raw = text(value, "");
  const match = raw.match(/(\d{2}:\d{2}:\d{2})/);
  return match?.[1] ?? "--:--:--";
}

function compactState(value: string): string {
  const raw = value.trim();
  if (!raw || raw === "--") return "未返回";
  if (raw.includes("下跌") || raw.includes("退潮")) return "下跌退潮";
  if (raw.includes("震荡")) return "震荡观察";
  if (raw.includes("上行") || raw.includes("强势") || raw.includes("进攻")) return "强势上行";
  if (raw.length <= 8) return raw;
  return `${raw.slice(0, 8)}...`;
}

function compactMarketRead(value: string): string {
  const raw = value.trim();
  if (!raw || raw === "--") return "未返回";
  if (raw.length <= 14) return raw;
  return `${raw.slice(0, 14)}...`;
}

function symbolFromSearch(search: unknown): string {
  const value = search && typeof search === "object" ? (search as Record<string, unknown>).symbol : undefined;
  if (typeof value !== "string" && typeof value !== "number") return "";
  const symbol = String(value).trim().replace(/\D/g, "").slice(0, 6);
  return symbol.length === 6 ? symbol : "";
}
