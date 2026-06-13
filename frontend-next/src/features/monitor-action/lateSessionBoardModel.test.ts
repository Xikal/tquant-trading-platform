import { describe, expect, it } from "vitest";
import {
  createLateSessionBoardModel,
  lateSessionSlotLabel,
  lateSessionStateLabel,
} from "./lateSessionBoardModel";

describe("late session board model", () => {
  it("maps late_confirmed items without changing order", () => {
    const model = createLateSessionBoardModel({
      snapshot_slot: "final_1457",
      status: "ok",
      generated_at: "2026-06-13T14:57:00",
      items: [
        { symbol: "000002", name: "万科A", late_session_state: "late_watch", late_session_score: 61, strategy_key: "volume_shrink" },
        { symbol: "000001", name: "平安银行", late_session_state: "late_confirmed", late_session_score: 82, strategy_key: "first_board" },
      ],
    });

    expect(model.items.map((item) => item.symbol)).toEqual(["000002", "000001"]);
    expect(model.items[1].stateLabel).toBe("尾盘确认");
    expect(model.confirmedCount).toBe(1);
  });

  it("maps partial_data and refresh_queued to visible degraded state", () => {
    const model = createLateSessionBoardModel({
      status: "partial_data",
      snapshot_slot: "preview_1450",
      degradation_reason: "refresh_queued",
      data_quality_tags: ["minute_data_missing"],
      items: [],
    });

    expect(model.isDegraded).toBe(true);
    expect(model.statusText).toContain("部分数据");
    expect(model.degradationText).toContain("后台刷新中");
    expect(model.emptyText).toContain("尾盘榜暂无确认项");
  });

  it("does not emit banned trading-copy text", () => {
    const model = createLateSessionBoardModel({
      status: "ok",
      snapshot_slot: "latest",
      items: [{ symbol: "000001", late_session_state: "late_confirmed", late_session_reason: "尾盘承接正常" }],
    });
    const banned = ["必涨", "建议买入", "立即买入"];
    const text = JSON.stringify(model);

    expect(banned.some((word) => text.includes(word))).toBe(false);
  });

  it("supports slot labels for preview_1450 snapshot_1455 final_1457", () => {
    expect(lateSessionSlotLabel("preview_1450")).toBe("14:50 预警");
    expect(lateSessionSlotLabel("snapshot_1455")).toBe("14:55 快照");
    expect(lateSessionSlotLabel("final_1457")).toBe("14:57 终版");
    expect(lateSessionStateLabel("late_rejected")).toBe("不满足尾盘确认");
  });
});
