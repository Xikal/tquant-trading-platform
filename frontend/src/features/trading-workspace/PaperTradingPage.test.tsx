import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PaperTradingPage } from "../paper/PaperTradingPage";

describe("PaperTradingPage", () => {
  it("renders paper trading panels and mecha order cockpit", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: false }}
        autoTradingRuns={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).not.toContain("模拟交易");
    expect(html).toContain("机甲指挥舱");
    expect(html).toContain("+委托");
    expect(html).toContain("详情信息");
    expect(html).toContain("策略绩效");
    expect(html).toContain("对账诊断");
  });

  it("shows main force paper advice on positions", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[{
          id: 1,
          symbol: "600000",
          name: "测试股份",
          quantity: 1000,
          available_quantity: 1000,
          frozen_quantity: 0,
          cost_basis: 10,
          latest_price: 10.5,
          market_value: 10500,
          unrealized_pnl: 500,
          unrealized_pnl_pct: 5,
          strategy_sources: ["volume_shrink"],
          opened_at: "2026-05-28T10:00:00",
          main_force_paper_advice: {
            visible: true,
            mode: "readonly_shadow",
            suggestion_enabled: false,
            stage_text: "洗盘确认",
            model_action_text: "小仓试买",
            action_text: "旁路观察，不自动下单",
            production_effect: "paper_readonly_shadow",
          },
        } as any]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: false }}
        autoTradingRuns={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).toContain("主力：洗盘确认 · 小仓试买 · 旁路观察，不自动下单");
  });

  it("uses account-level total return for the top paper metric", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={{
          id: 1,
          name: "测试账户",
          initial_cash: 100000,
          cash_available: 50000,
          frozen_cash: 0,
          market_value: 51230,
          total_assets: 101230,
          realized_pnl: 0,
          unrealized_pnl: 1230,
          total_return_pct: 1.23,
          max_drawdown_pct: 0,
          status: "active",
          today_return_pct: 1.23,
        }}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={{
          total_return_pct: -9.99,
          max_drawdown_pct: 0,
          win_rate_pct: 0,
          net_win_rate_pct: 0,
          avg_trade_return_pct: 0,
          avg_win_pct: 0,
          avg_loss_pct: 0,
          profit_factor: null,
          stop_loss_rate_pct: 0,
          total_trades: 0,
          avg_hold_days: 0,
          win_loss_ratio: null,
        }}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: false }}
        autoTradingRuns={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).toContain("总收益率");
    expect(html).toContain("+1.23%");
    expect(html).not.toContain("-9.99%");
  });

  it("locks manual order entry when auto trading is running", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: true }}
        autoTradingRuns={[]}
        draft={{
          symbol: "510300",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).toContain("超频");
    expect(html).toContain("disabled");
  });

  it("does not require an intraday confirmation card before manual buy", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: false }}
        autoTradingRuns={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).not.toContain("盘中确认已通过");
    expect(html).not.toContain("确认买入");
    expect(html).toContain("自动交易触发");
  });

  it("explains auto trading without any manual confirmation copy", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: true, engine_running: true, trading_time: true }}
        autoTradingRuns={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).not.toContain("可以进入委托确认");
    expect(html).not.toContain("确认买入");
    expect(html).not.toContain("分时确认");
    expect(html).toContain("自动交易按计划轮询，不依赖人工确认");
  });

  it("keeps paper review as history entry instead of the main review surface", () => {
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={null}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        performanceDashboard={{
          account: { id: 1, total_assets: 100500, total_return_pct: 0.5, sharpe_ratio: 1.2 },
          equity_curve: [],
          win_rate_trend: [],
          strategy_trend: [],
          market_perf_heatmap: [],
          strategy_market_matrix: [],
          today_report: {
            id: 1,
            report_date: "2026-05-25",
            report_slot: "midday",
            overall_summary: "模拟盘日报稳定",
            strategy_highlights: [],
            risk_alerts: [],
            suggestion: "午后控制追高",
            generated_at: "2026-05-25 11:35:00",
            llm_model: "",
          },
          review_reports: [
            {
              id: 1,
              report_date: "2026-05-25",
              report_slot: "midday",
              review_subject: "全市场",
              source_scope: "market",
              overall_summary: "午盘市场稳定",
              strategy_highlights: [],
              risk_alerts: [],
              suggestion: "午后控制追高",
              generated_at: "2026-05-25 11:35:00",
              llm_model: "",
            },
            {
              id: 2,
              report_date: "2026-05-25",
              report_slot: "close",
              review_subject: "全市场",
              source_scope: "market",
              overall_summary: "收盘市场复盘完成",
              strategy_highlights: [],
              risk_alerts: [],
              suggestion: "明日优先处理弱势仓位",
              generated_at: "2026-05-25 15:05:00",
              llm_model: "",
            },
          ],
          updated_at: "2026-05-25 15:05:00",
        }}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{ running: false }}
        autoTradingRuns={[]}
        draft={{
          symbol: "",
          name: "",
          side: "buy",
          order_type: "market",
          quantity: "100",
          price: "",
          current_price: "",
          strategy_key: "",
          reason: "",
          require_intraday_confirmation: false,
        }}
        setDraft={vi.fn()}
        loading=""
        onSubmitOrder={vi.fn()}
        onTogglePause={vi.fn()}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
      />
    );

    expect(html).toContain("复盘历史入口 · 2 条");
    expect(html).not.toContain("明日优先处理弱势仓位");
  });
});
