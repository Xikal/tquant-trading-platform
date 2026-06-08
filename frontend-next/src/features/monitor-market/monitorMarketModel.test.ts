import { describe, expect, it } from "vitest";
import { createMonitorMarketModel } from "./monitorMarketModel";
import { buildView } from "./MonitorMarketPage";

describe("monitor market model", () => {
  it("maps live market BFF fields without falling back to empty placeholders", () => {
    const model = createMonitorMarketModel({
      generated_at: "2026-06-08T18:50:06+08:00",
      stale: false,
      monitor_snapshot: {
        updated_at: "2026-06-08 18:49:30",
        priority_board: {
          refresh_count: 3,
          market_state_text: "下跌退潮",
          items: [{ symbol: "000001", lane: "observe", production_score: 82 }],
        },
      },
      market_breadth: {
        updated_at: "2026-06-08 18:50:06",
        data_quality: "fresh",
        state_text: "下跌退潮",
        stock_up_ratio: 0.1276,
        stock_median_change: -3.1,
        limit_up_count: 57,
        limit_down_count: 35,
        hot_industries: ["通用设备", "通信设备", "半导体"],
      },
      market_pulse: {
        updated_at: "2026-06-08 18:49:21",
        strength: 0.32,
      },
      sector_relative_strength: {
        updated_at: "2026-06-08 18:50:08",
        items: [
          {
            sector_name: "通用设备",
            symbol: "300145",
            name: "南方泵业",
            change_pct: 13.06,
          },
        ],
      },
      review_status: {
        status: "midday_ready",
        status_text: "今日市场午盘复盘已生成，等待收盘复盘",
      },
      review_reports: [
        {
          report_slot: "midday",
          overall_summary: "午后控制追高，等待右侧确认。",
          suggestion: "午后控制追高",
        },
      ],
      partial_errors: [],
    });

    const view = buildView(model);

    expect(view.syncStatus).toBe("BFF: ACTIVE");
    expect(view.dataUpdatedAt).toBe("2026-06-08 18:50:06");
    expect(view.medianChange).toBe("-3.10%");
    expect(view.hotSectors).toEqual(["通用设备", "通信设备", "半导体"]);
    expect(view.leaders[0]).toEqual({ sector: "通用设备", name: "南方泵业", change: "+13.1%" });
    expect(view.middayReview).toBe("午后控制追高，等待右侧确认。");
    expect(view.closeReview).toBe("收盘复盘暂未生成。等待收盘后生成。");
    expect(view.pulseBars.length).toBeGreaterThan(0);
  });

  it("exposes stale and partial BFF states", () => {
    const stale = buildView(createMonitorMarketModel({ stale: true }));
    expect(stale.syncStatus).toBe("BFF: STALE");

    const partial = buildView(createMonitorMarketModel({ partial_errors: [{ source: "market_breadth" }] }));
    expect(partial.syncStatus).toBe("BFF: PARTIAL 1");
  });
});
