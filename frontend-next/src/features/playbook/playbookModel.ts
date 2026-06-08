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
  action: string;
  price: string;
  score: number;
  scoreText: string;
  changeText: string;
  riskText: string;
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

export const DEFAULT_PLAYBOOK_STRATEGY = "first_board";

export async function loadPlaybookDataset(strategy: string, init: RequestJsonOptions = {}): Promise<PlaybookDataset> {
  const [screener, priorityBoard, strategies, meta] = await Promise.all([
    apiClient.lowBuyScreener({ strategy, limit: 36, scan_limit: 36, include_history: true }, init),
    apiClient.lowBuyPriorityBoard(30, "baseline", "cache", init),
    apiClient.lowBuyStrategies(init),
    apiClient.strategiesMeta(init),
  ]);
  const symbols = candidatesFromPriority(priorityBoard).slice(0, 20).map((item) => item.symbol);
  const quotes = await apiClient.lowBuyQuotes(symbols, strategy, init);
  return { screener, priorityBoard, quotes, strategies, meta, loadedAt: new Date().toLocaleTimeString("zh-CN", { hour12: false }) };
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

export function candidateFamilies(data: PlaybookDataset | null): PlaybookFamily[] {
  const board = boardRoot(data);
  const sections = readArray<Record<string, unknown>>(board.family_sections);
  if (sections.length) {
    return sections.map((section) => ({
      key: text(section.family_key),
      title: text(section.family_text ?? section.family_key),
      items: readArray<Record<string, unknown>>(section.items).map(candidateFromRecord),
      performance: readRecord(section.performance),
    }));
  }
  const groups = new Map<string, PlaybookCandidate[]>();
  candidatesFromPriority(data?.priorityBoard).forEach((candidate) => {
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

function candidatesFromPriority(value: unknown): PlaybookCandidate[] {
  return priorityRecordsFromBoard(value).map(candidateFromRecord);
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
  const fromScreener = readArray<Record<string, unknown>>(root.confirmed_candidates).concat(readArray<Record<string, unknown>>(root.watch_candidates));
  return fromScreener;
}

function candidateFromRecord(item: Record<string, unknown>): PlaybookCandidate {
  const score = Number(pickFirst(item, ["priority_score", "production_score", "score"]) ?? 0);
  return {
    symbol: text(item.symbol),
    name: text(item.name ?? item.stock_name, ""),
    lane: text(item.simple_bucket ?? item.display_lane ?? item.strategy_family, "baseline"),
    laneText: text(item.simple_bucket_text ?? item.display_lane_title ?? item.strategy_family_text, "候选"),
    action: text(item.buy_signal_text ?? item.next_action_text ?? item.action_summary, "观察"),
    price: numberText(item.latest_price ?? item.price, "--"),
    score: Number.isFinite(score) ? score : 0,
    scoreText: numberText(score, "--"),
    changeText: pctText(item.change_pct, ""),
    riskText: text(item.risk_tier ?? item.data_quality_text ?? item.blocked_reason, ""),
    details: text(item.action_summary ?? item.primary_lane_reason ?? item.execution_note ?? item.strategy_performance_text, ""),
    strategy: text(item.strategy_title ?? item.strategy_key, ""),
    raw: item,
  };
}

function boardRoot(data: PlaybookDataset | null): Record<string, unknown> {
  const root = readRecord(data?.priorityBoard);
  return readRecord(root.priority_board ?? root);
}

function countByLane(data: PlaybookDataset | null, lane: string): number {
  return candidatesFromPriority(data?.priorityBoard).filter((item) => item.lane === lane).length;
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
    ["止损", numberText(raw.stop_loss, "--")],
    ["仓位", text(raw.suggested_position_text ?? raw.position_breakdown_text, "--")],
    ["策略", text(candidate?.strategy, "--")],
  ];
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
