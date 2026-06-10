import { apiClient, type RequestJsonOptions } from "../../shared/api/client";
import { mutationClient } from "../../shared/api/mutations";
import type { StockCardItem } from "../../shared/ui/StockCard";
import { nested, numberText, pctText, pickFirst, readArray, readRecord, text } from "../shared/dataAccess";

export interface PlaybookDataset {
  screener: unknown;
  priorityBoard: unknown;
  quotes: unknown;
  strategies: unknown;
  meta: unknown;
  loadedAt: string;
}

export interface PlaybookStrategyTab {
  key: string;
  label: string;
  layer: string;
  status: string;
}

export interface PlaybookCandidate {
  symbol: string;
  name: string;
  lane: string;
  laneText: string;
  signalState: string;
  simpleBucket: string;
  action: string;
  price: string;
  score: number;
  scoreText: string;
  changeText: string;
  riskText: string;
  recommendDate: string;
  details: string;
  strategy: string;
  raw: Record<string, unknown>;
}

export interface PlaybookFamily {
  key: string;
  title: string;
  items: PlaybookCandidate[];
  performance: Record<string, unknown>;
}

export interface PlaybookDateGroup {
  key: "today" | "yesterday" | "history";
  title: string;
  hint: string;
  items: PlaybookCandidate[];
}

export const DEFAULT_PLAYBOOK_STRATEGY = "first_board";
export const PLAYBOOK_FAST_TIMEOUT_MS = 8_000;
export const PLAYBOOK_DEEP_TIMEOUT_MS = 20_000;

export async function loadPlaybookFastDataset(init: RequestJsonOptions = {}): Promise<PlaybookDataset> {
  const priorityBoard = await apiClient.lowBuyPriorityBoard(30, "baseline", "cache", withTimeout(init, PLAYBOOK_FAST_TIMEOUT_MS));
  return emptyPlaybookDataset({ priorityBoard });
}

export async function loadPlaybookConfig(init: RequestJsonOptions = {}): Promise<Pick<PlaybookDataset, "strategies" | "meta">> {
  const requestInit = withTimeout(init, PLAYBOOK_FAST_TIMEOUT_MS);
  const [strategies, meta] = await Promise.all([
    apiClient.lowBuyStrategies(requestInit),
    apiClient.strategiesMeta(requestInit),
  ]);
  return { strategies, meta };
}

export async function loadPlaybookDeepScreener(strategy: string, init: RequestJsonOptions = {}): Promise<Pick<PlaybookDataset, "screener">> {
  const screener = await apiClient.lowBuyScreener(
    { strategy, limit: 36, scan_limit: 36, scan_mode: "full", include_history: true },
    withTimeout(init, PLAYBOOK_DEEP_TIMEOUT_MS),
  );
  return { screener };
}

export async function loadPlaybookDataset(strategy: string, init: RequestJsonOptions = {}, options: { includeQuotes?: boolean } = {}): Promise<PlaybookDataset> {
  const [screener, priorityBoard, strategies, meta] = await Promise.all([
    apiClient.lowBuyScreener({ strategy, limit: 36, scan_limit: 36, include_history: true }, init),
    apiClient.lowBuyPriorityBoard(30, "baseline", "cache", init),
    apiClient.lowBuyStrategies(init),
    apiClient.strategiesMeta(init),
  ]);
  const symbols = playbookCandidates({ screener, priorityBoard } as PlaybookDataset).slice(0, 20).map((item) => item.symbol);
  const quotes = options.includeQuotes === false ? undefined : await apiClient.lowBuyQuotes(symbols, strategy, init);
  return { screener, priorityBoard, quotes, strategies, meta, loadedAt: new Date().toLocaleTimeString("zh-CN", { hour12: false }) };
}

export function mergePlaybookConfig(data: PlaybookDataset | null, config: Pick<PlaybookDataset, "strategies" | "meta"> | undefined): PlaybookDataset | null {
  if (!data || config === undefined) return data;
  return { ...data, strategies: config.strategies, meta: config.meta };
}

export function mergePlaybookScreener(data: PlaybookDataset | null, screener: Pick<PlaybookDataset, "screener"> | undefined): PlaybookDataset | null {
  if (!data || screener === undefined) return data;
  return { ...data, screener: screener.screener };
}

