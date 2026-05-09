import { useEffect, type RefObject } from "react";
import type { AuthUser } from "../../types";
import { MONITOR_REFRESH_INTERVAL_MS } from "./workspaceConstants";
import type { Page } from "./workspaceTypes";

const PAPER_TRADING_REFRESH_INTERVAL_MS = 30_000;
const PAPER_IDLE_REFRESH_INTERVAL_MS = 60 * 60 * 1000;

interface UseWorkspaceAutoRefreshParams {
  currentUser: AuthUser | null;
  page: Page;
  fetchMonitorData: (includeRuntime: boolean) => Promise<void>;
  paperTradingTime?: boolean;
  refreshPaperLiveSnapshotRef: RefObject<(options?: { refreshPrices?: boolean }) => Promise<void>>;
}

export function useWorkspaceAutoRefresh({
  currentUser,
  page,
  fetchMonitorData,
  paperTradingTime,
  refreshPaperLiveSnapshotRef,
}: UseWorkspaceAutoRefreshParams) {
  useEffect(() => {
    if (!currentUser || page !== "monitor") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void fetchMonitorData(false);
    }, MONITOR_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [currentUser, fetchMonitorData, page]);

  useEffect(() => {
    if (!currentUser || page !== "paper" || !currentUser.can_paper_trade) {
      return undefined;
    }
    let inFlight = false;
    const isTradingTime = Boolean(paperTradingTime);
    const intervalMs = isTradingTime ? PAPER_TRADING_REFRESH_INTERVAL_MS : PAPER_IDLE_REFRESH_INTERVAL_MS;
    const runRefresh = async () => {
      if (document.visibilityState !== "visible" || inFlight) {
        return;
      }
      inFlight = true;
      try {
        await refreshPaperLiveSnapshotRef.current?.({ refreshPrices: isTradingTime });
      } finally {
        inFlight = false;
      }
    };
    const timer = window.setInterval(() => {
      void runRefresh();
    }, intervalMs);
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        void runRefresh();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [currentUser, page, paperTradingTime, refreshPaperLiveSnapshotRef, currentUser?.can_paper_trade]);
}
