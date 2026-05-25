import { useLayoutEffect } from "react";
import { TradingWorkspace } from "../../features/trading-workspace/TradingWorkspace";
import { useWorkspaceStore } from "../../stores/workspaceStore";

export function AnalysisRoute() {
  const setPage = useWorkspaceStore((state) => state.setPage);

  useLayoutEffect(() => {
    setPage("analysis");
  }, [setPage]);

  return <TradingWorkspace />;
}
