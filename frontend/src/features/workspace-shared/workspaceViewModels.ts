import type { LowBuyCandidate, LowBuyPriorityBoardItem, LowBuyScreenerResult, SettingsPayload, WatchlistSignal } from "../../types";
import { ALL_PLAYBOOK_TABS } from "./workspaceConstants";
import { actionText, formatPct, formatPrice, parseNumber, plainTradingText, riskText, riskTierText, toneFromChange } from "./workspaceFormatters";
import type { SettingsDraft, StockCardView } from "./workspaceTypes";

export function priorityToCard(item: LowBuyPriorityBoardItem): StockCardView {
  const strategyTitles = Array.isArray(item.strategy_titles) ? item.strategy_titles : [];
  const highlight = item.strategy_key === "limit_up_breakout_retrace" || strategyTitles.some((title) => title.includes("涨停"));
  const sectorText = item.sector_name?.trim() || "未归类板块";
  const strategyNames = uniqueStrings([item.strategy_title, ...strategyTitles]);
  return {
    name: item.name,
    symbol: item.symbol,
    identityNote: laneIdentityText(item),
    identityTags: [sectorText, item.mainline_tier_text || item.industry_tier_text || ""].filter(Boolean),
    sectorText,
    priceText: formatPrice(item.latest_price),
    changeText: formatPct(item.change_pct),
    livePrice: true,
    scoreText: priorityScoreText(item),
    riskText: riskTierText(item.risk_tier),
    expectedText: item.suggested_position_text,
    actionText: item.buy_signal_text || item.action_summary,
    entryText: optionalPriceRange(item.entry_zone_low, item.entry_zone_high),
    stopText: optionalPrice(item.stop_loss),
    operationAmountText: item.suggested_position_text,
    primaryReason: item.next_action_text || item.action_summary,
    details: [
      mainForceSummary(item.main_force_advice),
      nextDayPlanText(item.next_day_event_plan),
      strategyNames.slice(0, 3).join(" + ") || item.strategy_title,
      item.leader_strength_text,
      item.multi_timeframe_resonance_text,
      sectorText,
      recommendationSummary(item.recommendation_days, item.recommendation_start_date),
      item.exit_plan_text,
      item.position_breakdown_text || item.suggested_position_text,
      item.primary_lane_reason,
      `止损 ${formatPrice(item.stop_loss)}`,
    ].filter(Boolean).join(" / "),
    executionHint: [nextDayPlanHint(item.next_day_event_plan), priorityExecutionHint(item), item.exit_plan_text, item.recommendation_duration_text].filter(Boolean).join(" "),
    failureText: priorityFailureText(item),
    tone: toneFromChange(item.change_pct),
    badges: [
      (item.strategy_count ?? 0) > 1 ? `${item.strategy_count}策略命中` : "",
      mainForceBadge(item.main_force_advice),
      item.family_count && item.family_count > 1 ? `${item.family_count}类逻辑共振` : "",
      item.leader_strength_rank ? `板块龙头#${item.leader_strength_rank}` : "",
      item.multi_timeframe_resonance_score ? "多周期共振" : "",
      matchedLaneBadge(item),
    ].filter(Boolean),
    highlight,
  };
}

function laneIdentityText(item: LowBuyPriorityBoardItem): string {
  if (item.display_lane === "front_row_weighted") {
    return "前排加权 · Paper验证";
  }
  if (item.display_lane === "front_row_only") {
    return "前排极精选 · 仅观察";
  }
  return item.strategy_title;
}

function priorityScoreText(item: LowBuyPriorityBoardItem): string {
  if (item.display_lane === "front_row_weighted" && item.production_score != null) {
    return `Shadow ${fixedNumberText(item.production_score, 0)}`;
  }
  if (item.display_lane === "front_row_only") {
    const score = item.elite_watch_score ?? item.watch_score ?? item.priority_score;
    return `观察 ${fixedNumberText(score, 0)}`;
  }
  return fixedNumberText(item.priority_score, 0);
}

function matchedLaneBadge(item: LowBuyPriorityBoardItem): string {
  const matched = item.matched_strategy_variants ?? [];
  if (matched.length <= 1) {
    return "";
  }
  return `同时命中${matched.length}线`;
}

