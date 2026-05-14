import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { ResearchPage } from "./ResearchPage";

describe("ResearchPage", () => {
  it("renders saved backtest runs for comparison", () => {
    const html = renderToStaticMarkup(
      <ResearchPage
        replays={[]}
        priorityBoard={null}
        lifecycleItems={[]}
        draft={{
          symbol: "510300",
          bar_period: "5m",
          lookback_bars: "480",
          initial_position: "1000",
          walk_forward_windows: "4",
          low_buy_strategy: "first_board",
          low_buy_lookback_days: "60",
          low_buy_limit: "160",
        }}
        setDraft={vi.fn()}
        result={null}
        runs={[{
          id: 7,
          name: "sample",
          params: { symbol: "510300" },
          result: { win_rate: 61.5, avg_pnl_pct: 1.16 },
          created_at: "2026-05-03T10:00:00",
        }]}
        executionBacktest={null}
        strategyValidation={null}
        loading=""
        onRun={vi.fn()}
        onValidate={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(html).toContain("历史回测 #7");
    expect(html).toContain("510300");
  });

  it("renders replay samples as readable case stories", () => {
    const html = renderToStaticMarkup(
      <ResearchPage
        replays={[{
          id: 1,
          symbol: "600519",
          outcome: "止盈退出",
          pnl_pct: 3.2,
          max_favorable_excursion: 4.8,
          max_adverse_excursion: -1.1,
          review_notes: "缩量承接有效，次日冲高兑现。",
          created_at: "2026-05-03T10:00:00",
        }]}
        priorityBoard={null}
        lifecycleItems={[]}
        draft={{
          symbol: "510300",
          bar_period: "5m",
          lookback_bars: "480",
          initial_position: "1000",
          walk_forward_windows: "4",
          low_buy_strategy: "first_board",
          low_buy_lookback_days: "60",
          low_buy_limit: "160",
        }}
        setDraft={vi.fn()}
        result={null}
        runs={[]}
        executionBacktest={null}
        strategyValidation={null}
        loading=""
        onRun={vi.fn()}
        onValidate={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(html).toContain("复盘案例故事");
    expect(html).toContain("月度结论");
    expect(html).toContain("最大冲高");
    expect(html).toContain("缩量承接有效");
  });
});
