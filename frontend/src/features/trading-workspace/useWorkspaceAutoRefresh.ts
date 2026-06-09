import { useEffect } from "react";
import type { AuthUser } from "../../types";
import { MONITOR_REFRESH_INTERVAL_MS } from "../workspace-shared/workspaceConstants";
import type { Page } from "../workspace-shared/workspaceTypes";
import { isMonitorDataPage } from "./workspaceRoutes";

interface UseWorkspaceAutoRefreshParams {
  currentUser: AuthUser | null;
  page: Page;
  fetchMonitorData: (includeRuntime: boolean) => Promise<unknown>;
}

export function useWorkspaceAutoRefresh({
  currentUser,
  page,
  fetchMonitorData,
}: UseWorkspaceAutoRefreshParams) {
  useEffect(() => {
    if (!currentUser || !isMonitorDataPage(page)) {
      return undefined;
    }
    let inFlight = false;
    const runRefresh = async () => {
      if (document.visibilityState !== "visible" || inFlight) {
        return;
      }
      inFlight = true;
      try {
        await fetchMonitorData(false);
      } finally {
        inFlight = false;
      }
    };
    const timer = window.setInterval(() => {
      void runRefresh();
    }, MONITOR_REFRESH_INTERVAL_MS);
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
  }, [currentUser, fetchMonitorData, page]);

}
