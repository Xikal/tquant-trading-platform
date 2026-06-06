import { describe, expect, it, vi } from "vitest";
import { loadMonitorWorkspaceFirstScreen, monitorWorkspaceViewForPage } from "./monitorWorkspaceLoaders";

describe("loadMonitorWorkspaceFirstScreen", () => {
  it("uses the BFF action view for monitor first screen", async () => {
    const fetchWorkspace = vi.fn(async () => workspaceFixture());
    const fetchLegacy = vi.fn();

    const result = await loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: false,
      bffEnabled: true,
      fetchWorkspace,
      fetchLegacy,
      fetchPriorityBoard: vi.fn(),
      fetchHourlyHistory: vi.fn(),
      fetchRuntime: vi.fn(),
      hasAdminToken: () => false,
    });

    expect(fetchWorkspace).toHaveBeenCalledWith(12, "action");
    expect(fetchLegacy).not.toHaveBeenCalled();
    expect(result.source).toBe("bff");
  });

  it("falls back to legacy only when the aggregate endpoint is explicitly disabled", async () => {
    const disabled = new Error("monitor BFF aggregate disabled") as Error & { status: number };
    disabled.status = 404;
    const fetchWorkspace = vi.fn(async () => {
      throw disabled;
    });
    const fetchLegacy = vi.fn(async () => ({ source: "legacy" }));

    const result = await loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: false,
      bffEnabled: true,
      fetchWorkspace,
      fetchLegacy,
      fetchPriorityBoard: vi.fn(),
      fetchHourlyHistory: vi.fn(),
      fetchRuntime: vi.fn(),
      hasAdminToken: () => false,
    });

    expect(result.source).toBe("legacy");
    expect(fetchLegacy).toHaveBeenCalledTimes(1);
  });

  it("returns a retryable error for transient BFF failures instead of issuing legacy fan-out", async () => {
    const transient = new Error("upstream timeout") as Error & { status: number };
    transient.status = 500;
    const fetchLegacy = vi.fn();

    await expect(loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: false,
      bffEnabled: true,
      fetchWorkspace: vi.fn(async () => {
        throw transient;
      }),
      fetchLegacy,
      fetchPriorityBoard: vi.fn(),
      fetchHourlyHistory: vi.fn(),
      fetchRuntime: vi.fn(),
      hasAdminToken: () => false,
    })).rejects.toThrow("upstream timeout");

    expect(fetchLegacy).not.toHaveBeenCalled();
  });

  it("loads hourly and runtime fallbacks only when omitted from the BFF payload", async () => {
    const fetchHourlyHistory = vi.fn(async () => ({ items: [] }));
    const fetchRuntime = vi.fn(async () => runtimeStatusFixture());

    const result = await loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: true,
      bffEnabled: true,
      fetchWorkspace: vi.fn(async () => {
        const { runtime: _runtime, ...workspace } = workspaceFixture();
        return {
          ...workspace,
          hourly_snapshot_history: undefined,
        };
      }),
      fetchLegacy: vi.fn(),
      fetchPriorityBoard: vi.fn(),
      fetchHourlyHistory,
      fetchRuntime,
      hasAdminToken: () => true,
    });

    expect(fetchHourlyHistory).toHaveBeenCalledTimes(1);
    expect(fetchRuntime).toHaveBeenCalledTimes(1);
    expect(result.fallbackResults).toHaveLength(2);
  });

  it("requests the priority-board cache fallback when the nested BFF snapshot is empty", async () => {
    const fetchPriorityBoard = vi.fn(async () => priorityBoardFixture());

    const result = await loadMonitorWorkspaceFirstScreen({
      page: "monitor",
      priorityLimit: 12,
      includeRuntime: false,
      bffEnabled: true,
      fetchWorkspace: vi.fn(async () => ({
        ...workspaceFixture(),
        monitor_snapshot: {
          updated_at: "2026-06-06T09:30:00+08:00",
          watchlist_signals: [],
          priority_board: { items: [] },
        },
      })),
      fetchLegacy: vi.fn(),
      fetchPriorityBoard,
      fetchHourlyHistory: vi.fn(),
      fetchRuntime: vi.fn(),
      hasAdminToken: () => false,
    });

    expect(fetchPriorityBoard).toHaveBeenCalledWith(12, "baseline", "cache");
    expect(result.priorityBoardFallback).toEqual(priorityBoardFixture());
  });
});

describe("monitorWorkspaceViewForPage", () => {
  it("maps monitor data routes to BFF view variants", () => {
    expect(monitorWorkspaceViewForPage("monitor")).toBe("action");
    expect(monitorWorkspaceViewForPage("monitor-market")).toBe("market");
    expect(monitorWorkspaceViewForPage("paper")).toBe("full");
  });
});

function workspaceFixture() {
  return {
    api_version: "v1",
    generated_at: "2026-06-06T09:30:00+08:00",
    schema_version: "test",
    partial_errors: [],
    hourly_snapshot_history: [],
    runtime: null,
    monitor_snapshot: {
      updated_at: "2026-06-06T09:30:00+08:00",
      watchlist_signals: [],
      priority_board: priorityBoardFixture(),
    },
  } as any;
}

function priorityBoardFixture() {
  return {
    items: [
      {
        symbol: "600000",
        priority_score: 88.5,
        production_score: 71.2,
        buy_signal_state: "near_entry",
        elite_watch_score: 63.1,
        latest_price: 10.1,
        name: "浦发银行",
      },
    ],
  } as any;
}

function runtimeStatusFixture() {
  return {
    app_name: "test",
    api_prefix: "/api",
    database_backend: "sqlite",
    database_url_masked: "sqlite:///test.db",
    runtime_database_url_masked: "sqlite:///test.db",
    runtime_env_path: ".env",
    runtime_env_exists: true,
    runtime_database_override: false,
    runtime_database_matches_settings: true,
    runtime_llm_secret_persisted: false,
    settings_consistency_status: "ok",
    settings_consistency_text: "ok",
    frontend_dist_path: "dist",
    frontend_dist_ready: true,
    llm_configured: false,
    data_source: "mock",
    data_source_base_url: "mock",
    cors_origins: [],
    ready_checks: {},
  };
}
