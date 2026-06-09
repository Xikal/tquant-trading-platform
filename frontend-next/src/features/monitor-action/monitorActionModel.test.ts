import { createRoot } from "solid-js";
import { describe, expect, it } from "vitest";
import { priorityEmptyText } from "./MonitorActionPage";
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

  it("does not fabricate market firepower or AI insight when backend fields are absent", () => {
    createRoot((dispose) => {
      const model = createMonitorActionModel(
        {
          monitor_snapshot: {
            priority_board: {
              items: [{ symbol: "000001", name: "平安银行", signal_state: "观察确认" }],
            },
          },
        },
        () => undefined,
      );

      expect(model.metrics.find((item) => item.label === "市场火力")?.value).toBe("--");
      expect(model.aiInsight).toBe("--");
      dispose();
    });
  });

  it("uses market pulse for action market status when priority board is still a refresh placeholder", () => {
    createRoot((dispose) => {
      const model = createMonitorActionModel(
        {
          market_pulse: {
            data_quality: "fresh",
            data_quality_text: "盘中 pulse 数据完整且新鲜",
            pulse_level: "repair",
            pulse_text: "市场修复但仍需确认：结构温和修复。",
            suggested_action: "下午动作以确认承接为主，小仓试错。",
          },
          monitor_snapshot: {
            priority_board: {
              market_state_text: "数据刷新中",
              market_state_category_text: "等待数据",
              data_quality_text: "后台刷新中",
              items: [],
            },
          },
        },
        () => undefined,
      );

      expect(model.marketStatus.badge).toBe("修复");
      expect(model.marketStatus.primary).toContain("市场修复");
      expect(model.marketStatus.secondary).toContain("小仓试错");
      expect(model.marketStatus.dataState).toBe("盘中 pulse 数据完整且新鲜");
      dispose();
    });
  });

  it("extracts action card details from backend priority board fields", () => {
    createRoot((dispose) => {
      const model = createMonitorActionModel(
        {
          monitor_snapshot: {
            priority_board: {
              items: [
                {
                  symbol: "000001",
                  name: "平安银行",
                  strategy_title: "首板回调",
                  latest_price: 12.3,
                  confirmed_trade_date: "2026-06-05",
                  entry_zone_low: 11.8,
                  entry_zone_high: 12.1,
                  stop_loss: 11.2,
                  buy_signal_text: "接近买点，等待承接确认",
                  suggested_position_text: "2成试错",
                  action_summary: "缩量回踩到支撑位",
                  trigger_condition: "放量站回 12.1",
                  invalid_condition: "跌破 11.2",
                },
              ],
            },
          },
        },
        () => undefined,
      );

      const item = model.priorityItems[0];
      expect(item.price).toBe("12.3");
      expect(item.entryRange).toBe("11.8-12.1");
      expect(item.signal).toBe("接近买点，等待承接确认");
      expect(item.stopLoss).toBe("11.2");
      expect(item.position).toBe("2成试错");
      expect(item.recommendDate).toBe("2026-06-05");
      expect(item.detailLines).toContain("缩量回踩到支撑位");
      dispose();
    });
  });

  it("explains empty buy lane without hiding existing candidates", () => {
    expect(priorityEmptyText("buy_now", 10)).toContain("当前无确认买入信号");
    expect(priorityEmptyText("buy_now", 10)).toContain("全部候选仍有 10 只");
    expect(priorityEmptyText("all", 0)).toContain("榜单数据刷新中");
  });
});
