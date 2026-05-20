import type {
  BacktestResourceTier,
  BacktestVerdictThresholdItem,
  BacktestVerdictThresholdsResponse,
} from "../../api/backtests";
import { backtestsApi } from "../../api/backtests";
import type { BacktestVerdictThresholds } from "../../utils/uxClarity";

export type BacktestVerdictThresholdMap = Record<BacktestResourceTier, BacktestVerdictThresholds>;

const DEFAULT_THRESHOLDS: BacktestVerdictThresholdMap = {
  light: {
    minReturnPct: 1.0,
    minSharpe: 0.4,
    maxDrawdownPct: -18,
    cautiousMinReturnPct: -1.0,
    cautiousMaxDrawdownPct: -25,
  },
  full: {
    minReturnPct: 3.0,
    minSharpe: 0.8,
    maxDrawdownPct: -12,
    cautiousMinReturnPct: 0.0,
    cautiousMaxDrawdownPct: -18,
  },
  walk_forward: {
    minReturnPct: 1.5,
    minSharpe: 0.6,
    maxDrawdownPct: -15,
    cautiousMinReturnPct: -0.5,
    cautiousMaxDrawdownPct: -22,
  },
};

let cachedThresholds: BacktestVerdictThresholdMap = DEFAULT_THRESHOLDS;
let inflight: Promise<BacktestVerdictThresholdMap> | null = null;

export function currentBacktestVerdictThresholds(): BacktestVerdictThresholdMap {
  return cachedThresholds;
}

export function backtestVerdictThresholds(value?: BacktestResourceTier | string | null): BacktestVerdictThresholds {
  const tier = normalizeResourceTier(value);
  return currentBacktestVerdictThresholds()[tier];
}

export function applyBacktestVerdictThresholds(payload: BacktestVerdictThresholdsResponse | null | undefined): void {
  if (!payload) return;
  cachedThresholds = normalizeThresholdResponse(payload);
}

export async function loadBacktestVerdictThresholds(force = false): Promise<BacktestVerdictThresholdMap> {
  if (!force && inflight) return inflight;
  inflight = backtestsApi.getVerdictThresholds()
    .then((payload) => {
      cachedThresholds = normalizeThresholdResponse(payload);
      return cachedThresholds;
    })
    .catch(() => cachedThresholds)
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

function normalizeThresholdResponse(payload: BacktestVerdictThresholdsResponse): BacktestVerdictThresholdMap {
  const thresholds = payload.thresholds ?? {};
  return {
    light: normalizeThresholdItem(thresholds.light, DEFAULT_THRESHOLDS.light),
    full: normalizeThresholdItem(thresholds.full, DEFAULT_THRESHOLDS.full),
    walk_forward: normalizeThresholdItem(thresholds.walk_forward, DEFAULT_THRESHOLDS.walk_forward),
  };
}

function normalizeThresholdItem(
  value: BacktestVerdictThresholdItem | Partial<BacktestVerdictThresholds> | Record<string, unknown> | undefined,
  fallback: BacktestVerdictThresholds,
): BacktestVerdictThresholds {
  const raw = (value ?? {}) as Record<string, unknown>;
  return {
    minReturnPct: numberValue(raw.minReturnPct ?? raw.min_return_pct, fallback.minReturnPct),
    minSharpe: numberValue(raw.minSharpe ?? raw.min_sharpe, fallback.minSharpe),
    maxDrawdownPct: numberValue(raw.maxDrawdownPct ?? raw.max_drawdown_pct, fallback.maxDrawdownPct),
    cautiousMinReturnPct: numberValue(
      raw.cautiousMinReturnPct ?? raw.cautious_min_return_pct,
      fallback.cautiousMinReturnPct,
    ),
    cautiousMaxDrawdownPct: numberValue(
      raw.cautiousMaxDrawdownPct ?? raw.cautious_max_drawdown_pct,
      fallback.cautiousMaxDrawdownPct,
    ),
  };
}

function normalizeResourceTier(value?: BacktestResourceTier | string | null): BacktestResourceTier {
  const tier = String(value || "").trim().toLowerCase();
  if (tier === "light" || tier === "walk_forward") return tier;
  return "full";
}

function numberValue(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
