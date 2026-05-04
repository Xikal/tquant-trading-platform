import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PlaybookPage } from "./PlaybookPage";

describe("PlaybookPage", () => {
  it("shows strategy switching state when selected tab differs from loaded playbook", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="volume_shrink"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "first_board",
          strategy_title: "首板回调",
          scanned_count: 0,
          candidates: [],
          confirmed_candidates: [],
          hot_industries: ["机器人"],
          latest_trade_date: "2026-05-04",
          full_scan_ready: true,
          performance: {
            data_insufficient: true,
            filled_signals: 0,
            hit_rate: 0,
            avg_return_5d: 0,
            avg_max_drawdown_5d: 0,
            profit_factor: 0,
            cvar_5pct: 0,
            kelly_half_position_pct: 0,
            avg_win_pct: 0,
            avg_loss_pct: 0,
            market_state_attribution: [],
          },
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect(html).toContain("当前策略：量能低吸");
    expect(html).toContain("已加载：首板回调，正在切换数据");
    expect(html).toContain("机器人");
  });
});
