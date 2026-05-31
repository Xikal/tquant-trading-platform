import { create } from "zustand";

export type AppPreviewTab = "home" | "low_buy";

interface AppPreviewStore {
  activeTab: AppPreviewTab;
  loading: boolean;
  tabLoading: boolean;
  detailLoading: boolean;
  actionLoading: boolean;
  error: string;
  message: string;
  pulseTime: string;
  priorityPulseTime: string;
  setActiveTab: (value: AppPreviewTab) => void;
  setLoading: (value: boolean) => void;
  setTabLoading: (value: boolean) => void;
  setDetailLoading: (value: boolean) => void;
  setActionLoading: (value: boolean) => void;
  setError: (value: string) => void;
  setMessage: (value: string) => void;
  setPulseTime: (value: string) => void;
  setPriorityPulseTime: (value: string) => void;
}

export const useAppPreviewStore = create<AppPreviewStore>((set) => ({
  activeTab: "home",
  loading: true,
  tabLoading: false,
  detailLoading: false,
  actionLoading: false,
  error: "",
  message: "",
  pulseTime: "--",
  priorityPulseTime: "--",
  setActiveTab: (activeTab) => set({ activeTab }),
  setLoading: (loading) => set({ loading }),
  setTabLoading: (tabLoading) => set({ tabLoading }),
  setDetailLoading: (detailLoading) => set({ detailLoading }),
  setActionLoading: (actionLoading) => set({ actionLoading }),
  setError: (error) => set({ error }),
  setMessage: (message) => set({ message }),
  setPulseTime: (pulseTime) => set({ pulseTime }),
  setPriorityPulseTime: (priorityPulseTime) => set({ priorityPulseTime }),
}));
