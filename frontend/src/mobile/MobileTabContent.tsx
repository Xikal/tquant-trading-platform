import type { ComponentProps } from "react";
import type { BacktestRunSummary } from "../api/backtests";
import type { WatchlistItem } from "../types";
import { PaperTradingPanel } from "./PaperTradingPanel";
import { MobileHoldingsSection, MobileHomeSection, MobileLowBuySection } from "./MobileTabSections";
import type { MobileLowBuyCardItem } from "./MobileDesignCards";
import type { MobileTab } from "./mobileTypes";

type HomeProps = ComponentProps<typeof MobileHomeSection>;
type HoldingsProps = ComponentProps<typeof MobileHoldingsSection>;
type LowBuyProps = ComponentProps<typeof MobileLowBuySection>;
type PaperProps = ComponentProps<typeof PaperTradingPanel>;

export function MobileTabContent({
  activeTab,
  home,
  holdings,
  lowBuy,
  paper,
}: {
  activeTab: MobileTab;
  home: Omit<HomeProps, "onSwitchToLowBuy"> & { onSwitchToLowBuy: () => void };
  holdings: Omit<HoldingsProps, "onCreateHolding" | "onSearchHolding" | "onEditHolding" | "onRemoveHolding"> & {
    onCreateHolding: () => void;
    onSearchHolding: (symbol: string) => void | Promise<void>;
    onEditHolding: (item: WatchlistItem) => void;
    onRemoveHolding: (item: WatchlistItem) => void | Promise<void>;
  };
  lowBuy: Omit<LowBuyProps, "onOpenAi" | "onBought"> & {
    onOpenAi: () => void;
    onBought: (item: MobileLowBuyCardItem) => void;
    recentBacktests?: BacktestRunSummary[];
  };
  paper: PaperProps;
}) {
  if (activeTab === "home") {
    return <MobileHomeSection {...home} />;
  }
  if (activeTab === "holdings") {
    return <MobileHoldingsSection {...holdings} />;
  }
  if (activeTab === "low_buy") {
    return <MobileLowBuySection {...lowBuy} />;
  }
  return <PaperTradingPanel {...paper} />;
}
