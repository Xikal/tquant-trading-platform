import { create } from "zustand";
import { getAdminApiToken } from "../api/base";
import type { SettingsTabKey } from "../features/settings/SettingsPageTabs";
import type { SettingsDraft } from "../features/workspace-shared/workspaceTypes";

export type SettingsQuantCardKey = "ml" | "paperExit" | "sectorEtf";

interface SettingsQuantCardState {
  draft: Record<string, string>;
  enabled: boolean;
  loading: boolean;
  saved: boolean;
  error: string;
}

interface SettingsMfaState {
  code: string;
  loading: boolean;
  message: string;
  error: string;
}

const EMPTY_QUANT_CARD: SettingsQuantCardState = {
  draft: {},
  enabled: true,
  loading: false,
  saved: false,
  error: "",
};

interface SettingsUiStore {
  activeTab: SettingsTabKey;
  factorDraft: Record<string, string>;
  settingsDraft: SettingsDraft;
  sectorQuery: string;
  savedSection: string;
  sectorDraft: string[];
  featureFlagError: string;
  operationAuditError: string;
  operationAuditLoading: boolean;
  dataQualityError: string;
  dataQualityLoading: boolean;
  dataQualityRepairLoading: boolean;
  quantCards: Record<SettingsQuantCardKey, SettingsQuantCardState>;
  mfa: SettingsMfaState;
  setActiveTab: (tab: SettingsTabKey) => void;
  setFactorDraft: (draft: Record<string, string> | ((current: Record<string, string>) => Record<string, string>)) => void;
  setSettingsDraft: (draft: SettingsDraft | ((current: SettingsDraft) => SettingsDraft)) => void;
  setSectorQuery: (query: string) => void;
  setSavedSection: (section: string) => void;
  setSectorDraft: (draft: string[] | ((current: string[]) => string[])) => void;
  setFeatureFlagError: (featureFlagError: string) => void;
  setOperationAuditError: (operationAuditError: string) => void;
  setOperationAuditLoading: (operationAuditLoading: boolean) => void;
  setDataQualityError: (dataQualityError: string) => void;
  setDataQualityLoading: (dataQualityLoading: boolean) => void;
  setDataQualityRepairLoading: (dataQualityRepairLoading: boolean) => void;
  setQuantCard: (key: SettingsQuantCardKey, patch: Partial<SettingsQuantCardState>) => void;
  setMfa: (patch: Partial<SettingsMfaState>) => void;
}

export const useSettingsUiStore = create<SettingsUiStore>((set) => ({
  activeTab: "account",
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
  featureFlagError: "",
  operationAuditError: "",
  operationAuditLoading: false,
  dataQualityError: "",
  dataQualityLoading: false,
  dataQualityRepairLoading: false,
  quantCards: {
    ml: { ...EMPTY_QUANT_CARD },
    paperExit: { ...EMPTY_QUANT_CARD },
    sectorEtf: { ...EMPTY_QUANT_CARD },
  },
  mfa: {
    code: "",
    loading: false,
    message: "",
    error: "",
  },
  setActiveTab: (activeTab) => set({ activeTab }),
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
  setFeatureFlagError: (featureFlagError) => set({ featureFlagError }),
  setOperationAuditError: (operationAuditError) => set({ operationAuditError }),
  setOperationAuditLoading: (operationAuditLoading) => set({ operationAuditLoading }),
  setDataQualityError: (dataQualityError) => set({ dataQualityError }),
  setDataQualityLoading: (dataQualityLoading) => set({ dataQualityLoading }),
  setDataQualityRepairLoading: (dataQualityRepairLoading) => set({ dataQualityRepairLoading }),
  setQuantCard: (key, patch) => set((state) => ({
    quantCards: {
      ...state.quantCards,
      [key]: { ...state.quantCards[key], ...patch },
    },
  })),
  setMfa: (patch) => set((state) => ({ mfa: { ...state.mfa, ...patch } })),
}));
