import { describe, expect, it } from "vitest";
import { buildDataFreshnessView } from "./dataFreshnessViewModel";

describe("buildDataFreshnessView", () => {
  it("marks stale recommendation snapshots as review-only", () => {
    expect(buildDataFreshnessView({
      stale: true,
      staleReason: "落后 2 个交易日",
      latestTradeDate: "2026-06-03",
      expectedTradeDate: "2026-06-05",
    })).toEqual({
      status: "stale",
      tone: "warn",
      title: "数据已过期，仅供复盘",
      detail: "落后 2 个交易日",
      tradeDateText: "2026-06-03 / 目标 2026-06-05",
      reviewOnly: true,
    });
  });

  it("keeps successful same-trade-date data usable", () => {
    expect(buildDataFreshnessView({
      status: "success",
      latestTradeDate: "2026-06-05",
      expectedTradeDate: "2026-06-05",
    })).toMatchObject({
      status: "ok",
      tone: "up",
      reviewOnly: false,
    });
  });

  it("uses waiting copy when data is not stale but not published yet", () => {
    const view = buildDataFreshnessView({
      status: "waiting",
      latestTradeDate: "2026-06-05",
      expectedTradeDate: "2026-06-05",
    });

    expect(view.status).toBe("waiting");
    expect(view.title).toBe("等待最新数据发布");
  });

  it("uses degraded copy without forcing review-only mode", () => {
    const view = buildDataFreshnessView({
      dataQuality: "partial",
      latestTradeDate: "2026-06-05",
      expectedTradeDate: "2026-06-05",
    });

    expect(view.status).toBe("degraded");
    expect(view.tone).toBe("warn");
    expect(view.reviewOnly).toBe(false);
  });

  it("marks missing strategy snapshots as waiting work", () => {
    expect(buildDataFreshnessView({
      status: "success",
      latestTradeDate: "2026-06-05",
      expectedTradeDate: "2026-06-05",
      missingCount: 2,
    })).toMatchObject({
      status: "waiting",
      title: "策略快照待补齐",
      tone: "warn",
    });
  });
});
