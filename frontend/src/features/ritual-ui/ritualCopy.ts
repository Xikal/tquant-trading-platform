import type { RitualMarketTone, RitualSealCopy } from "./ritualTypes";

export const RITUAL_FORTUNE_TEXT: Record<RitualMarketTone, string[]> = {
  strong: ["红而不躁", "顺势从容", "稳中求进"],
  neutral: ["守正待机", "静待东风", "纪律先行"],
  weak: ["绿而不慌", "守住节奏", "少动多看"],
  unknown: ["守正待机", "纪律先行", "静待东风"],
};

export const RITUAL_BLESSINGS = [
  "愿今日少追高，多从容。",
  "愿买点清晰，止损果断。",
  "愿红盘常在，纪律先行。",
  "愿顺势而为，不急不躁。",
  "愿看得清风险，也等得到机会。",
];

export const RITUAL_LUCKY_DRAWS = [
  { title: "红运签", content: "红而不躁，绿而不慌。" },
  { title: "守正签", content: "机会常有，仓位为先。" },
  { title: "风控签", content: "先守本金，再等东风。" },
  { title: "复盘签", content: "今日得失，明日成章。" },
  { title: "节奏签", content: "慢就是快，稳就是强。" },
];

export const RITUAL_CLOSE_BAGS = [
  "守住本金，也是胜利。",
  "纪律还在，机会就在。",
  "今日不急，明日再看风向。",
  "涨跌皆有数，复盘见真章。",
];

export const RITUAL_CALENDAR_HINTS = [
  { good: "复盘、轻仓、等确认", avoid: "冲动、满仓、追高" },
  { good: "看趋势、看承接、看风险", avoid: "凭感觉、赌反弹、忘止损" },
  { good: "按计划、控仓位、等信号", avoid: "加速追、频繁换、忽视线" },
];

const SIGNAL_SEAL_MAP: Record<string, RitualSealCopy> = {
  buy_now: { label: "买点已至", detail: "来自原业务信号，只做视觉红印。", tone: "strong" },
  soft_buy_now: { label: "红运临近", detail: "小仓试买语义，不新增判断。", tone: "strong" },
  near_entry: { label: "火候未到", detail: "接近买点，还需等业务确认。", tone: "neutral" },
  observe_confirmed: { label: "静候确认", detail: "观察确认，保留原状态。", tone: "neutral" },
  watch: { label: "守正待机", detail: "继续观察，不替代策略原因。", tone: "unknown" },
  avoid: { label: "过火勿追", detail: "风险或质量不足时保持克制。", tone: "danger" },
  stopped: { label: "过火勿追", detail: "已有风险提示，红印只做提醒。", tone: "danger" },
  weakening: { label: "过火勿追", detail: "走势转弱，仍以原风控为准。", tone: "danger" },
};

export function todayRitualKey(date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Shanghai",
    year: "numeric",
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

export function stableRitualIndex(seed: string, length: number): number {
  if (length <= 0) return 0;
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) >>> 0;
  }
  return hash % length;
}

export function ritualFortuneText(tone: RitualMarketTone = "unknown", date = new Date()): string {
  const pool = RITUAL_FORTUNE_TEXT[tone] ?? RITUAL_FORTUNE_TEXT.unknown;
  return pool[stableRitualIndex(`${todayRitualKey(date)}:${tone}`, pool.length)] ?? pool[0];
}

export function ritualBlessingText(date = new Date()): string {
  return RITUAL_BLESSINGS[stableRitualIndex(todayRitualKey(date), RITUAL_BLESSINGS.length)] ?? RITUAL_BLESSINGS[0];
}

export function ritualLuckyDrawText(seed: string): { title: string; content: string } {
  return RITUAL_LUCKY_DRAWS[stableRitualIndex(seed, RITUAL_LUCKY_DRAWS.length)] ?? RITUAL_LUCKY_DRAWS[0];
}

export function ritualCloseBagText(date = new Date()): string {
  return RITUAL_CLOSE_BAGS[stableRitualIndex(todayRitualKey(date), RITUAL_CLOSE_BAGS.length)] ?? RITUAL_CLOSE_BAGS[0];
}

export function ritualCalendarHint(date = new Date()): { good: string; avoid: string } {
  return RITUAL_CALENDAR_HINTS[stableRitualIndex(todayRitualKey(date), RITUAL_CALENDAR_HINTS.length)] ?? RITUAL_CALENDAR_HINTS[0];
}

export function ritualSealCopy(signalState?: string, riskLevel?: string): RitualSealCopy {
  const normalizedRisk = String(riskLevel || "").toLowerCase();
  if (normalizedRisk.includes("高") || normalizedRisk.includes("risk") || normalizedRisk.includes("stop")) {
    return SIGNAL_SEAL_MAP.stopped;
  }
  return SIGNAL_SEAL_MAP[String(signalState || "").trim()] ?? {
    label: "红运守候",
    detail: "只做视觉寓意，不改变原业务状态。",
    tone: "unknown",
  };
}