export function strategyTabs(data: PlaybookDataset | null): PlaybookStrategyTab[] {
  const governance = readRecord(data?.strategies);
  const meta = readRecord(data?.meta);
  const fromGovernance = readArray<Record<string, unknown>>(governance.items).map((item) => ({
    key: text(item.strategy_key),
    label: text(item.strategy_title ?? item.strategy_key),
    layer: text(item.layer ?? item.tier),
    status: text(item.status_text ?? item.status),
  }));
  const fromMeta = readArray<Record<string, unknown>>(meta.strategies).map((item) => ({
    key: text(item.key),
    label: text(item.display_name ?? item.name ?? item.key),
    layer: text(item.tier ?? item.category_key),
    status: text(item.promotion_status_text ?? item.probe_status),
  }));
  const merged = [...fromGovernance, ...fromMeta].filter((item) => item.key !== "--");
  return uniqueByKey(merged).slice(0, 8);
}

export function boardMetrics(data: PlaybookDataset | null) {
  const board = boardRoot(data);
  const risk = readRecord(board.portfolio_risk);
  return [
    { label: "立即处理", value: text(board.immediate_count ?? countByLane(data, "buy_now"), "0"), tone: "up" as const },
    { label: "观察", value: text(board.focus_count ?? board.track_count ?? countByLane(data, "wait_price"), "0") },
    { label: "总候选", value: text(board.total_candidates ?? candidatesFromPriority(data?.priorityBoard).length, "0") },
    { label: "组合上限", value: pctText(risk.recommended_total_cap_pct, "--") },
    { label: "市场状态", value: text(board.market_state_text, "--") },
    { label: "风险", value: text(risk.risk_level, "--") },
  ];
}

export function quoteStatus(data: PlaybookDataset | null): string {
  const quotes = readRecord(data?.quotes);
  return text(quotes.updated_at ?? quotes.quote_timestamp ?? data?.loadedAt, "--");
}

export function playbookTradeDate(data: PlaybookDataset | null): string {
  const screener = readRecord(data?.screener);
  const board = boardRoot(data);
  return text(screener.latest_trade_date ?? board.latest_trade_date ?? board.latest_available_trade_date, "--");
}

export function mergePlaybookQuotes(data: PlaybookDataset | null, quotes: unknown): PlaybookDataset | null {
  if (!data || quotes === undefined) return data;
  return { ...data, quotes };
}

export function candidateFamilies(data: PlaybookDataset | null): PlaybookFamily[] {
  const board = candidateRoot(data);
  const quotes = quoteBySymbol(data);
  const sections = readArray<Record<string, unknown>>(board.family_sections);
  if (sections.length) {
    return sections.map((section) => ({
      key: text(section.family_key),
      title: text(section.family_text ?? section.family_key),
      items: readArray<Record<string, unknown>>(section.items).map((item) => candidateFromRecord(item, quotes)),
      performance: readRecord(section.performance),
    }));
  }
  const groups = new Map<string, PlaybookCandidate[]>();
  playbookCandidates(data, quotes).forEach((candidate) => {
    const key = candidate.lane || "baseline";
    groups.set(key, [...(groups.get(key) ?? []), candidate]);
  });
  return Array.from(groups, ([key, items]) => ({ key, title: text(items[0]?.laneText, key), items, performance: {} }));
}

export function simpleBuckets(data: PlaybookDataset | null) {
  return readArray<Record<string, unknown>>(boardRoot(data).simple_buckets);
}

export function selectedCandidate(data: PlaybookDataset | null, symbol: string | null): PlaybookCandidate | null {
  const candidates = candidateFamilies(data).flatMap((family) => family.items);
  return candidates.find((candidate) => candidate.symbol === symbol) ?? candidates[0] ?? null;
}

export function stockCardItem(candidate: PlaybookCandidate): StockCardItem {
  return {
    symbol: candidate.symbol,
    name: candidate.name,
    priceText: candidate.price,
    changeText: candidate.changeText,
    scoreText: candidate.scoreText,
    actionText: candidate.action,
    riskText: candidate.riskText,
    details: candidate.details,
    badges: readArray<string>(candidate.raw.warning_tags ?? candidate.raw.data_quality_tags).slice(0, 4),
  };
}

export async function shadowLifecycle(symbol: string, nextState: string) {
  return mutationClient.updateLowBuyLifecycleShadow(symbol, {
    state: nextState,
    reason: "frontend-next playbook shadow action",
    source: "frontend-next-shadow",
  });
}

function candidatesFromPriority(value: unknown, quotes = new Map<string, Record<string, unknown>>()): PlaybookCandidate[] {
  return priorityRecordsFromBoard(value).map((item) => candidateFromRecord(item, quotes));
}