function priorityExecutionHint(item: LowBuyPriorityBoardItem): string {
  if (item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now") {
    return "确定买入：价格已进入买点区并通过承接确认，按建议仓位执行；跌破止损或出现阻断信号立即放弃。";
  }
  if (item.buy_signal_state === "near_entry") {
    return "接近买点：价格接近买点或已到位但确认不足，只盯承接，不提前买；确认后才进入执行。";
  }
  if (item.buy_signal_state === "observe_confirmed") {
    return "观察确认：结构、热点和市场状态已达标，仍需结合买点、仓位和风控执行。";
  }
  return "";
}

function priorityFailureText(item: LowBuyPriorityBoardItem): string {
  const risk = riskTierText(item.risk_tier);
  const stopLoss = item.stop_loss ? `跌破 ${formatPrice(item.stop_loss)} 视为失效` : "";
  if (item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now") {
    return [stopLoss, "出现放量下跌、板块退潮或硬阻断时放弃执行", `风险 ${risk}`].filter(Boolean).join("；");
  }
  if (item.buy_signal_state === "observe_confirmed") {
    return [stopLoss, "观察确认不等于自动买入，跌破买点区或板块转弱即降级", `风险 ${risk}`].filter(Boolean).join("；");
  }
  if (item.buy_signal_state === "near_entry") {
    return [stopLoss, "没有承接确认、冲高回落或板块转弱时继续观望", `风险 ${risk}`].filter(Boolean).join("；");
  }
  return [stopLoss, `风险 ${risk}，不满足买点和承接确认就不操作`].filter(Boolean).join("；");
}

function uniqueStrings(values: Array<string | undefined | null>): string[] {
  const result: string[] = [];
  for (const value of values) {
    const cleaned = (value ?? "").trim();
    if (cleaned && !result.includes(cleaned)) {
      result.push(cleaned);
    }
  }
  return result;
}

export function candidateToCard(item: LowBuyCandidate): StockCardView {
  return {
    name: item.name,
    symbol: item.symbol,
    identityNote: item.strategy_title,
    identityTags: [item.mainline_tier_text || ""].filter(Boolean),
    priceText: formatPrice(item.latest_price),
    changeText: formatPct(item.change_pct),
    scoreText: fixedNumberText(item.score, 0),
    riskText: riskTierText(item.risk_tier),
    expectedText: item.suggested_position_text,
    actionText: item.buy_signal_text,
    entryText: optionalPriceRange(item.entry_zone_low, item.entry_zone_high),
    stopText: optionalPrice(item.stop_loss),
    operationAmountText: item.suggested_position_text,
    primaryReason: item.summary_reason,
    details: [
      mainForceSummary(item.main_force_advice),
      nextDayPlanText(item.next_day_event_plan),
      exitPlanSummary(item.exit_plan),
      item.leader_strength_text,
      item.multi_timeframe_resonance_text,
      `${formatPrice(item.entry_zone_low)}-${formatPrice(item.entry_zone_high)}`,
      `止损 ${formatPrice(item.stop_loss)}`,
      quoteQualityText(item),
      recommendationSummary(item.recommendation_days, item.recommendation_start_date),
      item.summary_reason,
    ].filter(Boolean).join(" / "),
    executionHint: [nextDayPlanHint(item.next_day_event_plan), exitPlanHint(item.exit_plan), item.recommendation_duration_text].filter(Boolean).join(" "),
    failureText: candidateFailureText(item),
    tone: toneFromChange(item.change_pct),
    badges: [
      item.strategy_title,
      mainForceBadge(item.main_force_advice),
      item.leader_strength_rank ? `板块龙头#${item.leader_strength_rank}` : "",
      item.multi_timeframe_resonance_score ? "多周期共振" : "",
      item.mainline_tier_text || "",
      item.execution_quality_text || "",
      item.is_stale ? "行情过期" : "",
    ].filter(Boolean),
    highlight: item.strategy_key === "limit_up_breakout_retrace",
  };
}

