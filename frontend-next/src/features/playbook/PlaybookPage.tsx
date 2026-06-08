import { createQuery } from "@tanstack/solid-query";
import { useLocation, useNavigate } from "@tanstack/solid-router";
import { For, Match, Show, Switch, createEffect, createMemo, createSignal, untrack } from "solid-js";
import { apiClient } from "../../shared/api/client";
import { errorMessage } from "../../shared/api/errors";
import { queryKeys } from "../../shared/api/queryKeys";
import { normalizedStrategyKey } from "../../shared/config/strategyCommands";
import { PageScaffold } from "../shared/PageScaffold";
import { numberText, readRecord } from "../shared/dataAccess";
import {
  attributionLines,
  candidateFamilies,
  DEFAULT_PLAYBOOK_STRATEGY,
  detailRows,
  loadPlaybookDataset,
  mergePlaybookQuotes,
  performanceSummary,
  playbookTradeDate,
  quoteStatus,
  selectedCandidate,
  shadowLifecycle,
  strategyTabs,
  type PlaybookCandidate,
  type PlaybookFamily,
} from "./playbookModel";
import "./playbookSlice.css";

type StockLane = "buyable" | "observing" | "pending" | "discarded";

export function PlaybookPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const routeStrategy = createMemo(() => normalizedStrategyKey(readSearchValue(location().search, "strategy")) ?? DEFAULT_PLAYBOOK_STRATEGY);
  const routeSymbol = createMemo(() => symbolFromSearch(location().search));
  const [strategy, setStrategy] = createSignal(routeStrategy());
  const [selectedSymbol, setSelectedSymbol] = createSignal<string | null>(routeSymbol() || null);
  const [shadowMessage, setShadowMessage] = createSignal("");
  const [activeLane, setActiveLane] = createSignal<StockLane>("buyable");
  const [detailOpen, setDetailOpen] = createSignal(false);
  const query = createQuery(() => ({
    queryKey: queryKeys.lowBuyScreener({ strategy: strategy(), limit: 36, scan_limit: 36, include_history: true }),
    queryFn: ({ signal }) => loadPlaybookDataset(strategy(), { signal }, { includeQuotes: false }),
  }));
  const baseDataset = () => query.data ?? null;
  const quoteSymbols = createMemo(() => candidateFamilies(baseDataset()).flatMap((family) => family.items.map((item) => item.symbol)).slice(0, 20));
  const liveQuotesQuery = createQuery(() => ({
    queryKey: queryKeys.lowBuyQuotes(quoteSymbols(), strategy()),
    queryFn: ({ signal }) => apiClient.lowBuyQuotes(quoteSymbols(), strategy(), { signal }),
    enabled: quoteSymbols().length > 0,
  }));
  const dataset = createMemo(() => mergePlaybookQuotes(baseDataset(), liveQuotesQuery.data));
  const isRefreshing = createMemo(() => query.isFetching || liveQuotesQuery.isFetching);
  const tabs = createMemo(() => strategyTabs(dataset()).map((item) => ({ key: item.key, label: item.label })));
  const activeTabs = createMemo(() => tabs().length ? tabs() : fallbackStrategyTabs);
  const families = createMemo(() => candidateFamilies(dataset()));
  const activeFamily = createMemo<PlaybookFamily | null>(() => families()[0] ?? null);
  const candidates = createMemo(() => families().flatMap((family) => family.items));
  const selected = createMemo(() => selectedCandidate(dataset(), selectedSymbol()));
  const performance = createMemo(() => performanceSummary(activeFamily()));
  const laneItems = createMemo(() => laneCandidates(candidates(), activeLane()));
  const focusCandidate = createMemo(() => selected() ?? candidates()[0] ?? null);

  createEffect(() => {
    const first = selected();
    if (!selectedSymbol() && first) setSelectedSymbol(first.symbol);
  });

  createEffect(() => {
    const nextStrategy = routeStrategy();
    if (nextStrategy !== untrack(strategy)) {
      setStrategy(nextStrategy);
      setSelectedSymbol(routeSymbol() || null);
      setShadowMessage("");
    }
  });

  createEffect(() => {
    const nextSymbol = routeSymbol();
    if (nextSymbol && nextSymbol !== untrack(selectedSymbol)) setSelectedSymbol(nextSymbol);
  });

  return (
    <PageScaffold page="playbook" class="playbook-workflow playbook-clean-page">
      <section class="playbook-shell" aria-label="选股宝典">
        <header class="playbook-hero-card">
          <div class="playbook-hero-card__main">
            <div class="playbook-title-row">
              <h2>{currentStrategyLabel()}</h2>
              <span class="playbook-luck-pill"><strong>红运</strong><em>发布日守正待机</em><small>签</small></span>
            </div>
            <p>{strategyDescription(currentStrategyLabel())}</p>
          </div>
          <div class="playbook-hero-card__actions">
            <button type="button" class="playbook-btn playbook-btn--primary" onClick={() => void query.refetch()} data-testid="playbook-refresh">
              {isRefreshing() ? "刷新中" : "刷新全量"}
            </button>
          </div>

          <div class="playbook-param-grid">
            <ParamCard label="确认可买数量" value={String(laneCandidates(candidates(), "buyable").length)} suffix="只" />
            <ParamCard label="全量深筛状态" value={isRefreshing() ? "刷新中" : query.error ? "异常" : "已完成"} suffix={query.error ? "!" : "100%"} tone={query.error ? "risk" : "ok"} />
            <ParamCard label="数据状态" value={quoteStatus(dataset()) === "--" ? "实时就绪" : "已对齐"} suffix={quoteStatus(dataset())} tone="ok" />
            <ParamCard label="当前交易日" value={playbookTradeDate(dataset())} suffix="后端发布" />
          </div>

          <div class="playbook-strategy-tabs" role="tablist" aria-label="选股策略">
            <For each={activeTabs()}>
              {(item) => (
                <button
                  type="button"
                  class={`playbook-strategy-tab${strategy() === item.key ? " playbook-strategy-tab--active" : ""}`}
                  onClick={() => switchStrategy(item.key)}
                >
                  {item.label}
                </button>
              )}
            </For>
          </div>
        </header>

        <Switch>
          <Match when={query.error}>
            <div class="playbook-alert playbook-alert--error">接口暂不可用：{errorMessage(query.error)}</div>
          </Match>
          <Match when={query.isPending && !query.data}>
            <div class="playbook-alert">正在加载选股宝典数据</div>
          </Match>
        </Switch>

        <div class="playbook-layout-grid">
          <aside class="playbook-side-stack">
            <section class="playbook-panel">
              <div class="playbook-panel__header">
                <h3>最近表现</h3>
                <span>近5日统计</span>
              </div>
              <div class="playbook-status-box">
                <span>当前策略</span>
                <strong>{currentStrategyLabel()}</strong>
                <span>加载状态</span>
                <strong>{query.error ? "接口异常" : "已成功加载全量数据"}</strong>
              </div>
              <div class="playbook-mini-metrics">
                <MiniMetric label="5日达标率" value={metricValue(performance(), "命中率", "样本不足")} />
                <MiniMetric label="平均收益" value={metricValue(performance(), "平均收益", "--")} />
                <MiniMetric label="赚亏比" value={metricValue(performance(), "净胜率", "--")} />
              </div>
              <p class="playbook-note"><strong>样本说明：</strong>当前仅计算确定买入且归因的样本；观察票和接近买点票不计入胜率。</p>
              <button type="button" class="playbook-accordion-btn" onClick={() => setDetailOpen((value) => !value)}>
                样本、胜率与归因明细 <span>{detailOpen() ? "收起" : "展开"}</span>
              </button>
              <Show when={detailOpen()}>
                <div class="playbook-detail-lines">
                  <LineMetric label="历史总计买入样本" value={metricValue(performance(), "样本", "0")} />
                  <LineMetric label="完成归因胜率" value={metricValue(performance(), "命中率", "0.00%")} />
                  <LineMetric label="最大归因回撤" value={metricValue(performance(), "最大回撤", "0.00%")} />
                  <LineMetric label="近一月超额收益" value={metricValue(performance(), "平均收益", "0.00%")} />
                </div>
              </Show>
            </section>

            <section class="playbook-focus-card">
              <div class="playbook-focus-card__header">
                <h3>发布日注目核心标的</h3>
                <span>FOCUS</span>
              </div>
              <Show
                when={focusCandidate()}
                fallback={
                  <>
                    <p>当前策略暂无主看标的。</p>
                    <div class="playbook-focus-actions">
                      <button type="button" onClick={() => void openAnalysis(selectedSymbol() || undefined)} data-testid="playbook-open-analysis">打开量化分析</button>
                    </div>
                  </>
                }
              >
                {(candidate) => (
                  <>
                    <div class="playbook-focus-stock" data-testid="playbook-detail">
                      <div>
                        <strong>{candidate().name || candidate().symbol}</strong>
                        <span>{candidate().symbol}</span>
                      </div>
                      <div>
                        <em>{candidate().changeText || "--"}</em>
                        <small>{candidate().action}</small>
                      </div>
                    </div>
                    <div class="playbook-focus-actions">
                      <button type="button" onClick={() => void openAnalysis(candidate().symbol)} data-testid="playbook-open-analysis">打开量化分析</button>
                      <button type="button" onClick={() => void blockLifecycle(candidate().symbol)}>记录状态</button>
                    </div>
                  </>
                )}
              </Show>
              <Show when={shadowMessage()}><p class="playbook-shadow">{shadowMessage()}</p></Show>
            </section>

            <section class="playbook-panel">
              <div class="playbook-panel__header">
                <h3>真实成交实盘指标</h3>
              </div>
              <div class="playbook-real-metrics">
                <MiniMetric label="真实成交样本" value={metricValue(performance(), "样本", "0")} />
                <MiniMetric label="5日达标率" value={metricValue(performance(), "命中率", "样本不足")} />
                <MiniMetric label="平均收益" value={metricValue(performance(), "平均收益", "--")} />
                <MiniMetric label="最大回撤" value={metricValue(performance(), "净胜率", "--")} />
              </div>
            </section>
          </aside>

          <section class="playbook-board playbook-candidates-panel">
            <div class="playbook-stock-tabs">
              <div class="playbook-stock-tabs__buttons" role="tablist" aria-label="候选分层">
                <For each={laneTabs}>
                  {(item) => (
                    <button type="button" class={`playbook-stock-tab${activeLane() === item.key ? " playbook-stock-tab--active" : ""}`} onClick={() => setActiveLane(item.key)}>
                      <span>{item.label}</span>
                      <em>{laneCandidates(candidates(), item.key).length}</em>
                    </button>
                  )}
                </For>
              </div>
              <span>实时策略刷新流转</span>
            </div>

            <div class="playbook-board__body">
              <div class="playbook-list-title">
                <div>
                  <h3>候选分层</h3>
                  <h4>{laneTitle(activeLane())}</h4>
                  <p>{laneDescription(activeLane())}</p>
                </div>
                <span>更新时间: {quoteStatus(dataset())}</span>
              </div>

              <Show
                when={laneItems().length > 0}
                fallback={
                  <div class="playbook-empty-state">
                    <div>?</div>
                    <h5>当前没有可以直接执行的股票</h5>
                    <p>策略引擎正在计算，当前策略中尚未侦测到触发买入阈值的标的。</p>
                  </div>
                }
              >
                <div class="playbook-table-wrap">
                  <table class="playbook-stock-table">
                    <thead>
                      <tr>
                        <th>代码 & 简称</th>
                        <th>最新价</th>
                        <th>日涨跌幅</th>
                        <th>承接位</th>
                        <th>状态触发</th>
                        <th>操作建议</th>
                      </tr>
                    </thead>
                    <tbody>
                      <For each={laneItems()}>
                        {(item) => (
                          <tr class={selected()?.symbol === item.symbol ? "playbook-stock-row--active" : ""}>
                            <td>
                              <button type="button" class="playbook-stock-name" onClick={() => selectCandidate(item.symbol)}>
                                <strong>{item.name || item.symbol}</strong>
                                <span>{item.symbol}</span>
                              </button>
                            </td>
                            <td>{item.price}</td>
                            <td class={item.changeText.startsWith("-") ? "playbook-text--down" : "playbook-text--up"}>{item.changeText || "--"}</td>
                            <td>{numberText(readRecord(item.raw).entry_zone_low, "--")}</td>
                            <td><span class="playbook-state-pill">{item.riskText || item.details || "--"}</span></td>
                            <td>
                              <div class="playbook-row-actions">
                                <button type="button" onClick={() => selectCandidate(item.symbol)}>详情</button>
                                <button type="button" onClick={() => void openAnalysis(item.symbol)}>分析</button>
                                <button type="button" onClick={() => void blockLifecycle(item.symbol)}>记录状态</button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </For>
                    </tbody>
                  </table>
                </div>
              </Show>

              <div class="playbook-summary-strip">
                <div>
                  <h3>归因</h3>
                  <For each={attributionLines(selected())} fallback={<p>暂无归因说明</p>}>
                    {(line) => <p>{line}</p>}
                  </For>
                </div>
                <div>
                  <h3>候选约束</h3>
                  <div class="playbook-constraint-grid">
                    <For each={detailRows(selected())}>
                      {([label, value]) => <LineMetric label={label} value={value} />}
                    </For>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </section>
    </PageScaffold>
  );

  async function blockLifecycle(symbol = selected()?.symbol) {
    if (!symbol) return;
    const result = await shadowLifecycle(symbol, "blocked");
    setShadowMessage(result.mode === "live" ? "状态更新已发送" : "状态更新已记录");
  }

  function openAnalysis(symbol?: string) {
    if (!symbol) return undefined;
    return navigate({ to: "/next/analysis", search: { symbol } });
  }

  function selectCandidate(symbol: string) {
    setSelectedSymbol(symbol);
    setShadowMessage("");
    return navigate({ to: "/next/playbook", search: { strategy: strategy(), symbol }, replace: true });
  }

  function switchStrategy(nextStrategy: string) {
    setStrategy(nextStrategy);
    setSelectedSymbol(null);
    setShadowMessage("");
  }

  function currentStrategyLabel() {
    return activeTabs().find((item) => item.key === strategy())?.label ?? strategy();
  }
}

function ParamCard(props: { label: string; value: string; suffix?: string; tone?: "ok" | "risk" }) {
  return (
    <div class="playbook-param-card">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
      <small class={props.tone ? `playbook-param-card__suffix--${props.tone}` : ""}>{props.suffix}</small>
    </div>
  );
}

function MiniMetric(props: { label: string; value: string }) {
  return (
    <div class="playbook-mini-metric">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function LineMetric(props: { label: string; value: string }) {
  return (
    <div class="playbook-line-metric">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}

function readSearchValue(search: unknown, key: string): unknown {
  return search && typeof search === "object" ? (search as Record<string, unknown>)[key] : undefined;
}

function symbolFromSearch(search: unknown): string {
  const value = readSearchValue(search, "symbol");
  if (typeof value !== "string" && typeof value !== "number") return "";
  const symbol = String(value).trim().replace(/\D/g, "").slice(0, 6);
  return symbol.length === 6 ? symbol : "";
}

function metricValue(items: Array<{ label: string; value: string }>, label: string, fallback: string) {
  return items.find((item) => item.label === label)?.value ?? fallback;
}

function laneCandidates(items: PlaybookCandidate[], lane: StockLane): PlaybookCandidate[] {
  if (lane === "buyable") return items.filter((item) => laneText(item).includes("buy") || item.action.includes("买") || item.action.includes("立即"));
  if (lane === "observing") return items.filter((item) => laneText(item).includes("watch") || laneText(item).includes("wait") || item.action.includes("观察") || item.action.includes("等待"));
  if (lane === "pending") return items.filter((item) => laneText(item).includes("pending") || laneText(item).includes("confirm") || item.action.includes("确认") || item.details.includes("确认"));
  return items.filter((item) => laneText(item).includes("avoid") || laneText(item).includes("give_up") || item.riskText.includes("放弃") || item.riskText.includes("风险") || item.details.includes("放弃"));
}

function laneText(item: PlaybookCandidate): string {
  return `${item.lane} ${item.laneText}`.toLowerCase();
}

function laneTitle(lane: StockLane): string {
  const titles: Record<StockLane, string> = {
    buyable: "确认买入候选",
    observing: "核心观察阶段标的",
    pending: "等待条件确认标的",
    discarded: "观察 / 暂时放弃池",
  };
  return titles[lane];
}

function laneDescription(lane: StockLane): string {
  const descriptions: Record<StockLane, string> = {
    buyable: "符合当前盘面量能条件及反弹试探承接位的核心股",
    observing: "符合回调形态，资金持续加仓，正处于重要强力支撑位以上的标的",
    pending: "日内量能尚有不足或尚未突破核心阻力，需等待探底企稳再行确认",
    discarded: "筹码已经松散跌破防守均线，建议暂时不盲目抄底的防御标的",
  };
  return descriptions[lane];
}

function strategyDescription(label: string): string {
  const descriptions: Record<string, string> = {
    首板回调: "策略原理：首板回调，只看启动后第一次承接。寻找市场核心人气股首个涨停板后，首次回调稳健承接的低吸良机。",
    量能低吸: "策略原理：成交量极度萎缩至近20日均量以下，且价格处于核心强支撑带。",
    收盘强势承接: "策略原理：寻找尾盘半小时异常大单承接且全天保持高强度的强势票。",
  };
  return descriptions[label] ?? "策略原理：按服务端策略元数据展示，信号只做观察与复盘参考。";
}

const laneTabs: Array<{ key: StockLane; label: string }> = [
  { key: "buyable", label: "可买" },
  { key: "observing", label: "观察" },
  { key: "pending", label: "等确认" },
  { key: "discarded", label: "观察/放弃" },
];

const fallbackStrategyTabs = [
  { key: "first_board", label: "首板回调" },
  { key: "volume_low_buy", label: "量能低吸" },
  { key: "close_strength", label: "收盘强势承接" },
];
