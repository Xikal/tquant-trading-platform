import type { ComponentProps } from "react";
import type { WatchlistItem } from "../types";
import { MobileHoldingsSection, MobileHomeSection, MobileLowBuySection } from "./MobileTabSections";
import type { MobileLowBuyCardItem } from "./MobileDesignCards";
import type { MobileTab } from "./mobileTypes";

type HomeProps = ComponentProps<typeof MobileHomeSection>;
type HoldingsProps = ComponentProps<typeof MobileHoldingsSection>;
type LowBuyProps = ComponentProps<typeof MobileLowBuySection>;

export function MobileTabContent({
  activeTab,
  home,
  holdings,
  lowBuy,
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
  };
}) {
  if (activeTab === "home") {
    return <MobileHomeSection {...home} />;
  }
  if (activeTab === "holdings") {
    return <MobileHoldingsSection {...holdings} />;
  }
  return <MobileLowBuySection {...lowBuy} />;
}