function mainForceSummary(advice?: LowBuyCandidate["main_force_advice"]): string {
  if (!advice || (!advice.stage_text && !advice.action_text)) {
    return "";
  }
  const score = typeof advice.score === "number" && Number.isFinite(advice.score) ? advice.score.toFixed(1) : "";
  const status = advice.production_effect === "ranking_bonus"
    ? `已参与排序${advice.rank_bonus ? ` +${advice.rank_bonus.toFixed(1)}` : ""}`
    : "旁路观察";
  const evidence = (advice.reasons ?? []).slice(0, 2).join("；");
  const risk = advice.risk_flags?.length ? `风险：${advice.risk_flags.slice(0, 2).join("；")}` : "";
  return [`主力：${[advice.stage_text, advice.action_text, score].filter(Boolean).join(" · ")}`, status, evidence, risk].filter(Boolean).join(" / ");
}

function mainForceBadge(advice?: LowBuyCandidate["main_force_advice"]): string {
  if (!advice || !advice.stage_text) {
    return "";
  }
  if (advice.production_effect === "ranking_bonus") {
    return "主力已加权";
  }
  return `主力${advice.stage_text}`;
}

function quoteQualityText(item: Pick<LowBuyCandidate, "data_source" | "source_quality" | "is_stale">): string {
  if (item.is_stale) {
    return "行情已过期";
  }
  if (item.source_quality === "realtime") {
    return item.data_source ? `行情 ${item.data_source}` : "实时行情";
  }
  if (item.source_quality) {
    return `行情质量 ${item.source_quality}`;
  }
  return "";
}

function nextDayPlanText(plan?: { state?: string; state_text?: string; max_holding_days?: number; position_pct?: number }) {
  if (!plan || !plan.state || plan.state === "none") {
    return "";
  }
  const holding = plan.max_holding_days ? `最长${plan.max_holding_days}天` : "";
  const position = plan.position_pct ? `小仓${plan.position_pct}%` : "";
  return [plan.state_text, holding, position].filter(Boolean).join(" / ");
}

function nextDayPlanHint(plan?: { next_day_action?: string; t2_action?: string }) {
  if (!plan) {
    return "";
  }
  return [plan.next_day_action, plan.t2_action].filter(Boolean).join(" ");
}

function exitPlanSummary(plan?: LowBuyCandidate["exit_plan"]) {
  if (!plan) {
    return "";
  }
  const days = plan.max_holding_days ? `最长${plan.max_holding_days}天` : "";
  const takeProfit = plan.first_take_profit ? `先看${formatPrice(plan.first_take_profit)}` : "";
  return [days, takeProfit].filter(Boolean).join(" / ");
}

function exitPlanHint(plan?: LowBuyCandidate["exit_plan"]) {
  if (!plan) {
    return "";
  }
  const firstRule = plan.exit_rules?.[0] || "";
  return [plan.time_stop_text, firstRule].filter(Boolean).join(" ");
}

function candidateFailureText(item: LowBuyCandidate): string {
  const invalid = item.exit_plan?.invalid_condition || "";
  const stopLoss = item.stop_loss ? `跌破 ${formatPrice(item.stop_loss)} 视为失效` : "";
  const firstRule = item.exit_plan?.exit_rules?.[0] || "";
  return [invalid, stopLoss, firstRule, `风险 ${riskTierText(item.risk_tier)}`].filter(Boolean).join("；");
}

function recommendationSummary(days?: number, startDate?: string | null): string {
  if (!days || days <= 0) {
    return "";
  }
  return startDate ? `连续推荐 ${days}天，自 ${startDate}` : `连续推荐 ${days}天`;
}

