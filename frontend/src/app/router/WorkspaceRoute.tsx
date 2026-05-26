import { useEffect, useLayoutEffect } from "react";
import { TradingWorkspace } from "../../features/trading-workspace/TradingWorkspace";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import type { Page } from "../../features/workspace-shared/workspaceTypes";

interface WorkspaceRouteProps {
  page: Page;
}

export function WorkspaceRoute({ page }: WorkspaceRouteProps) {
  const currentPage = useWorkspaceStore((state) => state.page);
  const setPage = useWorkspaceStore((state) => state.setPage);

  useLayoutEffect(() => {
    setPage(page);
  }, [page, setPage]);

  useEffect(() => {
    if (import.meta.env.DEV && currentPage !== page) {
      console.warn(`WorkspaceRoute page mismatch: url expects ${page}, store has ${currentPage}.`);
    }
  }, [currentPage, page]);

  return <TradingWorkspace />;
}
