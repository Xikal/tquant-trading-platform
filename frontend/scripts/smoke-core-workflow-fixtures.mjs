import {
  emptyList,
  mockAnalysis,
  mockDataQualitySla,
  mockDataSources,
  mockEtfUniverseAdmin,
  mockPaperAccount,
  mockPaperAutoTradingStatus,
  mockPaperDashboard,
  mockPaperPerformance,
  mockPaperSectorEtfT0Performance,
  mockPaperStockPnl,
  mockPaperWorkspace,
  mockRuntimeTasks,
  mockStrategyMeta,
  mockTradeGate,
  mockUser,
  now,
} from "./smoke-responsive-fixtures.mjs";
import {
  authRefreshPayload,
  backtestRunsPayload,
  emptyPagedList,
  instrumentRulesPayload,
  klinePayload,
  lowBuyPayload,
  lowBuyStrategiesPayload,
  marketBreadthPayload,
  monitorSnapshotPayload,
  monitorWorkspacePayload,
  priorityBoardPayload,
  quantParametersPayload,
  quotePayload,
  quoteRefreshPayload,
  runtimePayload,
  sectorExclusionsPayload,
  settingsWorkspacePayload,
  tradingReadinessPayload,
  tradingSessionPayload,
} from "./smoke-core-workflow-payloads.mjs";

export function createCoreWorkflowApiMock({ staleScenario = false } = {}) {
  return async function handleApiRequest(route) {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    const response = (body, status = 200) => route.fulfill({
      status,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(body),
    });

    if (path === "/auth/me") return response({ user: mockUser });
    if (path === "/auth/refresh") return response(authRefreshPayload());
    if (path === "/auth/logout") return response({ message: "ok" });
    if (path === "/strategies/meta") return response({ strategies: mockStrategyMeta });
    if (path === "/strategy/presets") return response({ presets: [] });
    if (path === "/settings/feature-flags") return response({ items: [], flags: {}, updated_at: now });
    if (path === "/trading-experience/readiness") return response(tradingReadinessPayload());

    if (path === "/bff/v1/workspace/monitor") return response(monitorWorkspacePayload(staleScenario));
    if (path === "/monitor/snapshot") return response(monitorSnapshotPayload(staleScenario));
    if (path === "/market/breadth") return response(marketBreadthPayload(staleScenario));
    if (path === "/market/hourly-snapshots/history") return response({ items: [], total: 0 });
    if (path === "/market/sector-relative-strength") return response({ trade_date: "2026-05-26", items: [] });
    if (path === "/market/sector-etf-t0") return response({ items: [], opportunities: [] });
    if (path === "/market/paired-hedge-research") return response(null);
    if (path === "/market/review-summary") return response({ review_status: null, review_reports: [] });
    if (path === "/market/trading-session") return response(tradingSessionPayload());
    if (path === "/intraday/subscribe") return response({ stream_token: "smoke-stream-token", expires_in: 60 });

    if (path === "/screeners/low-buy") return response(lowBuyPayload(staleScenario));
    if (path === "/screeners/low-buy/priority-board") return response(priorityBoardPayload(staleScenario));
    if (path === "/screeners/low-buy/quotes") return response(quoteRefreshPayload());
    if (path === "/screeners/low-buy/strategies") return response(lowBuyStrategiesPayload());

    if (path === "/backtests/runs") return response(backtestRunsPayload());
    if (path === "/backtests") return response({ items: [], total: 0, limit: 20, offset: 0 });
    if (path === "/backtests/verdict-thresholds") return response({ thresholds: {} });
    if (path === "/backtests/compare") return response({ items: [] });
    if (path === "/backtests/optimize" || path.startsWith("/backtests/optimize?")) return response(emptyPagedList());
    if (path === "/backtests/validate" || path.startsWith("/backtests/validate?")) return response(emptyPagedList());
    if (path === "/backtests/live-comparison") return response({ items: [], total: 0 });
    if (path === "/backtests/strategy-improvement-report") return response({ items: [], notes: [] });
    if (path.startsWith("/backtests/")) return response(emptyList);
    if (path === "/quant/parameters/current") return response(quantParametersPayload());
    if (path === "/quant/parameters/schema") return response({});

    if (path === "/bff/v1/workspace/paper") return response(mockPaperWorkspace);
    if (path === "/paper/account") return response(mockPaperAccount);
    if (path === "/paper/positions" || path === "/paper/positions/refresh") {
      return response({ positions: [], total_market_value: 0, total_unrealized_pnl: 0 });
    }
    if (path === "/paper/orders") return response([]);
    if (path === "/paper/trades") return response({ trades: [] });
    if (path === "/paper/trades/tags") return response({ items: {} });
    if (path === "/paper/performance") return response(mockPaperPerformance);
    if (path === "/paper/performance/stock-pnl") return response(mockPaperStockPnl);
    if (path === "/paper/performance/dashboard") return response(mockPaperDashboard);
    if (path === "/paper/performance/sector-etf-t0") return response(mockPaperSectorEtfT0Performance);
    if (path === "/paper/performance/by-strategy") return response([]);
    if (path === "/paper/performance/by-market-state") return response([]);
    if (path === "/paper/performance/by-strategy-market-state") return response([]);
    if (path === "/paper/performance/by-tag") return response([]);
    if (path === "/paper/risk/events") return response([]);
    if (path === "/paper/auto-trading/status") return response(mockPaperAutoTradingStatus);
    if (path === "/paper/auto-trading/runs") return response([]);
    if (path === "/paper/account/reconcile") return response({ account_id: 1, issue_count: 0, fixed_count: 0, issues: [], apply: false });

    if (path === "/bff/v1/workspace/settings") return response(settingsWorkspacePayload());
    if (path === "/settings/runtime") return response(runtimePayload());
    if (path === "/settings/sector-exclusions") return response(sectorExclusionsPayload());
    if (path === "/settings/factor-weights") return response({ weights: {}, defaults: {}, factors: [] });
    if (path === "/admin/tasks") return response({ items: [] });
    if (path === "/admin/metrics") return response({});
    if (path === "/data-quality/sla") return response(mockDataQualitySla);
    if (path === "/data-quality/trade-gate") return response(mockTradeGate);
    if (path === "/market/data-sources/health") return response(mockDataSources);
    if (path === "/runtime-tasks") return response(mockRuntimeTasks);
    if (path === "/market/etf-universe/admin") return response(mockEtfUniverseAdmin);

    if (path === "/analyze") return response(mockAnalysis);
    if (path === "/analyze/batch") return response([mockAnalysis]);
    if (path === "/ai/decision-support") return response({ enabled: false, summary: "smoke", suggestions: [], warnings: [] });
    if (path.startsWith("/quote/")) return response(quotePayload());
    if (path.startsWith("/kline/")) return response(klinePayload());
    if (/^\/instruments\/[^/]+\/rules$/.test(path)) return response(instrumentRulesPayload());
    if (/^\/instruments\/[^/]+\/sector$/.test(path)) return response({ sector_name: "ETF", sector_strength: 58, market_strength: 52, alignment_score: 61, notes: "smoke" });
    if (/^\/instruments\/[^/]+\/events$/.test(path)) return response({ symbol: "510300", events: [] });

    return response({});
  };
}
