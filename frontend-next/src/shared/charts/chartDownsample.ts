import { downsample } from "../workers/computeSync";
import { downsamplePoints } from "../workers/workerClient";
import type { DownsamplePoint } from "../workers/protocol";

export type ChartPoint = DownsamplePoint;

export async function downsampleChartPoints<T extends ChartPoint>(points: T[], maxPoints = 240): Promise<T[]> {
  if (points.length <= maxPoints || maxPoints <= 0) return points;
  const response = await downsamplePoints({ points, maxPoints });
  return (response.result as T[] | undefined) ?? downsample({ points, maxPoints });
}
