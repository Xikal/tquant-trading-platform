import { create } from "zustand";
import type {
  EtfT0OosDataset,
  EtfT0OosLatestResponse,
  EtfT0OosValidationResponse,
} from "../types/etfT0Oos";

interface EtfT0OosStore {
  datasets: EtfT0OosDataset[];
  selectedDatasetKey: string;
  latest: EtfT0OosLatestResponse | null;
  validation: EtfT0OosValidationResponse | null;
  loading: boolean;
  error: string;
  setDatasets: (datasets: EtfT0OosDataset[]) => void;
  setSelectedDatasetKey: (selectedDatasetKey: string) => void;
  setLatest: (latest: EtfT0OosLatestResponse | null) => void;
  setValidation: (validation: EtfT0OosValidationResponse | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string) => void;
}

export const useEtfT0OosStore = create<EtfT0OosStore>((set) => ({
  datasets: [],
  selectedDatasetKey: "",
  latest: null,
  validation: null,
  loading: false,
  error: "",
  setDatasets: (datasets) => set((state) => ({
    datasets,
    selectedDatasetKey: state.selectedDatasetKey || datasets[0]?.dataset_key || "",
  })),
  setSelectedDatasetKey: (selectedDatasetKey) => set({ selectedDatasetKey }),
  setLatest: (latest) => set({ latest }),
  setValidation: (validation) => set({ validation }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
