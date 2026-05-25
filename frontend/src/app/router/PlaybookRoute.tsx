import { useLayoutEffect } from "react";
import { TradingWorkspace } from "../../features/trading-workspace/TradingWorkspace";
import { useWorkspaceStore } from "../../stores/workspaceStore";

export function PlaybookRoute() {
  const setPage = useWorkspaceStore((state) => state.setPage);

  useLayoutEffect(() => {
    setPage("playbook");
  }, [setPage]);

  return <TradingWorkspace />;
}