function priorityRecordsFromBoard(value: unknown): Record<string, unknown>[] {
  const root = readRecord(value);
  const board = readRecord(root.priority_board ?? value);
  const direct = readArray<Record<string, unknown>>(board.items);
  if (direct.length) return direct;
  const familyItems = readArray<Record<string, unknown>>(board.family_sections).flatMap((section) =>
    readArray<Record<string, unknown>>(readRecord(section).items),
  );
  if (familyItems.length) return familyItems;
  const bucketItems = readArray<Record<string, unknown>>(board.simple_buckets).flatMap((bucket) => {
    const bucketRecord = readRecord(bucket);
    const explicitItems = readArray<Record<string, unknown>>(bucketRecord.items ?? bucketRecord.candidates ?? bucketRecord.rows);
    if (explicitItems.length) return explicitItems;
    const bucketKey = text(bucketRecord.key, "");
    const bucketTitle = text(bucketRecord.title, bucketKey || "候选");
    return readArray<string | number>(bucketRecord.symbols).map((symbol) => ({
      symbol,
      simple_bucket: bucketKey,
      simple_bucket_text: bucketTitle,
      buy_signal_text: bucketTitle,
      action_summary: text(bucketRecord.description, ""),
    }));
  });
  if (bucketItems.length) return bucketItems;
  const fromScreener = readArray<Record<string, unknown>>(root.confirmed_candidates)
    .concat(readArray<Record<string, unknown>>(root.candidates))
    .concat(readArray<Record<string, unknown>>(root.watch_candidates));
  return fromScreener;
}

function candidateFromRecord(item: Record<string, unknown>, quotes = new Map<string, Record<string, unknown>>()): PlaybookCandidate {
  const symbol = text(item.symbol);
  const quote = quotes.get(symbol) ?? {};
  const price = pickFirst(quote, ["latest_price", "last_price", "price"]) ?? pickFirst(item, ["latest_price", "price"]);
  const change = pickFirst(quote, ["change_pct", "pct_chg", "change"]) ?? item.change_pct;
  const score = Number(pickFirst(item, ["priority_score", "production_score", "score"]) ?? 0);
  const signalState = normalizedSignalState(item, quote);
  const simpleBucket = normalizedSimpleBucket(item, signalState, quote);
  const raw = Object.keys(quote).length
    ? { ...item, latest_price: price, change_pct: change, live_quote: quote }
    : item;
  if (Object.keys(quote).length) {
    raw.buy_signal_state = signalState || raw.buy_signal_state;
    raw.buy_signal_text = pickFirst(quote, ["buy_signal_text", "signal_text"]) ?? raw.buy_signal_text;
    raw.buy_signal_hint = pickFirst(quote, ["buy_signal_hint", "trigger_condition"]) ?? raw.buy_signal_hint;
    raw.suggested_position_text = pickFirst(quote, ["suggested_position_text"]) ?? raw.suggested_position_text;
    raw.position_breakdown_text = pickFirst(quote, ["position_breakdown_text"]) ?? raw.position_breakdown_text;
    raw.execution_quality_text = pickFirst(quote, ["execution_quality_text"]) ?? raw.execution_quality_text;
    raw.trigger_condition = pickFirst(quote, ["trigger_condition"]) ?? raw.trigger_condition;
    raw.invalid_condition = pickFirst(quote, ["invalid_condition"]) ?? raw.invalid_condition;
    raw.risk_tier = pickFirst(quote, ["risk_tier"]) ?? raw.risk_tier;
  }
  return {
    symbol,
    name: text(item.name ?? item.stock_name, ""),
    lane: simpleBucket || text(item.display_lane ?? item.strategy_family, "baseline"),
    laneText: simpleBucketText(simpleBucket, text(item.simple_bucket_text ?? item.display_lane_title ?? item.strategy_family_text, "候选")),
    signalState,
    simpleBucket,
    action: actionTextForSignal(raw, signalState, simpleBucket),
    price: numberText(price, "--"),
    score: Number.isFinite(score) ? score : 0,
    scoreText: numberText(score, "--"),
    changeText: pctText(change, ""),
    riskText: text(item.risk_tier ?? item.data_quality_text ?? item.blocked_reason, ""),
    recommendDate: recommendationDateText(item),
    details: text(item.action_summary ?? item.primary_lane_reason ?? item.execution_note ?? item.strategy_performance_text, ""),
    strategy: text(item.strategy_title ?? item.strategy_key, ""),
    raw,
  };
}

function normalizedSignalState(item: Record<string, unknown>, quote: Record<string, unknown>): string {
  return text(pickFirst(quote, ["buy_signal_state", "signal_state"]) ?? pickFirst(item, ["buy_signal_state", "signal_state", "signal_status"]), "").toLowerCase();
}

