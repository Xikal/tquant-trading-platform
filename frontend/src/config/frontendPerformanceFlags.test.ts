import { describe, expect, it } from "vitest";
import { frontendPerformanceFlagDefaults, frontendPerformanceFlagEnabled } from "./frontendPerformanceFlags";

describe("frontendPerformanceFlags", () => {
  it("keeps worker and signals paths enabled by default with rollback overrides", () => {
    expect(frontendPerformanceFlagDefaults()).toMatchObject({
      frontend_worker_compute_enabled: true,
      frontend_realtime_signals_island_enabled: true,
      frontend_canvas_chart_island_enabled: true,
      frontend_wasm_compute_enabled: false,
      frontend_solid_island_enabled: false,
    });

    expect(frontendPerformanceFlagEnabled("frontend_worker_compute_enabled")).toBe(true);
    expect(frontendPerformanceFlagEnabled("frontend_worker_compute_enabled", { frontend_worker_compute_enabled: false })).toBe(false);
  });
});
