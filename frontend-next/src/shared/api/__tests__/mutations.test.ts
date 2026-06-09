import { describe, expect, it, vi } from "vitest";
import { createMutationClient, type Requester } from "../mutations";

describe("frontend-next guarded mutations", () => {
  it("keeps ready mutations in shadow mode by default", async () => {
    const requester = vi.fn();
    const client = createMutationClient({ writeEnabled: false, requester });

    const result = await client.updateFeatureFlag("frontend_solid_island_enabled", {
      key: "frontend_solid_island_enabled",
      enabled: true,
    });

    expect(result.mode).toBe("shadow");
    expect(result.operation).toBe("featureFlagUpdate");
    expect(result.contractStatus).toBe("ready");
    expect(result.safeWriteContract?.id).toBe("FNX-SW-FEATURE-FLAG");
    expect(result.endpoint).toBe("/api/settings/feature-flags/frontend_solid_island_enabled");
    expect(requester).not.toHaveBeenCalled();
  });

  it("sends typed payloads only when the write flag is explicitly enabled", async () => {
    const requester = vi.fn(async () => ({ id: 42 })) as unknown as Requester;
    const client = createMutationClient({ writeEnabled: true, writeMode: "live", isAdmin: true, requester });

    const result = await client.updateFeatureFlag("frontend_solid_island_enabled", {
      key: "frontend_solid_island_enabled",
      enabled: true,
    });

    expect(result.mode).toBe("live");
    expect(result.operation).toBe("featureFlagUpdate");
    expect(result.invalidates).toContain("featureFlags");
    expect(result.clientRequestId).toEqual(expect.stringMatching(/^fnx-featureFlagUpdate-/));
    expect(result.message).toContain("FNX-SW-FEATURE-FLAG");
    expect(requester).toHaveBeenCalledWith(
      "/api/settings/feature-flags/frontend_solid_island_enabled",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ key: "frontend_solid_island_enabled", enabled: true }),
        headers: expect.objectContaining({
          "X-Frontend-Next-Client-Request-Id": result.clientRequestId,
          "X-Frontend-Next-Contract-Id": "FNX-SW-FEATURE-FLAG",
          "X-Frontend-Next-Contract-State": "defined_production_ready",
          "X-Frontend-Next-Operation": "featureFlagUpdate",
          "X-Frontend-Next-Source": "frontend-next",
          "X-Frontend-Next-Write-Mode": "live",
        }),
      }),
    );
  });

  it("keeps writes in shadow when write mode remains shadow", async () => {
    const requester = vi.fn(async () => ({ id: 42 })) as unknown as Requester;
    const client = createMutationClient({ writeEnabled: true, writeMode: "shadow", isAdmin: true, requester });

    const result = await client.upsertWatchlistShadow({ symbol: "600000", reason: "shadow mode" });

    expect(result.mode).toBe("shadow");
    expect(result.message).toContain("write mode shadow");
    expect(result.clientRequestId).toBeUndefined();
    expect(requester).not.toHaveBeenCalled();
  });

  it("does not expose backtest write adapters after the backtest page is removed", () => {
    const client = createMutationClient();

    expect("createBacktestRun" in client).toBe(false);
    expect("cancelBacktestRun" in client).toBe(false);
  });

  it("blocks admin operations without explicit admin permission", async () => {
    const requester = vi.fn(async () => ({ id: 42 })) as unknown as Requester;
    const client = createMutationClient({ writeEnabled: true, writeMode: "live", isAdmin: false, requester });

    const result = await client.updateFeatureFlag("frontend_solid_island_enabled", {
      key: "frontend_solid_island_enabled",
      enabled: true,
    });

    expect(result.mode).toBe("shadow");
    expect(result.message).toContain("admin permission");
    expect(result.clientRequestId).toBeUndefined();
    expect(requester).not.toHaveBeenCalled();
  });

  it("keeps strategy/data writes shadow by default while pointing at real guarded endpoints", async () => {
    const requester = vi.fn();
    const client = createMutationClient({ writeEnabled: false, requester });

    const review = await client.recordStrategyReviewShadow({ strategy: "n_pattern_long_wash" });
    const dataJob = await client.submitDataJobShadow({ source: "akshare" });

    expect(review.endpoint).toBe("/api/strategy-tracking/review-records");
    expect(dataJob.endpoint).toBe("/api/runtime-tasks");
    expect(review.contractStatus).toBe("ready");
    expect(dataJob.contractStatus).toBe("ready");
    expect(review.safeWriteContract?.id).toBe("FNX-SW-STRATEGY-REVIEW");
    expect(dataJob.safeWriteContract?.id).toBe("FNX-SW-DATA-TASK");
    expect(review.message).toContain("write flag is disabled");
    expect(requester).not.toHaveBeenCalled();
  });

  it("blocks admin data writes without explicit admin permission", async () => {
    const requester = vi.fn();
    const client = createMutationClient({ writeEnabled: true, writeMode: "live", isAdmin: false, requester });

    const result = await client.submitDataRepairShadow({ symbol: "000001" });

    expect(result.mode).toBe("shadow");
    expect(result.endpoint).toBe("/api/data-quality/repair");
    expect(result.contractStatus).toBe("ready");
    expect(result.message).toContain("admin permission");
    expect(result.safeWriteContract).toEqual(
      expect.objectContaining({
        id: "FNX-SW-DATA-REPAIR",
        requiredMode: "live",
      }),
    );
    expect(requester).not.toHaveBeenCalled();
  });

  it("sends ready settings section writes only in live mode with explicit admin permission", async () => {
    const requester = vi.fn();
    const client = createMutationClient({ writeEnabled: true, writeMode: "live", isAdmin: true, requester });

    const risk = await client.updateSettings({ risk_max_single_loss_pct: 1 });
    const sectors = await client.updateSectorExclusions({ excluded_sectors: ["房地产"] });
    const factors = await client.updateFactorWeights({ weights: { volume_price: 0.4 } });

    expect(risk.operation).toBe("settingsUpdate");
    expect(sectors.operation).toBe("sectorExclusionsUpdate");
    expect(factors.operation).toBe("factorWeightsUpdate");
    expect([risk.contractStatus, sectors.contractStatus, factors.contractStatus]).toEqual(["ready", "ready", "ready"]);
    expect([risk.mode, sectors.mode, factors.mode]).toEqual(["live", "live", "live"]);
    expect([risk.safeWriteContract?.id, sectors.safeWriteContract?.id, factors.safeWriteContract?.id]).toEqual([
      "FNX-SW-SETTINGS-SECTION",
      "FNX-SW-SETTINGS-SECTION",
      "FNX-SW-SETTINGS-SECTION",
    ]);
    expect(requester).toHaveBeenCalledTimes(3);
  });

  it("sends newly-ready review and data writes only in live mode with permission", async () => {
    const requester = vi.fn(async () => ({ id: 42 })) as unknown as Requester;
    const client = createMutationClient({ writeEnabled: true, writeMode: "live", isAdmin: true, requester });

    const review = await client.recordStrategyReviewShadow({ symbol: "000001", reason: "cutover readiness" });
    const backfill = await client.submitDataBackfillShadow({ dry_run: true });

    expect(review.mode).toBe("live");
    expect(review.contractStatus).toBe("ready");
    expect(review.clientRequestId).toEqual(expect.stringMatching(/^fnx-strategyReviewRecord-/));
    expect(backfill.mode).toBe("live");
    expect(backfill.contractStatus).toBe("ready");
    expect(backfill.clientRequestId).toEqual(expect.stringMatching(/^fnx-dataQualityBackfill-/));
    expect(requester).toHaveBeenCalledTimes(2);
  });
});