function normalizedSimpleBucket(item: Record<string, unknown>, signalState: string, quote: Record<string, unknown>): string {
  if (pickFirst(quote, ["buy_signal_state", "signal_state"]) !== undefined) {
    return simpleBucketFromSignal(signalState);
  }
  const bucket = text(pickFirst(item, ["simple_bucket", "bucket", "priority_lane"]), "").toLowerCase();
  if (bucket) return bucket;
  return simpleBucketFromSignal(signalState);
}

function simpleBucketFromSignal(signalState: string): string {
  if (signalState === "buy_now" || signalState === "soft_buy_now") return "buy_now";
  if (signalState === "near_entry" || signalState === "observe_confirmed" || signalState === "watch") return "wait_price";
  if (signalState === "avoid") return "give_up";
  return "";
}

function simpleBucketText(simpleBucket: string, fallback: string): string {
  if (simpleBucket === "buy_now") return "确认可买";
  if (simpleBucket === "wait_price") return "观察等待";
  if (simpleBucket === "give_up") return "暂时放弃";
  return fallback;
}

function actionTextForSignal(item: Record<string, unknown>, signalState: string, simpleBucket: string): string {
  const action = text(pickFirst(item, ["buy_signal_text", "next_action_text", "signal_state", "action_text", "action_summary"]), "");
  if (conflictsWithStructuredSignal(action, signalState, simpleBucket)) {
    return structuredSignalText(signalState, simpleBucket);
  }
  return action || structuredSignalText(signalState, simpleBucket) || "观察";
}

function conflictsWithStructuredSignal(action: string, signalState: string, simpleBucket: string): boolean {
  if (!action) return false;
  const raw = action.toLowerCase();
  if ((simpleBucket === "wait_price" || signalState === "near_entry" || signalState === "observe_confirmed" || signalState === "watch") && isBuyLikeText(raw)) {
    return true;
  }
  if ((simpleBucket === "give_up" || signalState === "avoid") && isBuyLikeText(raw)) {
    return true;
  }
  return false;
}

function structuredSignalText(signalState: string, simpleBucket: string): string {
  if (simpleBucket === "buy_now" || signalState === "buy_now") return "确定买入";
  if (signalState === "soft_buy_now") return "小仓试买";
  if (simpleBucket === "wait_price" || signalState === "near_entry") return "接近买点，等待确认";
  if (signalState === "observe_confirmed") return "观察确认";
  if (signalState === "watch") return "继续观察";
  if (simpleBucket === "give_up" || signalState === "avoid") return "暂时放弃";
  return "";
}

function isBuyLikeText(value: string): boolean {
  return value.includes("buy") || value.includes("立即") || value.includes("确定") || value.includes("可买") || value.includes("买入");
}

function quoteBySymbol(data: PlaybookDataset | null): Map<string, Record<string, unknown>> {
  const root = readRecord(data?.quotes);
  const records = readArray<Record<string, unknown>>(root.quotes).concat(readArray<Record<string, unknown>>(root.items));
  const entries: Array<[string, Record<string, unknown>]> = [];
  records.forEach((item) => {
    const symbol = text(item.symbol, "");
    if (symbol) entries.push([symbol, item]);
  });
  addMappedQuotes(entries, root.quotes);
  addMappedQuotes(entries, root.items);
  return new Map(entries);
}

function addMappedQuotes(entries: Array<[string, Record<string, unknown>]>, value: unknown): void {
  const record = readRecord(value);
  Object.entries(record).forEach(([key, rawItem]) => {
    const item = readRecord(rawItem);
    if (!Object.keys(item).length) return;
    const symbol = text(item.symbol, key);
    if (symbol) entries.push([symbol, { symbol, ...item }]);
  });
}

function boardRoot(data: PlaybookDataset | null): Record<string, unknown> {
  const root = readRecord(data?.priorityBoard);
  return readRecord(root.priority_board ?? root);
}

function countByLane(data: PlaybookDataset | null, lane: string): number {
  return playbookCandidates(data).filter((item) => item.lane === lane).length;
}

function candidateRoot(data: PlaybookDataset | null): Record<string, unknown> {
  const screenerRoot = readRecord(data?.screener);
  return priorityRecordsFromBoard(screenerRoot).length ? screenerRoot : boardRoot(data);
}

