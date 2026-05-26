import { create } from "zustand";
import type { StrategyMeta } from "../api/strategies";
import type { LowBuyPriorityBoardItem } from "../types";
import type { PixelTraderAnimationState } from "../features/paper/pixelTrader/types";

export type PaperDetailTabKey = "today" | "orders" | "trades" | "pnl" | "strategy" | "risk" | "diagnostic";

interface PaperUiStore {
  detailTab: PaperDetailTabKey;
  orderModalOpen: boolean;
  dismissedConfirmationKey: string;
  selectedPositionSymbol: string;
  orderStrategies: StrategyMeta[];
  recommendedOrders: LowBuyPriorityBoardItem[];
  recommendedOrdersOpen: boolean;
  recommendedOrdersLoading: boolean;
  recommendedOrdersError: string;
  clockMs: number;
  pixelTraderVisualState: PixelTraderAnimationState;
  setDetailTab: (tab: PaperDetailTabKey) => void;
  setOrderModalOpen: (open: boolean) => void;
  setDismissedConfirmationKey: (key: string) => void;
  setSelectedPositionSymbol: (symbol: string) => void;
  setOrderStrategies: (strategies: StrategyMeta[]) => void;
  setRecommendedOrders: (orders: LowBuyPriorityBoardItem[]) => void;
  setRecommendedOrdersOpen: (open: boolean) => void;
  setRecommendedOrdersLoading: (loading: boolean) => void;
  setRecommendedOrdersError: (error: string) => void;
  setClockMs: (clockMs: number) => void;
  setPixelTraderVisualState: (state: PixelTraderAnimationState) => void;
}

export const usePaperUiStore = create<PaperUiStore>((set) => ({
  detailTab: "today",
  orderModalOpen: false,
  dismissedConfirmationKey: "",
  selectedPositionSymbol: "",
  orderStrategies: [],
  recommendedOrders: [],
  recommendedOrdersOpen: false,
  recommendedOrdersLoading: false,
  recommendedOrdersError: "",
  clockMs: Date.now(),
  pixelTraderVisualState: "idle",
  setDetailTab: (detailTab) => set({ detailTab }),
  setOrderModalOpen: (orderModalOpen) => set({ orderModalOpen }),
  setDismissedConfirmationKey: (dismissedConfirmationKey) => set({ dismissedConfirmationKey }),
  setSelectedPositionSymbol: (selectedPositionSymbol) => set({ selectedPositionSymbol }),
  setOrderStrategies: (orderStrategies) => set({ orderStrategies }),
  setRecommendedOrders: (recommendedOrders) => set({ recommendedOrders }),
  setRecommendedOrdersOpen: (recommendedOrdersOpen) => set({ recommendedOrdersOpen }),
  setRecommendedOrdersLoading: (recommendedOrdersLoading) => set({ recommendedOrdersLoading }),
  setRecommendedOrdersError: (recommendedOrdersError) => set({ recommendedOrdersError }),
  setClockMs: (clockMs) => set({ clockMs }),
  setPixelTraderVisualState: (pixelTraderVisualState) => set({ pixelTraderVisualState }),
}));
