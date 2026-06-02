import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePaperUiStore } from "../../stores/paperUiStore";
import { ExecutionPreviewTab, PaperOrdersTab, PaperTradesTab, ReviewHistoryTab } from "../paper/PaperDetailTabs";
import { PaperTradingPage } from "../paper/PaperTradingPage";

describe("PaperTradingPage", () => {
  afterEach(() => {
    usePaperUiStore.setState({ detailTab: "today", detailGroup: "automation" });
  });

  it("renders paper trading as conclusion, main, and secondary sections", () => {
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

    expect(html).toContain("paper-conclusion");
    expect(html).toContain("模拟盘");
    expect(html).toContain("真实收益");
    expect(html).toContain("仓位与风控");
    expect(html).toContain("自动状态");
    expect(html).toContain("paper-main-grid");
    expect(html).not.toContain("主区：持仓与今日动作");
    expect(html).not.toContain("今日红运");
    expect(html).not.toContain("像素状态");
    expect(html).not.toContain("+委托");
    expect(html).not.toContain("打开模拟委托弹窗");
    expect(html).toContain("paper-hero-grid");
    expect(html).toContain("paper-mecha-action-panel");
    expect(html).toContain("模拟盘机甲交易舱");
    expect(html).toContain("壹式·紫");
    expect(html).not.toContain("[ 模拟交易事件 / 触发特效 ]");
    expect(html).not.toContain("SIMULATE ACTION");
    expect(html).toContain("实时同步监控日志");
    expect(html).not.toContain("次区：记录、表现与自动化");
    expect(html).toContain("自动化");
    expect(html).toContain("策略绩效");
    expect(html).not.toContain("表现（策略绩效）");
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

    expect(html).toContain("运行中");
    expect(html).not.toContain("+委托");
    expect(html).not.toContain("打开模拟委托弹窗");
  });

  it("shows a resume order button when risk review pauses new paper orders", () => {
    const blockingReason = "最近连续 3 次卖出亏损，模拟账户已暂停新增委托，请先复盘。";
    const html = renderToStaticMarkup(
      <PaperTradingPage
        account={{
          id: 1,
          name: "测试账户",
          initial_cash: 100000,
          cash_available: 50000,
          frozen_cash: 0,
          market_value: 50000,
          total_assets: 100000,
          realized_pnl: 0,
          unrealized_pnl: 0,
          total_return_pct: 0,
          max_drawdown_pct: 0,
          status: "active",
          today_return_pct: 0,
        }}
        positions={[]}
        orders={[]}
        trades={[]}
        performance={null}
        strategyPerformance={[]}
        marketPerformance={[]}
        tagPerformance={[]}
        tradeTags={{}}
        riskEvents={[]}
        autoTradingStatus={{
          running: false,
          trading_time: true,
          account_status: "paused",
          blocking_reason: blockingReason,
        }}
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

    expect(html).toContain("未买原因");
    expect(html).toContain(blockingReason);
    expect(html).toContain("恢复委托");
    expect(html).not.toContain("恢复自动委托");
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
    expect(html).not.toContain("自动 (AUTO)");
    expect(html).toContain("SYS_FLOW: OK");
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
    expect(html).not.toContain("系统自动执行中");
    expect(html).not.toContain("自动 (AUTO)");
    expect(html).toContain("实时同步监控日志");
  });

  it("keeps paper page free of the full-market review entry", () => {
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

    expect(html).not.toContain("复盘历史入口 · 2 条");
    expect(html).not.toContain("今日收盘福袋");
    expect(html).not.toContain("明日优先处理弱势仓位");
  });

  it("places review history and portfolio execution preview under paper detail tabs", () => {
    const dashboard = {
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
      review_reports: [{
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
      }],
      updated_at: "2026-05-25 15:05:00",
    };
    const baseProps = {
      account: null,
      positions: [],
      orders: [],
      trades: [],
      performance: {
        total_trades: 2,
        win_rate_pct: 50,
        total_return_pct: 0.8,
        net_win_rate_pct: 50,
        avg_trade_return_pct: 1.2,
        avg_win_pct: 2.1,
        avg_loss_pct: -1.1,
        profit_factor: 1.5,
        max_drawdown_pct: 2,
        stop_loss_rate_pct: 0,
        avg_hold_days: 2,
        win_loss_ratio: 1.9,
        portfolio_execution_preview: {
          capital_model_label: "真实组合执行预览",
          source: "paper_trades",
          candidate_count: 2,
          skip_reason_counts: {},
          notes: ["组合预览只读，不会触发委托。"],
          max_5: {
            capital_model: "max_5",
            capital_model_label: "最多 5 只",
            max_positions: 5,
            candidate_count: 2,
            trade_count: 1,
            skipped_count: 1,
            skipped_by_duplicate_symbol: 0,
            skipped_by_max_positions: 1,
            skipped_by_strategy_daily_limit: 0,
            skipped_by_sector_limit: 0,
            skipped_by_retreat_market: 0,
            skipped_by_weak_market_position_cap: 0,
            skip_reason_counts: {},
            portfolio_return_pct: 1.2,
            annualized_return_pct: 12,
            max_drawdown_pct: 2,
            profit_factor: 1.5,
            avg_trade_return_pct: 1,
            avg_capital_utilization_pct: 40,
          },
          max_10: {
            capital_model: "max_10",
            capital_model_label: "最多 10 只",
            max_positions: 10,
            candidate_count: 2,
            trade_count: 2,
            skipped_count: 0,
            skipped_by_duplicate_symbol: 0,
            skipped_by_max_positions: 0,
            skipped_by_strategy_daily_limit: 0,
            skipped_by_sector_limit: 0,
            skipped_by_retreat_market: 0,
            skipped_by_weak_market_position_cap: 0,
            skip_reason_counts: {},
            portfolio_return_pct: 1.6,
            annualized_return_pct: 14,
            max_drawdown_pct: 2.3,
            profit_factor: 1.8,
            avg_trade_return_pct: 1.1,
            avg_capital_utilization_pct: 55,
          },
        },
      },
      performanceDashboard: dashboard,
      strategyPerformance: [],
      marketPerformance: [],
      tagPerformance: [],
      tradeTags: {},
      riskEvents: [],
      autoTradingStatus: { running: false },
      autoTradingRuns: [],
      draft: {
        symbol: "",
        name: "",
        side: "buy" as const,
        order_type: "market" as const,
        quantity: "100",
        price: "",
        current_price: "",
        strategy_key: "",
        reason: "",
        require_intraday_confirmation: false,
      },
      setDraft: vi.fn(),
      loading: "",
      onSubmitOrder: vi.fn(),
      onTogglePause: vi.fn(),
      onAddTradeTag: vi.fn(),
      onDeleteTradeTag: vi.fn(),
    };

    const mainHtml = renderToStaticMarkup(<PaperTradingPage {...baseProps} />);
    expect(mainHtml).toContain("详情信息");
    expect(mainHtml).not.toContain("收盘市场复盘完成");
    expect(mainHtml).not.toContain("最多 5 只");
    expect(mainHtml).toContain("策略绩效");

    const reviewHtml = renderToStaticMarkup(<ReviewHistoryTab performanceDashboard={dashboard} />);
    expect(reviewHtml).toContain("复盘历史");
    expect(reviewHtml).toContain("模拟盘日报稳定");
    expect(reviewHtml).toContain("收盘市场复盘完成");

    const previewHtml = renderToStaticMarkup(<ExecutionPreviewTab performance={baseProps.performance} />);
    expect(previewHtml).toContain("组合执行预览");
    expect(previewHtml).toContain("最多 5 只");
    expect(previewHtml).toContain("组合预览只读，不会触发委托。");
  });

  it("renders order records as narrow viewport cards beside the virtual grid", () => {
    const html = renderToStaticMarkup(
      <PaperOrdersTab
        loading={false}
        orders={[
          {
            id: 7,
            account_id: 1,
            symbol: "600519",
            name: "贵州茅台",
            side: "buy",
            order_type: "limit",
            price: 1688.5,
            quantity: 100,
            filled_quantity: 40,
            avg_fill_price: 1688.1,
            status: "partial",
            reject_reason: null,
            source: "manual",
            strategy_key: "first_board",
            reason: "观察后手动委托",
            created_at: "2026-05-29T10:05:00",
          },
        ]}
      />
    );

    expect(html).toContain("paper-detail-card-list");
    expect(html).toContain("paper-order-mobile-card");
    expect(html).toContain("贵州茅台");
    expect(html).toContain("已成 40 股");
  });

  it("renders trade records as narrow viewport cards beside the virtual grid", () => {
    const html = renderToStaticMarkup(
      <PaperTradesTab
        loading={false}
        performance={null}
        tagPerformance={[]}
        tradeTags={{}}
        onAddTradeTag={vi.fn()}
        onDeleteTradeTag={vi.fn()}
        trades={[
          {
            id: 9,
            order_id: 7,
            account_id: 1,
            symbol: "600519",
            side: "sell",
            price: 1702.3,
            quantity: 100,
            gross_amount: 170230,
            commission: 5,
            stamp_tax: 170.23,
            transfer_fee: 0,
            net_amount: 170054.77,
            strategy_key: "first_board",
            entry_reason: "",
            entry_reason_code: "",
            exit_reason: "达到计划价",
            exit_reason_code: "target",
            commission_warning: "",
            trade_time: "2026-05-29T14:35:00",
          },
        ]}
      />
    );

    expect(html).toContain("paper-detail-card-list");
    expect(html).toContain("paper-trade-mobile-card");
    expect(html).toContain("600519");
    expect(html).toContain("达到计划价");
  });
});
