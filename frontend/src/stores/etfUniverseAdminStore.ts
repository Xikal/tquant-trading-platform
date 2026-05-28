import { create } from "zustand";
import type {
  EtfUniverseAdminResponse,
  EtfUniverseOverrideMap,
  EtfUniverseRepairDraftResponse,
} from "../types/etfUniverseAdmin";

interface EtfUniverseAdminStore {
  payload: EtfUniverseAdminResponse | null;
  draftOverrides: EtfUniverseOverrideMap;
  repairDraft: EtfUniverseRepairDraftResponse | null;
  filter: string;
  repairSymbol: string;
  repairName: string;
  repairCategory: string;
  version: string;
  description: string;
  activate: boolean;
  confirmHighRisk: boolean;
  rollbackVersion: string;
  loading: boolean;
  error: string;
  message: string;
  setPayload: (payload: EtfUniverseAdminResponse | null) => void;
  setDraftOverrides: (draftOverrides: EtfUniverseOverrideMap) => void;
  setRepairDraft: (repairDraft: EtfUniverseRepairDraftResponse | null) => void;
  setField: <K extends keyof EtfUniverseAdminStore>(key: K, value: EtfUniverseAdminStore[K]) => void;
  mergeDraftOverrides: (draft: EtfUniverseOverrideMap) => void;
}

export const useEtfUniverseAdminStore = create<EtfUniverseAdminStore>((set) => ({
  payload: null,
  draftOverrides: {},
  repairDraft: null,
  filter: "",
  repairSymbol: "",
  repairName: "",
  repairCategory: "",
  version: `etf-universe-${Date.now()}`,
  description: "",
  activate: false,
  confirmHighRisk: false,
  rollbackVersion: "",
  loading: false,
  error: "",
  message: "",
  setPayload: (payload) => set({
    payload,
    draftOverrides: payload?.normalized_overrides ?? {},
    rollbackVersion: payload?.recent_versions?.[0]?.version ?? "",
  }),
  setDraftOverrides: (draftOverrides) => set({ draftOverrides }),
  setRepairDraft: (repairDraft) => set({ repairDraft }),
  setField: (key, value) => set({ [key]: value } as Partial<EtfUniverseAdminStore>),
  mergeDraftOverrides: (draft) => set((state) => ({
    draftOverrides: { ...state.draftOverrides, ...draft },
  })),
}));
