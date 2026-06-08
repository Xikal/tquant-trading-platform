export type ComputeTaskKind = "filter" | "derive" | "downsample" | "sort";

export interface ComputeRequest<T = unknown> {
  id: string;
  kind: ComputeTaskKind;
  payload: T;
}

export interface ComputeResponse<T = unknown> {
  id: string;
  ok: boolean;
  duration_ms: number;
  result?: T;
  error?: string;
}

export interface FilterPayload<T = Record<string, unknown>> {
  items: T[];
  keyword?: string;
  fields?: string[];
}

export interface SortPayload<T = object> {
  items: T[];
  key: string;
  direction?: "asc" | "desc";
  numeric?: boolean;
}

export interface DownsamplePoint {
  time: string | number;
}

export interface DownsamplePayload<T extends DownsamplePoint = DownsamplePoint> {
  points: T[];
  maxPoints: number;
}
