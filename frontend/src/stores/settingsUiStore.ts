import { create } from "zustand";
import type { FeatureFlagAuditItem, FeatureFlagItem } from "../api/featureFlags";
import { getAdminApiToken } from "../api/base";
import type { OperationAuditItem } from "../api/operationAudit";
import type { QuantParameterSet } from "../api/quantParameters";
import type { SettingsTabKey } from "../features/settings/SettingsPageTabs";
import type {
  AdminMetricsResponse,
  AdminTaskStatus,
  AuthMfaSetupResponse,
  FactorWeightsResponse,
  LowBuyStrategyGovernanceResponse,
  SettingsPayload,
  UserSectorExclusionsResponse,
} from "../types";
import type { SettingsDraft } from "../features/workspace-shared/workspaceTypes";

export type SettingsQuantCardKey = "ml" | "paperExit" | "sectorEtf";

interface SettingsQuantCardState {
  current: QuantParameterSet | null;
  draft: Record<string, string>;
  enabled: boolean;
  loading: boolean;
  saved: boolean;
  error: string;
}

interface SettingsMfaState {
  setup: AuthMfaSetupResponse | null;
  code: string;
  loading: boolean;
  message: string;
  error: string;
}

const EMPTY_QUANT_CARD: SettingsQuantCardState = {
  current: null,
  draft: {},
  enabled: true,
  loading: false,
  saved: false,
  error: "",
};

interface SettingsUiStore {
  activeTab: SettingsTabKey;
  settings: SettingsPayload | null;
  factorWeights: FactorWeightsResponse | null;
  adminTasks: AdminTaskStatus[];
  strategyGovernance: LowBuyStrategyGovernanceResponse | null;
  sectorExclusions: UserSectorExclusionsResponse | null;
  adminMetrics: AdminMetricsResponse | null;
  factorDraft: Record<string, string>;
  settingsDraft: SettingsDraft;
  sectorQuery: string;
  savedSection: string;
  sectorDraft: string[];
  featureFlags: FeatureFlagItem[];
  featureFlagAudits: FeatureFlagAuditItem[];
  featureFlagError: string;
  operationAudits: OperationAuditItem[];
  operationAuditError: string;
  operationAuditLoading: boolean;
  quantCards: Record<SettingsQuantCardKey, SettingsQuantCardState>;
  mfa: SettingsMfaState;
  setActiveTab: (tab: SettingsTabKey) => void;
  setSettings: (settings: SettingsPayload | null) => void;
  setFactorWeights: (factorWeights: FactorWeightsResponse | null) => void;
  setAdminTasks: (adminTasks: AdminTaskStatus[]) => void;
  setStrategyGovernance: (strategyGovernance: LowBuyStrategyGovernanceResponse | null) => void;
  setSectorExclusions: (sectorExclusions: UserSectorExclusionsResponse | null) => void;
  setAdminMetrics: (adminMetrics: AdminMetricsResponse | null) => void;
  setFactorDraft: (draft: Record<string, string> | ((current: Record<string, string>) => Record<string, string>)) => void;
  setSettingsDraft: (draft: SettingsDraft | ((current: SettingsDraft) => SettingsDraft)) => void;
  setSectorQuery: (query: string) => void;
  setSavedSection: (section: string) => void;
  setSectorDraft: (draft: string[] | ((current: string[]) => string[])) => void;
  setFeatureFlags: (featureFlags: FeatureFlagItem[] | ((current: FeatureFlagItem[]) => FeatureFlagItem[])) => void;
  setFeatureFlagAudits: (featureFlagAudits: FeatureFlagAuditItem[]) => void;
  setFeatureFlagError: (featureFlagError: string) => void;
  setOperationAudits: (operationAudits: OperationAuditItem[]) => void;
  setOperationAuditError: (operationAuditError: string) => void;
  setOperationAuditLoading: (operationAuditLoading: boolean) => void;
  setQuantCard: (key: SettingsQuantCardKey, patch: Partial<SettingsQuantCardState>) => void;
  setMfa: (patch: Partial<SettingsMfaState>) => void;
}

export const useSettingsUiStore = create<SettingsUiStore>((set) => ({
  activeTab: "account",
  settings: null,
  factorWeights: null,
  adminTasks: [],
  strategyGovernance: null,
  sectorExclusions: null,
  adminMetrics: null,
  factorDraft: {},
  settingsDraft: {
    adminToken: getAdminApiToken(),
    llm_provider: "",
    llm_api_key: "",
    llm_base_url: "",
    llm_model: "",
    data_source: "",
    data_source_base_url: "",
    risk_max_single_loss_pct: "",
    risk_max_daily_loss_pct: "",
    risk_pause_after_losses: "",
    strategy_min_profit_pct: "",
  },
  sectorQuery: "",
  savedSection: "",
  sectorDraft: [],
  featureFlags: [],
  featureFlagAudits: [],
  featureFlagError: "",
  operationAudits: [],
  operationAuditError: "",
  operationAuditLoading: false,
  quantCards: {
    ml: { ...EMPTY_QUANT_CARD },
    paperExit: { ...EMPTY_QUANT_CARD },
    sectorEtf: { ...EMPTY_QUANT_CARD },
  },
  mfa: {
    setup: null,
    code: "",
    loading: false,
    message: "",
    error: "",
  },
  setActiveTab: (activeTab) => set({ activeTab }),
  setSettings: (settings) => set({ settings }),
  setFactorWeights: (factorWeights) => set({ factorWeights }),
  setAdminTasks: (adminTasks) => set({ adminTasks }),
  setStrategyGovernance: (strategyGovernance) => set({ strategyGovernance }),
  setSectorExclusions: (sectorExclusions) => set({ sectorExclusions }),
  setAdminMetrics: (adminMetrics) => set({ adminMetrics }),
  setFactorDraft: (draft) => set((state) => ({
    factorDraft: typeof draft === "function" ? draft(state.factorDraft) : draft,
  })),
  setSettingsDraft: (draft) => set((state) => ({
    settingsDraft: typeof draft === "function" ? draft(state.settingsDraft) : draft,
  })),
  setSectorQuery: (sectorQuery) => set({ sectorQuery }),
  setSavedSection: (savedSection) => set({ savedSection }),
  setSectorDraft: (draft) => set((state) => ({
    sectorDraft: typeof draft === "function" ? draft(state.sectorDraft) : draft,
  })),
  setFeatureFlags: (featureFlags) => set((state) => ({
    featureFlags: typeof featureFlags === "function" ? featureFlags(state.featureFlags) : featureFlags,
  })),
  setFeatureFlagAudits: (featureFlagAudits) => set({ featureFlagAudits }),
  setFeatureFlagError: (featureFlagError) => set({ featureFlagError }),
  setOperationAudits: (operationAudits) => set({ operationAudits }),
  setOperationAuditError: (operationAuditError) => set({ operationAuditError }),
  setOperationAuditLoading: (operationAuditLoading) => set({ operationAuditLoading }),
  setQuantCard: (key, patch) => set((state) => ({
    quantCards: {
      ...state.quantCards,
      [key]: { ...state.quantCards[key], ...patch },
    },
  })),
  setMfa: (patch) => set((state) => ({ mfa: { ...state.mfa, ...patch } })),
}));
