import type {
  BacktestMonthlyReturnsResponse,
  BacktestStatus,
  BacktestStrategyCorrelationResponse,
  ResearchListParams,
} from "./backtestTypes";

export function buildListQuery({ page, pageSize, limit, offset, status }: ResearchListParams = {}): URLSearchParams {
  const params = new URLSearchParams();
  const resolvedLimit = limit ?? pageSize ?? 20;
  const resolvedOffset = offset ?? ((page ?? 1) - 1) * resolvedLimit;
  params.set("limit", String(resolvedLimit));
  params.set("offset", String(Math.max(0, resolvedOffset)));
  if (status && status !== "all") {
    params.set("status", status);
  }
  return params;
}

export function normalizeBacktestStatus(status: BacktestStatus): BacktestStatus {
  return status;
}

export function toBackendStatus(status: BacktestStatus): BacktestStatus {
  if (status === "pending") return "queued";
  if (status === "completed") return "succeeded";
  return status;
}

export function normalizeMonthlyReturns(payload: BacktestMonthlyReturnsResponse): BacktestMonthlyReturnsResponse {
  return {
    ...payload,
    items: payload.items ?? [],
  };
}

export function normalizeStrategyCorrelation(payload: BacktestStrategyCorrelationResponse): BacktestStrategyCorrelationResponse {
  return {
    ...payload,
    strategies: payload.strategies ?? [],
    matrix: payload.matrix ?? [],
  };
}
