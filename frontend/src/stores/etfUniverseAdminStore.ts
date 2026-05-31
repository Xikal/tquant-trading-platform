import { create } from "zustand";
import type {
  EtfUniverseOverrideMap,
} from "../types/etfUniverseAdmin";

interface EtfUniverseAdminStore {
  draftOverrides: EtfUniverseOverrideMap;
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
  setDraftOverrides: (draftOverrides: EtfUniverseOverrideMap) => void;
  setField: <K extends keyof EtfUniverseAdminStore>(key: K, value: EtfUniverseAdminStore[K]) => void;
  mergeDraftOverrides: (draft: EtfUniverseOverrideMap) => void;
}

export const useEtfUniverseAdminStore = create<EtfUniverseAdminStore>((set) => ({
  draftOverrides: {},
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
  setDraftOverrides: (draftOverrides) => set({ draftOverrides }),
  setField: (key, value) => set({ [key]: value } as Partial<EtfUniverseAdminStore>),
  mergeDraftOverrides: (draft) => set((state) => ({
    draftOverrides: { ...state.draftOverrides, ...draft },
  })),
}));
