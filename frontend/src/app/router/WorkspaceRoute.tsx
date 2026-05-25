import { useLayoutEffect } from "react";
import { TradingWorkspace } from "../../features/trading-workspace/TradingWorkspace";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import type { Page } from "../../features/workspace-shared/workspaceTypes";

interface WorkspaceRouteProps {
  page: Page;
}

export function WorkspaceRoute({ page }: WorkspaceRouteProps) {
  const setPage = useWorkspaceStore((state) => state.setPage);

  useLayoutEffect(() => {
    setPage(page);
  }, [page, setPage]);

  return <TradingWorkspace />;
}
