import type {
  AnalysisBatchRankRequest,
  AnalysisBatchRankResponse,
  GeneratedPriorityItem,
  ChartDownsampleRequest,
  ChartDownsampleResponse,
  MonitorPriorityNormalizeRequest,
  MonitorPriorityNormalizeResponse,
  StrategyTrackingFilterSortRequest,
  StrategyTrackingFilterSortResponse,
} from "./protocol";

export function normalizeMonitorPrioritySync({
  board,
  limit = 120,
}: MonitorPriorityNormalizeRequest): MonitorPriorityNormalizeResponse {
  const items = [...(board?.items ?? [])]
    .filter((item) => Boolean(item?.symbol))
    .sort(prioritySort)
    .slice(0, Math.max(0, limit));
  return {
    items,
    total: board?.items?.length ?? 0,
  };
}

export function filterSortStrategyTrackingSync({
  filters = {},
  items,
  limit = items.length,
  offset = 0,
  sort = "max_gain_desc",
}: StrategyTrackingFilterSortRequest): StrategyTrackingFilterSortResponse {
  const filtered = items.filter((item) => (
    matchesString(item.signal_state, filters.signal_state) &&
    matchesString(item.lifecycle_status, filters.status) &&
    matchesString(item.data_quality, filters.data_quality) &&
    matchesString(item.user_friendly_status, filters.user_status) &&
    (filters.stopped === null || filters.stopped === undefined || Boolean(item.stop_triggered) === filters.stopped)
  ));
  const sorted = [...filtered].sort(strategySort(sort));
  return {
    items: sorted.slice(Math.max(0, offset), Math.max(0, offset) + Math.max(0, limit)),
    total: filtered.length,
  };
}

export function rankAnalysisBatchSync({
  items,
}: AnalysisBatchRankRequest): AnalysisBatchRankResponse {
  return {
    items: [...items].sort(analysisRankSort),
    total: items.length,
  };
}

export function downsampleChartPointsSync({
  points,
  maxPoints,
}: ChartDownsampleRequest): ChartDownsampleResponse {
  const finite = points.filter((point) => Number.isFinite(point.nav ?? point.value));
  if (maxPoints <= 0 || finite.length <= maxPoints) {
    return {
      points: finite,
      input_count: points.length,
      output_count: finite.length,
    };
  }
  return {
    points: largestTriangleThreeBuckets(finite, maxPoints),
    input_count: points.length,
    output_count: maxPoints,
  };
}

function prioritySort(
  left: GeneratedPriorityItem,
  right: GeneratedPriorityItem,
): number {
  return score(right.priority_score ?? right.production_score) - score(left.priority_score ?? left.production_score);
}

function strategySort(sort: string) {
  return (
    left: StrategyTrackingFilterSortRequest["items"][number],
    right: StrategyTrackingFilterSortRequest["items"][number],
  ): number => {
    if (sort === "current_return_desc") {
      return score(right.current_return_pct) - score(left.current_return_pct);
    }
    if (sort === "risk_desc") {
      return score(left.max_drawdown_pct) - score(right.max_drawdown_pct);
    }
    return score(right.max_gain_pct) - score(left.max_gain_pct);
  };
}

function analysisRankSort(
  left: AnalysisBatchRankRequest["items"][number],
  right: AnalysisBatchRankRequest["items"][number],
): number {
  const leftAction = left.suggestion?.is_actionable ? 1000 : 0;
  const rightAction = right.suggestion?.is_actionable ? 1000 : 0;
  return (rightAction + score(right.suggestion?.signal_score)) - (leftAction + score(left.suggestion?.signal_score));
}

function matchesString(value: string | undefined, expected?: string): boolean {
  return !expected || value === expected;
}

function score(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}

function pointValue(point: { nav?: number | null; value?: number | null }): number {
  const value = point.nav ?? point.value;
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function largestTriangleThreeBuckets<T extends { nav?: number | null; value?: number | null }>(
  data: T[],
  threshold: number,
): T[] {
  if (threshold >= data.length || threshold <= 2) {
    return data.slice(0, threshold);
  }
  const sampled: T[] = [data[0]];
  const every = (data.length - 2) / (threshold - 2);
  let a = 0;
  for (let i = 0; i < threshold - 2; i += 1) {
    const avgRangeStart = Math.floor((i + 1) * every) + 1;
    const avgRangeEnd = Math.min(Math.floor((i + 2) * every) + 1, data.length);
    const avgRangeLength = Math.max(1, avgRangeEnd - avgRangeStart);
    let avgX = 0;
    let avgY = 0;
    for (let j = avgRangeStart; j < avgRangeEnd; j += 1) {
      avgX += j;
      avgY += pointValue(data[j]);
    }
    avgX /= avgRangeLength;
    avgY /= avgRangeLength;

    const rangeOffs = Math.floor(i * every) + 1;
    const rangeTo = Math.min(Math.floor((i + 1) * every) + 1, data.length - 1);
    const pointA = data[a];
    let maxArea = -1;
    let nextA = rangeOffs;
    for (let j = rangeOffs; j < rangeTo; j += 1) {
      const area = Math.abs((a - avgX) * (pointValue(data[j]) - pointValue(pointA)) - (a - j) * (avgY - pointValue(pointA)));
      if (area > maxArea) {
        maxArea = area;
        nextA = j;
      }
    }
    sampled.push(data[nextA]);
    a = nextA;
  }
  sampled.push(data[data.length - 1]);
  return sampled;
}
