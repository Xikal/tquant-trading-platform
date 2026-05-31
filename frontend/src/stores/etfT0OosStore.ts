import { create } from "zustand";

interface EtfT0OosStore {
  selectedDatasetKey: string;
  loading: boolean;
  error: string;
  setSelectedDatasetKey: (selectedDatasetKey: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string) => void;
}

export const useEtfT0OosStore = create<EtfT0OosStore>((set) => ({
  selectedDatasetKey: "",
  loading: false,
  error: "",
  setSelectedDatasetKey: (selectedDatasetKey) => set({ selectedDatasetKey }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
