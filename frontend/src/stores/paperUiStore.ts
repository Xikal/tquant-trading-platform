import { create } from "zustand";
import type { PixelTraderAnimationState } from "../features/paper/pixelTrader/types";

export type PaperDetailTabKey = "today" | "orders" | "trades" | "pnl" | "strategy" | "risk" | "diagnostic";
export type PaperDetailGroupKey = "records" | "performance" | "automation";

interface PaperUiStore {
  detailTab: PaperDetailTabKey;
  detailGroup: PaperDetailGroupKey;
  orderModalOpen: boolean;
  dismissedConfirmationKey: string;
  selectedPositionSymbol: string;
  recommendedOrdersOpen: boolean;
  recommendedOrdersLoading: boolean;
  recommendedOrdersError: string;
  clockMs: number;
  pixelTraderVisualState: PixelTraderAnimationState;
  setDetailTab: (tab: PaperDetailTabKey) => void;
  setDetailGroup: (group: PaperDetailGroupKey) => void;
  setOrderModalOpen: (open: boolean) => void;
  setDismissedConfirmationKey: (key: string) => void;
  setSelectedPositionSymbol: (symbol: string) => void;
  setRecommendedOrdersOpen: (open: boolean) => void;
  setRecommendedOrdersLoading: (loading: boolean) => void;
  setRecommendedOrdersError: (error: string) => void;
  setClockMs: (clockMs: number) => void;
  setPixelTraderVisualState: (state: PixelTraderAnimationState) => void;
}

export const usePaperUiStore = create<PaperUiStore>((set) => ({
  detailTab: "today",
  detailGroup: "automation",
  orderModalOpen: false,
  dismissedConfirmationKey: "",
  selectedPositionSymbol: "",
  recommendedOrdersOpen: false,
  recommendedOrdersLoading: false,
  recommendedOrdersError: "",
  clockMs: Date.now(),
  pixelTraderVisualState: "idle",
  setDetailTab: (detailTab) => set({ detailTab }),
  setDetailGroup: (detailGroup) => set({ detailGroup }),
  setOrderModalOpen: (orderModalOpen) => set({ orderModalOpen }),
  setDismissedConfirmationKey: (dismissedConfirmationKey) => set({ dismissedConfirmationKey }),
  setSelectedPositionSymbol: (selectedPositionSymbol) => set({ selectedPositionSymbol }),
  setRecommendedOrdersOpen: (recommendedOrdersOpen) => set({ recommendedOrdersOpen }),
  setRecommendedOrdersLoading: (recommendedOrdersLoading) => set({ recommendedOrdersLoading }),
  setRecommendedOrdersError: (recommendedOrdersError) => set({ recommendedOrdersError }),
  setClockMs: (clockMs) => set({ clockMs }),
  setPixelTraderVisualState: (pixelTraderVisualState) => set({ pixelTraderVisualState }),
}));
