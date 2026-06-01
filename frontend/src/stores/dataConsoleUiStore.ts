import { create } from "zustand";
import { getAdminApiToken } from "../api/base";

export type DataConsoleModuleKey = "sla" | "sources" | "coverage" | "tasks" | "repair" | "inspector" | "gate";
export type CoverageStatusFilter = "all" | "blocked" | "stale";

interface DataConsoleUiStore {
  adminToken: string;
  coverageStatusFilter: CoverageStatusFilter;
  coverageScopeFilter: string;
  selectedDatasetKey: string;
  selectedScope: string;
  backfillStartDate: string;
  backfillEndDate: string;
  repairDatasetKey: string;
  repairConfirmOpen: boolean;
  inspectorSymbol: string;
  moduleLoading: Record<DataConsoleModuleKey, boolean>;
  moduleErrors: Record<DataConsoleModuleKey, string>;
  setAdminToken: (adminToken: string) => void;
  setField: (field: DataConsoleField, value: string | boolean) => void;
  setModuleLoading: (key: DataConsoleModuleKey, loading: boolean) => void;
  setModuleError: (key: DataConsoleModuleKey, error: string) => void;
}

type DataConsoleField =
  | "coverageStatusFilter"
  | "coverageScopeFilter"
  | "selectedDatasetKey"
  | "selectedScope"
  | "backfillStartDate"
  | "backfillEndDate"
  | "repairDatasetKey"
  | "repairConfirmOpen"
  | "inspectorSymbol";

const MODULE_KEYS: DataConsoleModuleKey[] = ["sla", "sources", "coverage", "tasks", "repair", "inspector", "gate"];
const today = new Date().toISOString().slice(0, 10);

export const useDataConsoleUiStore = create<DataConsoleUiStore>((set) => ({
  adminToken: getAdminApiToken(),
  coverageStatusFilter: "all",
  coverageScopeFilter: "all",
  selectedDatasetKey: "daily_bars",
  selectedScope: "all",
  backfillStartDate: today,
  backfillEndDate: today,
  repairDatasetKey: "daily_bars",
  repairConfirmOpen: false,
  inspectorSymbol: "",
  moduleLoading: emptyBoolMap(),
  moduleErrors: emptyTextMap(),
  setAdminToken: (adminToken) => set({ adminToken }),
  setField: (field, value) => set({ [field]: value } as Pick<DataConsoleUiStore, DataConsoleField>),
  setModuleLoading: (key, loading) => set((state) => ({ moduleLoading: { ...state.moduleLoading, [key]: loading } })),
  setModuleError: (key, error) => set((state) => ({ moduleErrors: { ...state.moduleErrors, [key]: error } })),
}));

function emptyBoolMap(): Record<DataConsoleModuleKey, boolean> {
  return Object.fromEntries(MODULE_KEYS.map((key) => [key, false])) as Record<DataConsoleModuleKey, boolean>;
}

function emptyTextMap(): Record<DataConsoleModuleKey, string> {
  return Object.fromEntries(MODULE_KEYS.map((key) => [key, ""])) as Record<DataConsoleModuleKey, string>;
}
