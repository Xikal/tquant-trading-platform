import type {
  LowBuyDailyDecision,
  LowBuyPriorityBoardItem,
  LowBuyPriorityBoardResult,
  LowBuySimpleBucket
} from "../types";
import { plainMarketText } from "./plainTradingText";

const GOOD_MARKETS = new Set(["broad_rally", "repair", "neutral"]);
const CAUTIOUS_MARKETS = new Set(["fast_rotation", "weight_support", "low_volume_wait"]);
const BLOCKED_MARKETS = new Set(["risk_release", "high_flyer_retreat"]);

const DEFAULT_BUCKETS: LowBuySimpleBucket[] = [
  { key: "buy_now", title: "确定可买", description: "价格和结构已经满足，只看前排并控制仓位。", count: 0, symbols: [] },
  { key: "wait_price", title: "等到价格", description: "结构还可以，但必须等价格到买点或承接确认。", count: 0, symbols: [] },
  { key: "give_up", title: "放弃观察", description: "没有达到执行条件，先不参与。", count: 0, symbols: [] }
];

export function deriveDailyDecision(board: LowBuyPriorityBoardResult | null): LowBuyDailyDecision {
  if (board?.daily_decision) {
    return board.daily_decision;
  }
  const marketState = board?.market_state ?? "neutral";
  const marketPlainText = plainMarketText(marketState);
  if (BLOCKED_MARKETS.has(marketState)) {
    return {
      key: "wait",
      title: "空仓等待",
      message: "今天不适合新开仓，优先处理持仓或空仓等待。",
      market_plain_text: marketPlainText,
      risk_level: "high",
      action_steps: ["不新增买入", "持仓只按止损和减仓规则处理", "等待市场转修复"]
    };
  }
  if ((board?.immediate_count ?? 0) > 0 && GOOD_MARKETS.has(marketState)) {
    return {
      key: "tradable",
      title: "可交易",
      message: "今天可以小仓试错，只看确定可买里的前 1-3 只。",
      market_plain_text: marketPlainText,
      risk_level: marketState === "broad_rally" ? "low" : "medium",
      action_steps: ["只看确定可买", "先小仓", "提前设好止损"]
    };
  }
  if ((board?.focus_count ?? 0) > 0 || (board?.track_count ?? 0) > 0 || CAUTIOUS_MARKETS.has(marketState)) {
    return {
      key: "observe_only",
      title: "只观察",
      message: "今天先等价格和承接，不追高，不提前买。",
      market_plain_text: marketPlainText,
      risk_level: "medium",
      action_steps: ["等价格到买点", "等止跌确认", "不追高"]
    };
  }
  return {
    key: "wait",
    title: "空仓等待",
    message: "今天没有明确机会，不适合新开仓。",
    market_plain_text: marketPlainText,
    risk_level: "medium",
    action_steps: ["等待下一轮信号", "复查持仓风险"]
  };
}

export function deriveSimpleBuckets(items: LowBuyPriorityBoardItem[]): LowBuySimpleBucket[] {
  const grouped: Record<LowBuySimpleBucket["key"], string[]> = {
    buy_now: [],
    wait_price: [],
    give_up: []
  };
  for (const item of items) {
    grouped[item.simple_bucket ?? fallbackBucketKey(item)].push(item.symbol);
  }
  return DEFAULT_BUCKETS.map((bucket) => ({
    ...bucket,
    count: grouped[bucket.key].length,
    symbols: grouped[bucket.key].slice(0, 10)
  }));
}

export function itemBucketKey(item: LowBuyPriorityBoardItem): LowBuySimpleBucket["key"] {
  return item.simple_bucket ?? fallbackBucketKey(item);
}

export function bucketTitle(key: LowBuySimpleBucket["key"]) {
  return DEFAULT_BUCKETS.find((bucket) => bucket.key === key)?.title ?? "放弃观察";
}

export function recommendationWindowText(item: LowBuyPriorityBoardItem) {
  if (item.recommendation_duration_text) {
    return item.recommendation_duration_text;
  }
  const days = item.recommendation_days ?? 0;
  return days > 0 ? `${item.strategy_title}第 ${days} 天，建议验证窗口 3 天。` : "";
}

function fallbackBucketKey(item: LowBuyPriorityBoardItem): LowBuySimpleBucket["key"] {
  if (item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now") {
    return "buy_now";
  }
  if (item.buy_signal_state === "near_entry") {
    return "wait_price";
  }
  return "give_up";
}
