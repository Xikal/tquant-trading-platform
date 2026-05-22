import { create } from "zustand";
import type { IntradayConfirmationItem } from "../types";

interface PaperIntradayStore {
  intradayConfirmations: IntradayConfirmationItem[];
  setIntradayConfirmations: (items: IntradayConfirmationItem[]) => void;
}

export const usePaperIntradayStore = create<PaperIntradayStore>((set) => ({
  intradayConfirmations: [],
  setIntradayConfirmations: (intradayConfirmations) => set({ intradayConfirmations }),
}));
