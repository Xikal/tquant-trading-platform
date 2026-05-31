import { create } from "zustand";
import type { HoldingEditorSeed } from "../features/app-preview/holdingEditor";
import type { MobileStrategyTabKey, MobileStrategyTabOption } from "../mobile/MobileDesignCards";
import type { MobileTab } from "../mobile/mobileTypes";

export interface HoldingEditorState {
  mode: "create" | "buy" | "edit";
  seed: HoldingEditorSeed;
}

interface MobileAuthDraft {
  username: string;
  password: string;
  register: boolean;
  formError: string;
}

interface MobileHoldingForm {
  symbol: string;
  costBasis: string;
  basePosition: string;
  availablePosition: string;
  formError: string;
}

interface MobileUiState {
  activeTab: MobileTab;
  holdingEditor: HoldingEditorState | null;
  aiOpen: boolean;
  accountMenuOpen: boolean;
  offline: boolean;
  sectorSettingsOpen: boolean;
  excludedSectors: string[];
  availableSectors: string[];
  sectorSettingsSaving: boolean;
  signalToastVisible: boolean;
  strategyFilter: MobileStrategyTabKey;
  strategyTabs: MobileStrategyTabOption[];
  playbookLoading: boolean;
  playbookError: string;
  authLoading: boolean;
  authError: string;
  updateChecking: boolean;
  updateVerifying: boolean;
  updateError: string;
  authDraft: MobileAuthDraft;
  holdingQuery: string;
  holdingForm: MobileHoldingForm;
  sectorSelection: string[];
  setActiveTab: (activeTab: MobileTab) => void;
  setHoldingEditor: (holdingEditor: HoldingEditorState | null) => void;
  setAiOpen: (aiOpen: boolean) => void;
  setAccountMenuOpen: (accountMenuOpen: boolean | ((current: boolean) => boolean)) => void;
  setOffline: (offline: boolean) => void;
  setSectorSettingsOpen: (sectorSettingsOpen: boolean) => void;
  setExcludedSectors: (excludedSectors: string[]) => void;
  setAvailableSectors: (availableSectors: string[]) => void;
  setSectorSettingsSaving: (sectorSettingsSaving: boolean) => void;
  setSignalToastVisible: (signalToastVisible: boolean) => void;
  setStrategyFilter: (strategyFilter: MobileStrategyTabKey | ((current: MobileStrategyTabKey) => MobileStrategyTabKey)) => void;
  setStrategyTabs: (strategyTabs: MobileStrategyTabOption[]) => void;
  setPlaybookLoading: (playbookLoading: boolean) => void;
  setPlaybookError: (playbookError: string) => void;
  setAuthLoading: (authLoading: boolean) => void;
  setAuthError: (authError: string) => void;
  setUpdateChecking: (updateChecking: boolean) => void;
  setUpdateVerifying: (updateVerifying: boolean) => void;
  setUpdateError: (updateError: string) => void;
  setAuthDraft: (patch: Partial<MobileAuthDraft>) => void;
  setHoldingQuery: (query: string) => void;
  setHoldingForm: (patch: Partial<MobileHoldingForm>) => void;
  resetHoldingForm: (seed: HoldingEditorSeed) => void;
  setSectorSelection: (selection: string[] | ((current: string[]) => string[])) => void;
}

export const useMobileUiStore = create<MobileUiState>((set) => ({
  activeTab: "home",
  holdingEditor: null,
  aiOpen: false,
  accountMenuOpen: false,
  offline: typeof navigator === "undefined" ? false : !navigator.onLine,
  sectorSettingsOpen: false,
  excludedSectors: [],
  availableSectors: [],
  sectorSettingsSaving: false,
  signalToastVisible: false,
  strategyFilter: "first_board",
  strategyTabs: [],
  playbookLoading: false,
  playbookError: "",
  authLoading: true,
  authError: "",
  updateChecking: false,
  updateVerifying: false,
  updateError: "",
  authDraft: {
    username: "",
    password: "",
    register: false,
    formError: "",
  },
  holdingQuery: "",
  holdingForm: {
    symbol: "",
    costBasis: "",
    basePosition: "0",
    availablePosition: "0",
    formError: "",
  },
  sectorSelection: [],
  setActiveTab: (activeTab) => set({ activeTab }),
  setHoldingEditor: (holdingEditor) => set({ holdingEditor }),
  setAiOpen: (aiOpen) => set({ aiOpen }),
  setAccountMenuOpen: (accountMenuOpen) => set((state) => ({
    accountMenuOpen: typeof accountMenuOpen === "function" ? accountMenuOpen(state.accountMenuOpen) : accountMenuOpen,
  })),
  setOffline: (offline) => set({ offline }),
  setSectorSettingsOpen: (sectorSettingsOpen) => set({ sectorSettingsOpen }),
  setExcludedSectors: (excludedSectors) => set({ excludedSectors }),
  setAvailableSectors: (availableSectors) => set({ availableSectors }),
  setSectorSettingsSaving: (sectorSettingsSaving) => set({ sectorSettingsSaving }),
  setSignalToastVisible: (signalToastVisible) => set({ signalToastVisible }),
  setStrategyFilter: (strategyFilter) => set((state) => ({
    strategyFilter: typeof strategyFilter === "function" ? strategyFilter(state.strategyFilter) : strategyFilter,
  })),
  setStrategyTabs: (strategyTabs) => set({ strategyTabs }),
  setPlaybookLoading: (playbookLoading) => set({ playbookLoading }),
  setPlaybookError: (playbookError) => set({ playbookError }),
  setAuthLoading: (authLoading) => set({ authLoading }),
  setAuthError: (authError) => set({ authError }),
  setUpdateChecking: (updateChecking) => set({ updateChecking }),
  setUpdateVerifying: (updateVerifying) => set({ updateVerifying }),
  setUpdateError: (updateError) => set({ updateError }),
  setAuthDraft: (patch) => set((state) => ({ authDraft: { ...state.authDraft, ...patch } })),
  setHoldingQuery: (holdingQuery) => set({ holdingQuery }),
  setHoldingForm: (patch) => set((state) => ({ holdingForm: { ...state.holdingForm, ...patch } })),
  resetHoldingForm: (seed) => set({
    holdingForm: {
      symbol: seed.symbol,
      costBasis: typeof seed.cost_basis === "number" && Number.isFinite(seed.cost_basis) ? String(seed.cost_basis) : "",
      basePosition: String(seed.base_position),
      availablePosition: String(seed.available_position),
      formError: "",
    },
  }),
  setSectorSelection: (selection) => set((state) => ({
    sectorSelection: typeof selection === "function" ? selection(state.sectorSelection) : selection,
  })),
}));
