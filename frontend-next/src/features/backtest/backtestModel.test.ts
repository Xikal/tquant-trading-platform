import { describe, expect, it } from "vitest";
import {
  attributionRowsFromDetail,
  executionAssumptionRows,
  logRowsFromDetail,
  oosRowsFromDetail,
  strategyOptionsFromMeta,
} from "./backtestModel";

describe("backtest display model", () => {
  it("builds strategy options from backend meta before run fallbacks", () => {
    const options = strategyOptionsFromMeta({
      strategies: [
        { key: "hidden", display_name: "隐藏", enabled: true, visibility: "hidden", sort_order: 1 },
        { key: "n_pattern_long_wash", display_name: "N形洗盘研究", enabled: true, sort_order: 2, tier: "research" },
        { key: "first_board", name: "首板回调", enabled: true, sort_order: 1, tier: "core" },
      ],
    }, [{ strategy_keys: ["fallback"] }]);

    expect(options.map((item) => [item.key, item.label])).toEqual([
      ["first_board", "首板回调"],
      ["n_pattern_long_wash", "N形洗盘研究"],
    ]);
  });

  it("extracts attribution, logs and OOS rows only from backend payload fields", () => {
    const detail = {
      updated_at: "2026-06-05T15:02:00",
      attribution: {
        industry: [{ bucket: "半导体", signal_count: 4, trade_count: 2, win_rate_pct: 0.75 }],
      },
      result_quality: { notes: ["数据完整度通过"] },
      result: {
        oos_windows: [
          { market_state: "震荡", oos_start: "2026-04-01", oos_end: "2026-04-30", confidence: 0.82, verdict: "observe" },
        ],
      },
    };

    expect(attributionRowsFromDetail(detail)).toEqual([
      { label: "行业: 半导体", signal: 4, trades: 2, winRate: 0.75, tone: "indigo" },
    ]);
    expect(logRowsFromDetail(detail)[0]).toEqual({
      time: "15:02:00",
      level: "INFO",
      message: "数据完整度通过",
      source: "BACKTEST",
      tone: "blue",
    });
    expect(oosRowsFromDetail(detail)[0]).toMatchObject({
      state: "震荡",
      range: "2026-04-01 ~ 2026-04-30",
      confidence: "0.82",
      tone: "amber",
    });
  });

  it("returns empty display rows when backend payload has no matching fields", () => {
    const detail = { id: 1, strategy_keys: ["first_board"] };

    expect(attributionRowsFromDetail(detail)).toEqual([]);
    expect(logRowsFromDetail(detail)).toEqual([]);
    expect(oosRowsFromDetail(detail)).toEqual([]);
  });

  it("prefers backend execution assumptions over frontend fee literals", () => {
    const rows = executionAssumptionRows({
      execution_assumptions: {
        fee_model: {
          version: "paper_fee_v2",
          commission: "股票买卖双边 0.0085% / ETF 0.005%",
          stamp_tax: "股票卖出 0.05%",
          transfer_fee: "股票 0.001%",
        },
        slippage_model: { version: "conservative_bps" },
        source: "app.services.paper.fees.calculate_fee",
      },
      fee_model_version: "stale_frontend_value",
    });

    expect(rows).toContainEqual({ label: "费率模型", value: "paper_fee_v2" });
    expect(rows).toContainEqual({ label: "佣金", value: "股票买卖双边 0.0085% / ETF 0.005%" });
    expect(rows.map((row) => row.value)).not.toContain("0.03%");
  });

  it("falls back to explicit run fields without labeling fee model as a rate", () => {
    expect(executionAssumptionRows({
      params: { max_position_pct: "10%" },
      slippage_bps: 1.5,
      fee_model_version: "paper_fee_v2",
    })).toEqual([
      { label: "单笔最大仓位", value: "10%" },
      { label: "双向滑点 (bp)", value: "1.5" },
      { label: "费率模型", value: "paper_fee_v2" },
    ]);
  });
});
