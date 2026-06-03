import { describe, expect, it, vi } from "vitest";

import { dataQualityApi } from "./dataQuality";
import { apiClient } from "./httpClient";

describe("dataQualityApi", () => {
  it("calls coverage, backfill, repair, runtime fallback and trade gate endpoints", async () => {
    const request = vi.spyOn(apiClient, "request").mockResolvedValue({} as never);

    await dataQualityApi.coverage({ dataset_key: "daily_bars", scope: "all" });
    await dataQualityApi.backfill({ dataset_key: "daily_bars", scope: "all", start_date: "2026-05-01", end_date: "2026-05-29" });
    await dataQualityApi.repair({ dataset_key: "daily_bars", dry_run: false });
    await dataQualityApi.tradeGate();
    await dataQualityApi.runtimeFallback();

    expect(request).toHaveBeenNthCalledWith(1, "/data-quality/coverage?dataset_key=daily_bars&scope=all");
    expect(request).toHaveBeenNthCalledWith(2, "/data-quality/backfill", {
      method: "POST",
      body: JSON.stringify({ dataset_key: "daily_bars", scope: "all", start_date: "2026-05-01", end_date: "2026-05-29" }),
    });
    expect(request).toHaveBeenNthCalledWith(3, "/data-quality/repair", {
      method: "POST",
      body: JSON.stringify({ dataset_key: "daily_bars", dry_run: false }),
    });
    expect(request).toHaveBeenNthCalledWith(4, "/data-quality/trade-gate");
    expect(request).toHaveBeenNthCalledWith(5, "/data-quality/runtime-fallback");
  });
});