export function watchSignalToCard(item: WatchlistSignal): StockCardView {
  return {
    name: displayName(item.symbol, item.name, item.quote.name),
    symbol: item.symbol,
    identityNote: `成本价 ${formatPrice(item.cost_basis)}`,
    priceText: formatPrice(item.quote.last_price),
    changeText: formatPct(item.quote.change_pct),
    livePrice: true,
    scoreText: fixedNumberText(item.signal.signal_score, 0),
    riskText: riskText(item.signal.risk_level),
    expectedText: formatPct(item.signal.expected_profit_pct),
    actionText: item.signal.plain_action_text || actionText(item.signal.action),
    entryText: optionalPrice(item.signal.entry_price),
    stopText: optionalPrice(item.signal.stop_loss),
    operationAmountText: item.signal.min_shares_suggestion ? `${item.signal.min_shares_suggestion} 股起` : `${formatPct(item.signal.position_pct, 0)} 仓位`,
    primaryReason: plainTradingText(item.signal.plain_action_reason) || plainTradingText(item.signal.scenario),
    details: [
      plainTradingText(item.signal.plain_action_reason) || plainTradingText(item.signal.scenario),
      `仓位 ${formatPct(item.signal.position_pct, 0)}`,
      item.signal.stop_loss ? `止损 ${formatPrice(item.signal.stop_loss)}` : "",
    ].filter(Boolean).join(" / "),
    executionHint: item.signal.plain_execution_text || item.signal.plain_invalid_condition,
    failureText: watchSignalFailureText(item),
    tone: toneFromChange(item.quote.change_pct),
    badges: [plainTradingText(item.signal.trade_scene_text), plainTradingText(item.memo)].filter(Boolean),
  };
}

function optionalPrice(value?: number | null): string | undefined {
  return typeof value === "number" && Number.isFinite(value) ? formatPrice(value) : undefined;
}

function optionalPriceRange(low?: number | null, high?: number | null): string | undefined {
  if (typeof low !== "number" || !Number.isFinite(low) || typeof high !== "number" || !Number.isFinite(high)) {
    return undefined;
  }
  return `${formatPrice(low)} - ${formatPrice(high)}`;
}

function fixedNumberText(value: number | undefined | null, digits: number): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "--";
}

function watchSignalFailureText(item: WatchlistSignal): string {
  const invalid = plainTradingText(item.signal.plain_invalid_condition);
  const stopLoss = item.signal.stop_loss ? `跌破 ${formatPrice(item.signal.stop_loss)} 视为失效` : "";
  return [invalid, stopLoss, `风险 ${riskText(item.signal.risk_level)}`].filter(Boolean).join("；");
}

function displayName(symbol: string, ...names: Array<string | undefined | null>) {
  for (const name of names) {
    const cleaned = (name ?? "").trim();
    if (cleaned && cleaned !== symbol) {
      return cleaned;
    }
  }
  return symbol;
}

export function settingsToDraft(settings: SettingsPayload, adminToken: string): SettingsDraft {
  return {
    adminToken,
    llm_provider: settings.llm_provider || "",
    llm_api_key: "",
    llm_base_url: settings.llm_base_url || "",
    llm_model: settings.llm_model || "",
    data_source: settings.data_source || "",
    data_source_base_url: settings.data_source_base_url || "",
    risk_max_single_loss_pct: String(settings.risk_max_single_loss_pct ?? ""),
    risk_max_daily_loss_pct: String(settings.risk_max_daily_loss_pct ?? ""),
    risk_pause_after_losses: String(settings.risk_pause_after_losses ?? ""),
    strategy_min_profit_pct: String(settings.strategy_min_profit_pct ?? ""),
  };
}

export function settingsPayload(draft: SettingsDraft, section: "llm" | "risk" | "data"): Partial<SettingsPayload> {
  if (section === "llm") {
    return {
      llm_provider: draft.llm_provider,
      llm_api_key: draft.llm_api_key,
      llm_base_url: draft.llm_base_url,
      llm_model: draft.llm_model,
    };
  }
  if (section === "data") {
    return {
      data_source: draft.data_source,
      data_source_base_url: draft.data_source_base_url,
    };
  }
  return {
    risk_max_single_loss_pct: parseNumber(draft.risk_max_single_loss_pct),
    risk_max_daily_loss_pct: parseNumber(draft.risk_max_daily_loss_pct),
    risk_pause_after_losses: parseNumber(draft.risk_pause_after_losses),
    strategy_min_profit_pct: parseNumber(draft.strategy_min_profit_pct),
  };
}

export function trackedPlaybookSymbols(payload: LowBuyScreenerResult) {
  const symbols = new Set<string>();
  for (const candidate of [...payload.confirmed_candidates, ...payload.candidates]) {
    if (candidate.symbol) {
      symbols.add(candidate.symbol);
    }
  }
  return [...symbols];
}
