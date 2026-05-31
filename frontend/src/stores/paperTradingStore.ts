import { create } from "zustand";
import type { PaperOrderDraft } from "../features/workspace-shared/workspaceTypes";

export const DEFAULT_PAPER_ORDER_DRAFT: PaperOrderDraft = {
  symbol: "",
  name: "",
  side: "buy",
  order_type: "market",
  quantity: "100",
  price: "",
  current_price: "",
  strategy_key: "",
  reason: "",
  require_intraday_confirmation: false,
};

interface PaperTradingStore {
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft | ((current: PaperOrderDraft) => PaperOrderDraft)) => void;
  clearPaperData: () => void;
}

export const usePaperTradingStore = create<PaperTradingStore>((set) => ({
  draft: DEFAULT_PAPER_ORDER_DRAFT,
  setDraft: (draft) => set((state) => ({
    draft: typeof draft === "function" ? draft(state.draft) : draft,
  })),
  clearPaperData: () => undefined,
}));
