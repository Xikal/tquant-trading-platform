import { create } from "zustand";
import type { PixelTraderAnimationState } from "../features/paper/pixelTrader/types";

export type PaperDetailTabKey = "today" | "orders" | "trades" | "pnl" | "strategy" | "risk" | "diagnostic" | "review-history" | "execution-preview";
export type PaperDetailGroupKey = "records" | "performance" | "automation" | "details";
export type PaperMechaUnitId = "purple" | "blue" | "red" | "black" | "grey";
export type PaperMechaVisualState = "idle" | "buy" | "sell" | "profit" | "loss" | "auto" | "paused" | "risk" | "closed";

export interface PaperMechaEffectState {
  key: PaperMechaVisualState;
  label: string;
  syncRate: string;
  caption: string;
  token: string;
}

interface PaperUiStore {
  detailTab: PaperDetailTabKey;
  detailGroup: PaperDetailGroupKey;
  orderModalOpen: boolean;
  dismissedConfirmationKey: string;
  selectedPositionSymbol: string;
  recommendedOrdersOpen: boolean;
  recommendedOrdersLoading: boolean;
  recommendedOrdersError: string;
  exitModelShadowLoading: boolean;
  exitModelShadowError: string;
  clockMs: number;
  selectedMechaUnitId: PaperMechaUnitId;
  activeMechaEffect: PaperMechaEffectState | null;
  pixelTraderVisualState: PixelTraderAnimationState;
  setDetailTab: (tab: PaperDetailTabKey) => void;
  setDetailGroup: (group: PaperDetailGroupKey) => void;
  setOrderModalOpen: (open: boolean) => void;
  setDismissedConfirmationKey: (key: string) => void;
  setSelectedPositionSymbol: (symbol: string) => void;
  setRecommendedOrdersOpen: (open: boolean) => void;
  setRecommendedOrdersLoading: (loading: boolean) => void;
  setRecommendedOrdersError: (error: string) => void;
  setExitModelShadowLoading: (loading: boolean) => void;
  setExitModelShadowError: (error: string) => void;
  setClockMs: (clockMs: number) => void;
  setSelectedMechaUnitId: (unitId: PaperMechaUnitId) => void;
  setActiveMechaEffect: (effect: PaperMechaEffectState | null) => void;
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
  exitModelShadowLoading: false,
  exitModelShadowError: "",
  clockMs: Date.now(),
  selectedMechaUnitId: "purple",
  activeMechaEffect: null,
  pixelTraderVisualState: "idle",
  setDetailTab: (detailTab) => set({ detailTab }),
  setDetailGroup: (detailGroup) => set({ detailGroup }),
  setOrderModalOpen: (orderModalOpen) => set({ orderModalOpen }),
  setDismissedConfirmationKey: (dismissedConfirmationKey) => set({ dismissedConfirmationKey }),
  setSelectedPositionSymbol: (selectedPositionSymbol) => set({ selectedPositionSymbol }),
  setRecommendedOrdersOpen: (recommendedOrdersOpen) => set({ recommendedOrdersOpen }),
  setRecommendedOrdersLoading: (recommendedOrdersLoading) => set({ recommendedOrdersLoading }),
  setRecommendedOrdersError: (recommendedOrdersError) => set({ recommendedOrdersError }),
  setExitModelShadowLoading: (exitModelShadowLoading) => set({ exitModelShadowLoading }),
  setExitModelShadowError: (exitModelShadowError) => set({ exitModelShadowError }),
  setClockMs: (clockMs) => set({ clockMs }),
  setSelectedMechaUnitId: (selectedMechaUnitId) => set({ selectedMechaUnitId }),
  setActiveMechaEffect: (activeMechaEffect) => set({ activeMechaEffect }),
  setPixelTraderVisualState: (pixelTraderVisualState) => set({ pixelTraderVisualState }),
}));