function playbookCandidates(data: PlaybookDataset | null, quotes = new Map<string, Record<string, unknown>>()): PlaybookCandidate[] {
  const screenerCandidates = candidatesFromPriority(data?.screener, quotes);
  if (screenerCandidates.length) return screenerCandidates;
  return candidatesFromPriority(data?.priorityBoard, quotes);
}

function uniqueByKey(items: PlaybookStrategyTab[]): PlaybookStrategyTab[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (!item.key || seen.has(item.key)) return false;
    seen.add(item.key);
    return true;
  });
}

export function detailRows(candidate: PlaybookCandidate | null) {
  const raw = readRecord(candidate?.raw);
  return [
    ["触发", text(raw.trigger_condition ?? raw.buy_signal_hint, "--")],
    ["失效", text(raw.invalid_condition, "--")],
    ["入场区间", `${numberText(raw.entry_zone_low, "--")} - ${numberText(raw.entry_zone_high, "--")}`],
    ["推荐日期", recommendationDateText(raw)],
    ["止损", numberText(raw.stop_loss, "--")],
    ["仓位", text(raw.suggested_position_text ?? raw.position_breakdown_text, "--")],
    ["策略", text(candidate?.strategy, "--")],
  ];
}

export function candidateDateGroups(items: PlaybookCandidate[], tradeDate: string): PlaybookDateGroup[] {
  const today: PlaybookCandidate[] = [];
  const yesterday: PlaybookCandidate[] = [];
  const history: PlaybookCandidate[] = [];
  const recommendationDates = Array.from(new Set(items.map((item) => normalizeDate(item.recommendDate)).filter(Boolean))).sort();
  const normalizedTradeDate = normalizeDate(tradeDate) || recommendationDates.at(-1) || "";
  const previousRecommendationDate = latestDateBefore(recommendationDates, normalizedTradeDate);
  items.forEach((item) => {
    const recommendationDate = normalizeDate(item.recommendDate);
    if (recommendationDate && normalizedTradeDate && recommendationDate === normalizedTradeDate) {
      today.push(item);
    } else if (recommendationDate && recommendationDate === previousRecommendationDate) {
      yesterday.push(item);
    } else {
      history.push(item);
    }
  });
  const groups: PlaybookDateGroup[] = [
    { key: "today", title: "今日推荐", hint: "后端当前交易日新入榜", items: today },
    { key: "yesterday", title: "昨日延续", hint: "上一交易窗口延续观察", items: yesterday },
    { key: "history", title: "历史观察", hint: "更早推荐，先看状态再行动", items: history },
  ];
  return groups.filter((group) => group.items.length > 0);
}

function recommendationDateText(item: Record<string, unknown>): string {
  return text(
    pickFirst(item, [
      "recommendation_date",
      "recommended_at",
      "confirmed_trade_date",
      "signal_trade_date",
      "latest_trade_date",
      "current_date",
      "quote_timestamp",
      "board_date",
    ]),
    "--",
  ).slice(0, 10);
}

function normalizeDate(value: string): string {
  const match = value.match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : "";
}

function latestDateBefore(dates: string[], tradeDate: string): string {
  return dates.filter((date) => date < tradeDate).at(-1) ?? "";
}

function emptyPlaybookDataset(patch: Partial<PlaybookDataset> = {}): PlaybookDataset {
  return {
    screener: undefined,
    priorityBoard: undefined,
    quotes: undefined,
    strategies: undefined,
    meta: undefined,
    loadedAt: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    ...patch,
  };
}

function withTimeout(init: RequestJsonOptions, timeoutMs: number): RequestJsonOptions {
  return { ...init, timeoutMs: init.timeoutMs ?? timeoutMs, retry: init.retry ?? false };
}

export function performanceSummary(family: PlaybookFamily | null) {
  const performance = readRecord(family?.performance);
  return [
    { label: "样本", value: text(performance.evaluated_signals ?? performance.strategy_count, "--") },
    { label: "命中率", value: pctText(performance.hit_rate, "--") },
    { label: "净胜率", value: pctText(performance.net_win_rate, "--") },
    { label: "平均收益", value: pctText(performance.avg_net_return_pct, "--") },
  ];
}

export function attributionLines(candidate: PlaybookCandidate | null): string[] {
  const raw = readRecord(candidate?.raw);
  return readArray<string>(raw.market_gate_reasons)
    .concat(readArray<string>(raw.sector_leader_gate_reasons))
    .concat(readArray<string>(raw.strategy_engine_exclusion_reasons))
    .concat(text(nested(raw, "next_day_event_plan.state_text"), ""))
    .filter(Boolean)
    .slice(0, 6);
}
