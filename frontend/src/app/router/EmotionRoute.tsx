import { useLayoutEffect } from "react";
import { TradingWorkspace } from "../../features/trading-workspace/TradingWorkspace";
import { useWorkspaceStore } from "../../stores/workspaceStore";

export function EmotionRoute() {
  const setPage = useWorkspaceStore((state) => state.setPage);

  useLayoutEffect(() => {
    setPage("emotion");
  }, [setPage]);

  return <TradingWorkspace />;
}
