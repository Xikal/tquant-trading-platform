import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { components } from "../../generated/api-types";
import { monitorSnapshotOptions } from "./monitor";

type MonitorWorkspace = components["schemas"]["MonitorWorkspaceBffResponse"];

describe("monitor server queries", () => {
  it("keeps the full response in query cache while select returns only monitor snapshot", async () => {
    const payload: MonitorWorkspace = {
      api_version: "v1",
      generated_at: "2026-05-31T10:00:00+08:00",
      monitor_snapshot: {
        priority_board: {},
        watchlist_signals: [],
        sector_etf_t0: {},
        updated_at: "2026-05-31T10:00:00+08:00",
      },
      market_breadth: null,
      market_pulse: null,
      review_status: null,
      review_reports: [],
      sector_relative_strength: null,
      paired_hedge: null,
      partial_errors: [],
      schema_version: "v14",
    };
    const fetchMonitorWorkspace = vi.fn(async () => payload);
    const options = monitorSnapshotOptions({ priorityLimit: 3, fetchMonitorWorkspace });
    const client = new QueryClient();

    await client.fetchQuery(options);
    const defaultedOptions = client.defaultQueryOptions(options);
    const observer = new QueryObserver(client, defaultedOptions);
    const selected = observer.getOptimisticResult(defaultedOptions).data;

    expect(fetchMonitorWorkspace).toHaveBeenCalledWith(3);
    expect(selected).toBe(payload.monitor_snapshot);
    expect(client.getQueryData(options.queryKey)).toBe(payload);
  });
});
