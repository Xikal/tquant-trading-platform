import { createRoot } from "solid-js";
import { describe, expect, it } from "vitest";
import { createMonitorActionModel, priorityRowsForTable } from "./monitorActionModel";

describe("monitor action priority board model", () => {
  it("renders grouped priority board items when the top-level items array is absent", () => {
    createRoot((dispose) => {
      const model = createMonitorActionModel(
        {
          monitor_snapshot: {
            priority_board: {
              total_candidates: 2,
              immediate_count: 1,
              focus_count: 1,
              family_sections: [
                {
                  family_key: "wash",
                  family_text: "洗盘低吸",
                  items: [
                    {
                      symbol: "000001",
                      name: "平安银行",
                      strategy_title: "N形洗盘低吸",
                      latest_price: 12.3,
                      change_pct: -0.004,
                      priority_score: 88,
                      buy_signal_state: "buy_now",
                      buy_signal_text: "立即处理",
                      simple_bucket: "buy_now",
                      action_summary: "缩量回踩到位",
                    },
                    {
                      symbol: "600000",
                      name: "浦发银行",
                      strategy_title: "N形洗盘低吸",
                      latest_price: 8.72,
                      change_pct: 0.012,
                      priority_score: 83,
                      buy_signal_state: "watch",
                      buy_signal_text: "等待回踩",
                      simple_bucket: "wait_price",
                      action_summary: "接近支撑位",
                    },
                  ],
                },
              ],
            },
          },
        },
        () => undefined,
      );

      expect(priorityRowsForTable(model.priorityItems).map((row) => row.symbol)).toEqual(["000001", "600000"]);
      expect(model.laneOptions[0].label).toBe("全部 2");
      expect(model.laneItems("buy_now").map((item) => item.symbol)).toEqual(["000001"]);
      expect(model.laneItems("observe").map((item) => item.symbol)).toEqual(["600000"]);
      dispose();
    });
  });
});
