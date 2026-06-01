import { describe, expect, it } from "vitest";

import { candidateToCard, priorityToCard, settingsPayload, trackedPlaybookSymbols, watchSignalToCard } from "../workspace-shared/workspaceViewModels";

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
    expect(card.details).toContain("价格接近支撑");
    expect(card.details).not.toContain(" / ");
    expect(card.executionHint).toContain("连续跟踪 2天");
    expect(card.expectedText).toBeUndefined();
    expect(card.operationAmountText).toBe("15%");
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

    expect(card.details).toContain("价格接近支撑");
    expect(card.details).not.toContain("旁路观察");
    expect(card.badges).toContain("主力洗盘确认");
    expect(card.badges).toHaveLength(2);
  });

  it("keeps observation priority cards out of buy-recommendation copy and caps card density", () => {
    const nearEntry = priorityToCard({
      name: "观察股份",
      symbol: "300001",
      sector_name: "半导体",
      strategy_key: "front_row",
      strategy_title: "前排加权",
      strategy_titles: ["前排加权", "N 字洗盘", "缩量回踩", "涨停回踩"],
      strategy_count: 4,
      family_count: 3,
      latest_price: 20.5,
      change_pct: 2.1,
      buy_signal_state: "near_entry",
      buy_signal_text: "接近买点",
      action_summary: "接近买点",
      next_action_text: "等承接确认",
      priority_score: 72,
      production_score: 82,
      entry_zone_low: 19.8,
      entry_zone_high: 20.2,
      stop_loss: 19.2,
      suggested_position_text: "10%",
      display_lane: "front_row_weighted",
      mainline_tier_text: "核心主线",
      leader_strength_rank: 1,
      multi_timeframe_resonance_score: 88,
      matched_strategy_variants: ["baseline", "front_row_weighted", "front_row_only"],
      primary_lane_reason: "只进入影子验证，不参与真实生产排序",
      recommendation_days: 3,
      recommendation_start_date: "2026-05-27",
      risk_tier: "note",
    } as never);

    expect(nearEntry.identityNote).toBe("前排加权 · 模拟验证中");
    expect(nearEntry.scoreText).toBe("影子分 82（仅验证）");
    expect(nearEntry.expectedText).toBeUndefined();
    expect(nearEntry.details).toBe("等承接确认");
    expect(nearEntry.details).not.toContain(" / ");
    expect(nearEntry.badges).toHaveLength(2);
    expect(`${nearEntry.actionText} ${nearEntry.executionHint} ${nearEntry.failureText}`).toContain("观察类");
    expect(`${nearEntry.actionText} ${nearEntry.executionHint} ${nearEntry.failureText}`).toContain("不是买入");
    expect(`${nearEntry.actionText} ${nearEntry.executionHint} ${nearEntry.failureText}`).not.toContain("买入推荐");

    const watchOnly = priorityToCard({
      name: "只观察股份",
      symbol: "300002",
      strategy_key: "front_row_only",
      strategy_title: "前排极精选",
      strategy_titles: ["前排极精选"],
      strategy_count: 1,
      latest_price: 9.8,
      change_pct: -0.4,
      buy_signal_state: "observe_confirmed",
      buy_signal_text: "观察确认",
      action_summary: "观察确认",
      next_action_text: "继续提醒",
      priority_score: 61,
      elite_watch_score: 75,
      entry_zone_low: 9.6,
      entry_zone_high: 10,
      stop_loss: 9.2,
      suggested_position_text: "0%",
      display_lane: "front_row_only",
      risk_tier: "degrade",
    } as never);

    expect(watchOnly.identityNote).toBe("前排极精选 · 只观察，不参与买入排序");
    expect(watchOnly.scoreText).toBe("观察分 75（只观察）");
    expect(`${watchOnly.actionText} ${watchOnly.executionHint} ${watchOnly.failureText}`).toContain("不是买入");
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
