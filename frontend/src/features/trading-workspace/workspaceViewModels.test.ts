import { describe, expect, it } from "vitest";

import { candidateToCard, settingsPayload, trackedPlaybookSymbols, watchSignalToCard } from "../workspace-shared/workspaceViewModels";

describe("workspaceViewModels", () => {
  it("keeps playbook symbols unique across confirmed and watch buckets", () => {
    const payload = {
      confirmed_candidates: [{ symbol: "300059" }],
      candidates: [{ symbol: "300059" }, { symbol: "510300" }],
    };

    expect(trackedPlaybookSymbols(payload as never)).toEqual(["300059", "510300"]);
  });

  it("converts settings drafts by section", () => {
    const draft = {
      adminToken: "token",
      llm_provider: "deepseek",
      llm_api_key: "secret",
      llm_base_url: "https://api.example.com",
      llm_model: "deepseek-v4-pro",
      data_source: "akshare",
      data_source_base_url: "",
      risk_max_single_loss_pct: "1.2",
      risk_max_daily_loss_pct: "3",
      risk_pause_after_losses: "3",
      strategy_min_profit_pct: "0.8",
    };

    expect(settingsPayload(draft, "llm")).toMatchObject({ llm_provider: "deepseek", llm_model: "deepseek-v4-pro" });
    expect(settingsPayload(draft, "risk")).toMatchObject({ risk_max_single_loss_pct: 1.2, risk_pause_after_losses: 3 });
  });

  it("renders a low-buy candidate as an actionable card", () => {
    const card = candidateToCard({
      name: "测试股份",
      symbol: "600000",
      strategy_key: "first_board",
      strategy_title: "首板回调",
      latest_price: 10.12,
      change_pct: 1.23,
      score: 88,
      risk_tier: "note",
      suggested_position_text: "15%",
      buy_signal_text: "接近买点",
      entry_zone_low: 9.8,
      entry_zone_high: 10.2,
      stop_loss: 9.5,
      summary_reason: "价格接近支撑",
      recommendation_days: 2,
      recommendation_start_date: "2026-04-28",
    } as never);

    expect(card.name).toBe("测试股份");
    expect(card.details).toContain("9.800-10.200");
    expect(card.details).toContain("连续推荐 2天");
  });

  it("renders main force advice in low-buy card details", () => {
    const card = candidateToCard({
      name: "测试股份",
      symbol: "600000",
      strategy_key: "volume_shrink",
      strategy_title: "缩量回踩",
      latest_price: 10.12,
      change_pct: 1.23,
      score: 88,
      risk_tier: "note",
      suggested_position_text: "15%",
      buy_signal_text: "接近买点",
      entry_zone_low: 9.8,
      entry_zone_high: 10.2,
      stop_loss: 9.5,
      summary_reason: "价格接近支撑",
      main_force_advice: {
        stage_text: "洗盘确认",
        action_text: "小仓试买",
        score: 68.5,
        production_effect: "readonly_shadow",
        reasons: ["回撤适中"],
        risk_flags: [],
      },
    } as never);

    expect(card.details).toContain("主力：洗盘确认 · 小仓试买 · 68.5");
    expect(card.details).toContain("旁路观察");
    expect(card.badges).toContain("主力洗盘确认");
  });

  it("renders watchlist signal with plain-language action", () => {
    const card = watchSignalToCard({
      symbol: "510300",
      name: "",
      cost_basis: 4.02,
      memo: "缩量观望",
      quote: { name: "沪深300ETF", last_price: 4.081, change_pct: -0.42 },
      signal: {
        action: "positive_t",
        plain_action_text: "等回踩确认后做正T",
        signal_score: 76,
        risk_level: "low",
        expected_profit_pct: 1.4,
        position_pct: 25,
        stop_loss: 4.03,
        plain_action_reason: "回踩承接",
        scenario: "",
        trade_scene_text: "低开回踩",
      },
    } as never);

    expect(card.name).toBe("沪深300ETF");
    expect(card.identityNote).toContain("成本价");
    expect(card.details).toContain("回落时有人接盘");
  });
});
