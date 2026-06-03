import { describe, expect, it, vi } from "vitest";
import { updateTopbarPulse } from "../../state/realtime/topbarClockSignal";
import { useWorkspaceStore } from "../../stores/workspaceStore";

describe("Topbar clock signal", () => {
  it("does not broadcast workspace store subscriptions when pulse updates", () => {
    const subscriber = vi.fn();
    const unsubscribe = useWorkspaceStore.subscribe(subscriber);

    updateTopbarPulse("09:30:00");
    updateTopbarPulse("09:30:01");

    unsubscribe();
    expect(subscriber).not.toHaveBeenCalled();
  });
});
