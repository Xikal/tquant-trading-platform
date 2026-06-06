import { describe, expect, it } from "vitest";
import { createMonitorRefreshState } from "./monitorRefreshState";

describe("createMonitorRefreshState", () => {
  it("queues duplicate refreshes while a request is in flight", () => {
    const state = createMonitorRefreshState();

    expect(state.start({ includeRuntime: false })).toEqual({ status: "started", includeRuntime: false });
    expect(state.start({ includeRuntime: true })).toEqual({ status: "queued", includeRuntime: true });
  });

  it("merges includeRuntime for queued refreshes", () => {
    const state = createMonitorRefreshState();
    state.start({ includeRuntime: false });
    state.start({ includeRuntime: true });

    expect(state.finish()).toEqual({ next: { includeRuntime: true } });
  });

  it("clears the queue after the queued refresh is consumed", () => {
    const state = createMonitorRefreshState();
    state.start({ includeRuntime: false });
    state.start({ includeRuntime: true });
    state.finish();

    expect(state.finish()).toEqual({ next: null });
  });

  it("resets in-flight and queued state", () => {
    const state = createMonitorRefreshState();
    state.start({ includeRuntime: false });
    state.start({ includeRuntime: true });
    state.reset();

    expect(state.start({ includeRuntime: false })).toEqual({ status: "started", includeRuntime: false });
    expect(state.finish()).toEqual({ next: null });
  });
});
