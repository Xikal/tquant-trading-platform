import { describe, expect, it } from "vitest";
import { buildDriftRows } from "./strategyTrackingModel";

describe("strategy tracking display model", () => {
  it("does not fabricate drift metrics when backend payload has no drift fields", () => {
    const rows = buildDriftRows({ avg_current_return_pct: 0.18 });

    expect(rows).toEqual([
      { label: "均化滑点损失", value: "--", status: "暂无数据", tone: "slate", hasData: false },
      { label: "实盘信号响应延时", value: "--", status: "暂无数据", tone: "slate", hasData: false },
      { label: "时序排序一致性", value: "--", status: "暂无数据", tone: "slate", hasData: false },
    ]);
    expect(rows.map((row) => `${row.value} ${row.status}`).join(" ")).not.toMatch(/-0\.12|0\.85|可接受|高速级|无异动/);
  });

  it("formats real drift fields and derives statuses from data", () => {
    const rows = buildDriftRows({
      slippage_pct: 0.001,
      latency_ms: 420,
      order_consistency: 0.991,
    });

    expect(rows).toEqual([
      { label: "均化滑点损失", value: "0.1%", status: "可观察", tone: "green", hasData: true },
      { label: "实盘信号响应延时", value: "420 ms", status: "响应正常", tone: "green", hasData: true },
      { label: "时序排序一致性", value: "99.1%", status: "一致性稳定", tone: "green", hasData: true },
    ]);
  });
});
