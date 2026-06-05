import { vi } from "vitest";
import type { MonitorActionPageProps } from "./MonitorActionPage";

export function baseMonitorPageProps(overrides: Partial<MonitorActionPageProps> = {}): MonitorActionPageProps {
  return {
    priorityBoard: null,
    marketBreadth: null,
    marketPulse: null,
    hourlySnapshotHistory: [],
    reviewStatus: null,
    reviewReports: [],
    keyLevelAlerts: [],
    sectorEtfT0: null,
    sectorRelativeStrength: null,
    pairedHedge: null,
    priorityCards: [],
    watchCards: [],
    runtime: null,
    instrumentSyncStatus: null,
    watchDraft: { symbol: "", name: "", base_position: "", available_position: "", cost_basis: "", memo: "" },
    setWatchDraft: vi.fn(),
    editingWatchSymbol: "",
    loading: "",
    onRefresh: vi.fn(),
    onSync: vi.fn(),
    onAi: vi.fn(),
    onGoPlaybook: vi.fn(),
    onSelect: vi.fn(),
    onAnalyze: vi.fn(),
    onEdit: vi.fn(),
    onRemove: vi.fn(),
    onAddWatchlist: vi.fn(),
    onCancelEdit: vi.fn(),
    ...overrides,
  };
}
