import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PlaybookPage } from "../playbook/PlaybookPage";

describe("PlaybookPage", () => {
  it("keeps hero metrics from duplicating into the compact metric grid", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="volume_shrink"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "volume_shrink",
          strategy_title: "缩量回踩",
          scanned_count: 18,
          candidates: [],
          confirmed_candidates: [],
          hot_industries: ["机器人"],
          latest_trade_date: beijingTodayString(),
          data_quality: "ok",
          data_quality_text: "数据完整",
          full_scan_ready: true,
          performance: {
            data_insufficient: false,
            filled_signals: 4,
            hit_rate: 62,
            avg_return_5d: 1.2,
            avg_max_drawdown_5d: -2.1,
            profit_factor: 1.4,
            market_state_attribution: [],
          },
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect((html.match(/全量深筛/g) ?? []).length).toBe(1);
    expect((html.match(/数据状态/g) ?? []).length).toBe(1);
    expect(html).toContain("确认可买");
    expect(html).toContain("真实成交样本");
    expect(html).toContain("5日达标率");
    expect(html).toContain("tq-playbook-candidate-tabs");
    expect(html).toContain("当前没有可以直接执行的股票");
    expect(html).not.toContain(">现在可买<");
    expect(html).toContain(">观察<span");
    expect(html).toContain(">等确认<span");
    expect(html).toContain(">观察/放弃<span");
  });

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
          latest_trade_date: beijingTodayString(),
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
    expect(html).toContain("今日主看");
    expect(html).toContain("今日红运");
    expect(html).toContain("tq-playbook-page");
    expect(html).toContain("tq-playbook-page__hero");
    expect(html).toContain("tq-playbook-page__performance");
    expect(html).toContain("tq-playbook-page__focus");
  });

  it("shows main force readonly advice in candidate list", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="volume_shrink"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "volume_shrink",
          strategy_title: "缩量回踩",
          scanned_count: 1,
          candidates: [],
          confirmed_candidates: [{
            name: "测试股份",
            symbol: "600000",
            strategy_key: "volume_shrink",
            strategy_title: "缩量回踩",
            latest_price: 10.12,
            change_pct: 1.23,
            score: 88,
            risk_tier: "note",
            suggested_position_text: "15%",
            buy_signal_state: "buy_now",
            buy_signal_text: "确定买入",
            entry_zone_low: 9.8,
            entry_zone_high: 10.2,
            stop_loss: 9.5,
            summary_reason: "价格接近支撑",
            reasons: [],
            risks: [],
            tags: [],
            main_force_advice: {
              stage_text: "洗盘确认",
              action_text: "小仓试买",
              score: 68.5,
              production_effect: "readonly_shadow",
              reasons: ["回撤适中"],
              risk_flags: [],
            },
          }],
          hot_industries: ["机器人"],
          latest_trade_date: beijingTodayString(),
          full_scan_ready: true,
          performance: null,
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect(html).not.toContain("主力：洗盘确认 · 小仓试买 · 68.5");
    expect(html).not.toContain("旁路观察");
    expect(html).toContain("价格接近支撑");
    expect(html).toContain("买点已至");
    expect(html).toContain("tq-playbook-candidate-tabs");
    expect(html).toContain("tq-playbook-dense-row");
    expect(html).toContain("tq-playbook-dense-row__meta");
  });

  it("shows observe-only stocks as strategy candidates without marking them buyable", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="volume_shrink"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "volume_shrink",
          strategy_title: "缩量回踩",
          scanned_count: 1,
          candidates: [],
          confirmed_candidates: [{
            name: "观察股份",
            symbol: "600123",
            strategy_key: "volume_shrink",
            strategy_title: "缩量回踩",
            latest_price: 10.12,
            change_pct: 1.23,
            score: 88,
            risk_tier: "note",
            suggested_position_text: "15%",
            buy_signal_state: "observe_confirmed",
            buy_signal_text: "观察确认",
            entry_zone_low: 9.8,
            entry_zone_high: 10.2,
            stop_loss: 9.5,
            summary_reason: "只观察",
            reasons: [],
            risks: [],
            tags: [],
          }],
          hot_industries: ["机器人"],
          latest_trade_date: beijingTodayString(),
          full_scan_ready: true,
          performance: null,
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect(html).toContain("当前无确认买入");
    expect(html).toContain("确认可买");
    expect(html).toContain('data-playbook-active-section="observe"');
    expect(html).toContain("tq-playbook-candidate-tabs");
    expect(html).not.toContain("当前没有可以直接执行的股票");
    expect(html).toContain(">观察<span");
    expect(html).toMatch(/>观察<span[^>]*tq-playbook-page__tab-count[^>]*>1<\/span>/);
    expect(html).toContain("观察：观察股份");
    expect(html).toContain("600123");
    expect(html).not.toContain("主看：观察股份");
  });

  it("opens the passive candidate tab when only watch or avoid stocks exist", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="first_board"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "first_board",
          strategy_title: "首板回调",
          scanned_count: 18,
          candidates: [{
            name: "观察候选",
            symbol: "603977",
            strategy_key: "first_board",
            strategy_title: "首板回调",
            latest_price: 10.12,
            change_pct: 1.23,
            score: 88,
            risk_tier: "note",
            suggested_position_text: "15%",
            buy_signal_state: "watch",
            buy_signal_text: "继续观察",
            entry_zone_low: 9.8,
            entry_zone_high: 10.2,
            stop_loss: 9.5,
            summary_reason: "未到买点",
            reasons: [],
            risks: [],
            tags: [],
          }],
          confirmed_candidates: [],
          hot_industries: ["机器人"],
          latest_trade_date: beijingTodayString(),
          full_scan_ready: true,
          performance: null,
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect(html).toContain('data-playbook-active-section="watch"');
    expect(html).toMatch(/>观察\/放弃<span[^>]*tq-playbook-page__tab-count[^>]*>1<\/span>/);
    expect(html).toContain("观察候选");
    expect(html).toContain("603977");
  });

  it("does not drop backend states that are unknown to the current frontend", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="first_board"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "first_board",
          strategy_title: "首板回调",
          scanned_count: 1,
          candidates: [{
            name: "新状态候选",
            symbol: "603888",
            strategy_key: "first_board",
            strategy_title: "首板回调",
            latest_price: 10.12,
            change_pct: 1.23,
            score: 88,
            risk_tier: "note",
            suggested_position_text: "15%",
            buy_signal_state: "backend_new_state",
            buy_signal_text: "新增观察状态",
            entry_zone_low: 9.8,
            entry_zone_high: 10.2,
            stop_loss: 9.5,
            summary_reason: "后端新增状态",
            reasons: [],
            risks: [],
            tags: [],
          }],
          confirmed_candidates: [],
          hot_industries: ["机器人"],
          latest_trade_date: beijingTodayString(),
          full_scan_ready: true,
          performance: null,
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect(html).toContain('data-playbook-active-section="watch"');
    expect(html).toContain("新状态候选");
    expect(html).toContain("603888");
    expect(html).toContain("新增观察状态");
  });

  it("keeps the more actionable state when the same stock appears in multiple buckets", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="first_board"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "first_board",
          strategy_title: "首板回调",
          scanned_count: 2,
          confirmed_candidates: [{
            name: "重复候选",
            symbol: "600001",
            strategy_key: "first_board",
            strategy_title: "首板回调",
            latest_price: 10.12,
            change_pct: 1.23,
            score: 88,
            risk_tier: "note",
            suggested_position_text: "15%",
            buy_signal_state: "observe_confirmed",
            buy_signal_text: "观察确认",
            entry_zone_low: 9.8,
            entry_zone_high: 10.2,
            stop_loss: 9.5,
            summary_reason: "观察版本",
            reasons: [],
            risks: [],
            tags: [],
          }],
          candidates: [{
            name: "重复候选",
            symbol: "600001",
            strategy_key: "first_board",
            strategy_title: "首板回调",
            latest_price: 10.12,
            change_pct: 1.23,
            score: 80,
            risk_tier: "note",
            suggested_position_text: "15%",
            buy_signal_state: "watch",
            buy_signal_text: "继续观察",
            entry_zone_low: 9.8,
            entry_zone_high: 10.2,
            stop_loss: 9.5,
            summary_reason: "弱版本",
            reasons: [],
            risks: [],
            tags: [],
          }],
          hot_industries: ["机器人"],
          latest_trade_date: beijingTodayString(),
          full_scan_ready: true,
          performance: null,
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect(html).toContain('data-playbook-active-section="observe"');
    expect(html).toContain("观察确认 · 观察版本");
    expect(html).not.toContain("继续观察 · 弱版本");
  });

  it("keeps backend stale-date candidates visible in their strategy state lanes", () => {
    const html = renderToStaticMarkup(
      <PlaybookPage
        strategy="volume_shrink"
        setStrategy={vi.fn()}
        playbook={{
          strategy_key: "volume_shrink",
          strategy_title: "缩量回踩",
          scanned_count: 1,
          candidates: [{
            name: "旧观察",
            symbol: "600456",
            strategy_key: "volume_shrink",
            strategy_title: "缩量回踩",
            latest_price: 10.12,
            change_pct: 1.23,
            score: 88,
            risk_tier: "note",
            suggested_position_text: "15%",
            buy_signal_state: "near_entry",
            buy_signal_text: "接近买点",
            entry_zone_low: 9.8,
            entry_zone_high: 10.2,
            stop_loss: 9.5,
            summary_reason: "旧交易日",
            reasons: [],
            risks: [],
            tags: [],
          }],
          confirmed_candidates: [],
          hot_industries: ["机器人"],
          latest_trade_date: "2026-01-01",
          stale: true,
          stale_reason: "当前选股宝典停留在 2026-01-01，距最新交易日 2026-01-05 已落后 2 个交易日，仅供复盘，不作为今日观察。",
          full_scan_ready: true,
          performance: null,
        } as any}
        loading=""
        onRefresh={vi.fn()}
        onAnalyze={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    expect(html).toContain(">等确认<span");
    expect(html).toMatch(/>等确认<span[^>]*tq-playbook-page__tab-count[^>]*>1<\/span>/);
    expect(html).toContain("观察：旧观察");
    expect(html).toContain("600456");
    expect(html).toContain("当前无确认买入");
    expect(html).toContain("推荐快照已过期");
    expect(html).toContain("仅供复盘");
  });
});

function beijingTodayString(): string {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value ?? "";
  const month = parts.find((part) => part.type === "month")?.value ?? "";
  const day = parts.find((part) => part.type === "day")?.value ?? "";
  return `${year}-${month}-${day}`;
}
