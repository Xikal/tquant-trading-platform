import type {
  DataQualityCoverageResponse,
  DataQualitySlaResponse,
  DataQualitySnapshotItem,
  TradeDataGateResponse,
} from "../../api/dataQuality";
import type { InstrumentInspectorResponse } from "../../api/dataConsoleInspector";
import type { RuntimeTaskOut } from "../../api/runtimeTasks";
import type { DataSourceProbeResponse } from "../../types";

export type DataConsoleStatus = "ok" | "warn" | "blocked";

export interface DataConsoleSummary {
  status: DataConsoleStatus;
  conclusion: string;
  total: number;
  blocked: number;
  stale: number;
  missing: number;
  checkedAt: string;
}

export interface DataConsoleData {
  sla: DataQualitySlaResponse | null;
  sourceHealth: DataSourceProbeResponse | null;
  coverage: DataQualityCoverageResponse | null;
  tasks: RuntimeTaskOut[];
  inspector: InstrumentInspectorResponse | null;
  gate: TradeDataGateResponse | null;
}

export interface DataConsoleActions {
  refreshSla: () => Promise<void>;
  refreshSources: () => Promise<void>;
  refreshCoverage: (next?: { dataset_key: string; scope: string }) => Promise<void>;
  refreshTasks: () => Promise<void>;
  refreshGate: () => Promise<void>;
  refreshAll: () => Promise<void>;
  syncInstruments: () => Promise<void>;
  refreshCloseData: () => Promise<void>;
  backfill: () => Promise<void>;
  repairDryRun: () => Promise<void>;
  repairApply: () => Promise<void>;
  inspectSymbol: () => Promise<void>;
}

export function buildDataConsoleSummary(items: DataQualitySnapshotItem[]): DataConsoleSummary {
  const blocked = items.filter((item) => criticalStatus(item.status)).length;
  const stale = items.filter((item) => item.stale || item.status === "stale").length;
  const missing = items.reduce((total, item) => total + Number(item.missing_days || 0), 0);
  const checkedValues = items.map((item) => item.checked_at || item.as_of_date).filter(Boolean).sort();
  const checkedAt = checkedValues[checkedValues.length - 1] ?? "--";
  const status: DataConsoleStatus = blocked > 0 ? "blocked" : stale > 0 || missing > 0 ? "warn" : "ok";
  return {
    status,
    conclusion: conclusionText(status),
    total: items.length,
    blocked,
    stale,
    missing,
    checkedAt,
  };
}

export function criticalStatus(status: string): boolean {
  return ["fail", "blocked_by_data", "unavailable", "missing"].includes(status);
}

export function conclusionText(status: DataConsoleStatus): string {
  if (status === "blocked") return "关键数据缺失或阻断，暂不建议据此下单";
  if (status === "warn") return "部分数据偏旧，注意甄别";
  return "数据正常，可放心使用";
}

export function gateTone(gate: TradeDataGateResponse | null): DataConsoleStatus {
  if (!gate) return "warn";
  if (gate.checks.some((item) => item.severity === "red")) return "blocked";
  if (gate.checks.some((item) => item.severity === "yellow")) return "warn";
  return "ok";
}
