import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../shared/api/client";
import { boardMetrics, loadPlaybookDataset, type PlaybookDataset } from "./playbookModel";

describe("playbook priority board model", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads quote data for symbols carried only in grouped priority board sections", async () => {
    vi.spyOn(apiClient, "lowBuyScreener").mockResolvedValue({ confirmed_candidates: [], watch_candidates: [] });
    vi.spyOn(apiClient, "lowBuyPriorityBoard").mockResolvedValue(groupedPriorityBoard);
    vi.spyOn(apiClient, "lowBuyStrategies").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "strategiesMeta").mockResolvedValue({ strategies: [] });
    const quotes = vi.spyOn(apiClient, "lowBuyQuotes").mockResolvedValue({ updated_at: "09:45:00", quotes: [] });

    await loadPlaybookDataset("first_board");

    expect(quotes).toHaveBeenCalledWith(["000001", "600000"], "first_board", expect.any(Object));
  });

  it("counts grouped priority board candidates when top-level items are absent", () => {
    const data = { priorityBoard: groupedPriorityBoard } as PlaybookDataset;

    expect(boardMetrics(data).find((item) => item.label === "总候选")?.value).toBe("2");
  });
});

const groupedPriorityBoard = {
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
          latest_price: 12.3,
          change_pct: -0.004,
          priority_score: 88,
          buy_signal_text: "立即处理",
          simple_bucket: "buy_now",
          action_summary: "缩量回踩到位",
        },
        {
          symbol: "600000",
          name: "浦发银行",
          latest_price: 8.72,
          change_pct: 0.012,
          priority_score: 83,
          buy_signal_text: "等待回踩",
          simple_bucket: "wait_price",
          action_summary: "接近支撑位",
        },
      ],
    },
  ],
};
