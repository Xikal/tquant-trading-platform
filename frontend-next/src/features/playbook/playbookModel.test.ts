import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../shared/api/client";
import { candidateFamilies, boardMetrics, loadPlaybookDataset, type PlaybookDataset } from "./playbookModel";

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

  it("loads quote data for the selected strategy screener before the global priority board", async () => {
    vi.spyOn(apiClient, "lowBuyScreener").mockResolvedValue({
      strategy_key: "first_board",
      watch_candidates: [
        { symbol: "603319", name: "美湖股份", strategy_key: "first_board", simple_bucket: "watch" },
        { symbol: "601208", name: "东材科技", strategy_key: "first_board", simple_bucket: "watch" },
      ],
    });
    vi.spyOn(apiClient, "lowBuyPriorityBoard").mockResolvedValue(groupedPriorityBoard);
    vi.spyOn(apiClient, "lowBuyStrategies").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "strategiesMeta").mockResolvedValue({ strategies: [] });
    const quotes = vi.spyOn(apiClient, "lowBuyQuotes").mockResolvedValue({ updated_at: "09:45:00", quotes: [] });

    await loadPlaybookDataset("first_board");

    expect(quotes).toHaveBeenCalledWith(["603319", "601208"], "first_board", expect.any(Object));
  });

  it("shows candidates from the selected strategy screener rather than the global priority board", () => {
    const data = {
      screener: {
        strategy_key: "first_board",
        watch_candidates: [
          { symbol: "603319", name: "美湖股份", strategy_key: "first_board", simple_bucket: "watch" },
          { symbol: "601208", name: "东材科技", strategy_key: "first_board", simple_bucket: "watch" },
        ],
      },
      priorityBoard: groupedPriorityBoard,
    } as PlaybookDataset;

    const symbols = candidateFamilies(data).flatMap((family) => family.items.map((item) => item.symbol));

    expect(symbols).toEqual(["603319", "601208"]);
  });

  it("uses the formal screener candidates field before falling back to the global board", () => {
    const data = {
      screener: {
        strategy_key: "volume_shrink",
        latest_trade_date: "2026-06-05",
        confirmed_candidates: [],
        candidates: [
          { symbol: "300750", name: "宁德时代", strategy_key: "volume_shrink", simple_bucket: "wait_price" },
        ],
      },
      priorityBoard: groupedPriorityBoard,
    } as PlaybookDataset;

    const symbols = candidateFamilies(data).flatMap((family) => family.items.map((item) => item.symbol));

    expect(symbols).toEqual(["300750"]);
  });

  it("keeps each recommendation date visible on candidate rows", () => {
    const data = {
      screener: {
        strategy_key: "first_board",
        latest_trade_date: "2026-06-05",
        confirmed_candidates: [
          { symbol: "603319", name: "美湖股份", confirmed_trade_date: "2026-06-05", board_date: "2026-05-29" },
        ],
        candidates: [
          { symbol: "601208", name: "东材科技", quote_timestamp: "2026-06-04 15:03:00", board_date: "2026-05-28" },
        ],
      },
    } as PlaybookDataset;

    const candidates = candidateFamilies(data).flatMap((family) => family.items);

    expect(candidates.map((item) => [item.symbol, item.recommendDate])).toEqual([
      ["603319", "2026-06-05"],
      ["601208", "2026-06-04"],
    ]);
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
