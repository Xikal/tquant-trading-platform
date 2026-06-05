import { afterEach, describe, expect, it, vi } from "vitest";
import { updateTopbarPulse } from "../../state/realtime/topbarClockSignal";
import { useWorkspaceStore } from "../../stores/workspaceStore";
import { topbarRealtimePulseEnabled } from "./Topbar";

describe("Topbar clock signal", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("does not broadcast workspace store subscriptions when pulse updates", () => {
    const subscriber = vi.fn();
    const unsubscribe = useWorkspaceStore.subscribe(subscriber);

    updateTopbarPulse("09:30:00");
    updateTopbarPulse("09:30:01");

    unsubscribe();
    expect(subscriber).not.toHaveBeenCalled();
  });

  it("does not start a one-second signal timer when the realtime island flag is disabled", () => {
    vi.stubEnv("VITE_FRONTEND_REALTIME_SIGNALS_ISLAND_ENABLED", "false");

    expect(topbarRealtimePulseEnabled()).toBe(false);
  });
});
