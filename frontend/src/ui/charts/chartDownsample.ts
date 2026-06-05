import { frontendPerformanceFlagEnabled } from "../../config/frontendPerformanceFlags";
import { downsampleChartPointsSync } from "../../workers/computeSync";
import { downsampleChartPoints } from "../../workers/workerClient";
import type { ChartPoint } from "../../workers/protocol";

export function downsampleDenseChartPoints<T extends ChartPoint>(
  points: T[],
  maxPoints = 1200,
): T[] {
  if (!frontendPerformanceFlagEnabled("frontend_canvas_chart_island_enabled") || points.length <= maxPoints) {
    return points;
  }
  return downsampleChartPointsSync({ maxPoints, points }).points as T[];
}

export async function downsampleDenseChartPointsAsync<T extends ChartPoint>(
  points: T[],
  maxPoints = 1200,
): Promise<T[]> {
  if (!frontendPerformanceFlagEnabled("frontend_canvas_chart_island_enabled") || points.length <= maxPoints) {
    return points;
  }
  const result = await downsampleChartPoints({ maxPoints, points });
  return result.points as T[];
}
