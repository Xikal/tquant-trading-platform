import { renderToStaticMarkup } from "react-dom/server";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import type { DataQualitySnapshotItem } from "../../api/dataQuality";
import { createAppQueryClient } from "../../state/queryClient";
import { useDataConsoleUiStore } from "../../stores/dataConsoleUiStore";
import type { AuthUser } from "../../types";
import { visiblePrimaryNav } from "../trading-workspace/navConfig";
import { CollectionJobsPanel } from "./CollectionJobsPanel";
import { CoveragePanel } from "./CoveragePanel";
import { DataConsolePage } from "./DataConsolePage";
import { DataHealthOverview } from "./DataHealthOverview";
import { DataSourceHealthPanel } from "./DataSourceHealthPanel";
import { DATA_CONSOLE_SERVER_KEYS } from "./useDataConsole";
import { DataRepairPanel } from "./DataRepairPanel";
import { InstrumentInspectorPanel } from "./InstrumentInspectorPanel";
import { TradeDataGateCard } from "./TradeDataGateCard";
import { datasetLabel, qualityLabel, scopeLabel, severityLabel, statusLabel, taskStatusLabel } from "./dataConsoleTypes";
import { shouldPollRuntimeTasks } from "./useDataConsole";

const ADMIN_USER: AuthUser = {
  id: 1,
  username: "admin",
  display_name: "Admin",
  roles: ["admin"],
  can_paper_trade: true,
  created_at: "2026-06-01T00:00:00+08:00",
};

const NORMAL_USER: AuthUser = {
  ...ADMIN_USER,
  id: 2,
  username: "user",
  roles: [],
};

describe("DataConsolePage", () => {
  it("shows data nav only to administrators", () => {
    expect(visiblePrimaryNav(ADMIN_USER).map((item) => item.key)).toContain("data");
    expect(visiblePrimaryNav(NORMAL_USER).map((item) => item.key)).not.toContain("data");
  });

  it("uses data center wording for unauthorized users", () => {
    const html = renderToStaticMarkup(<DataConsolePage currentUser={NORMAL_USER} />);

    expect(html).toContain("数据中心");
    expect(html).toContain("当前账号没有数据中心权限");
    expect(html).not.toContain("数据控制台");
  });

  it("maps internal data console codes to Chinese labels", () => {
    expect(statusLabel("blocked_by_data")).toBe("缺数据已停用");
    expect(statusLabel("stale")).toBe("待更新");
    expect(qualityLabel("degraded")).toBe("质量下降");
    expect(qualityLabel("failed")).toBe("不可用");
    expect(severityLabel("red")).toBe("不通过");
    expect(taskStatusLabel("queued")).toBe("排队中");
    expect(taskStatusLabel("succeeded")).toBe("已完成");
    expect(datasetLabel("daily_bars")).toBe("日线");
    expect(scopeLabel("production_universe")).toBe("交易标的池");
  });

  it("disables write actions when admin token is missing", () => {
    const html = renderToStaticMarkup(
      <CollectionJobsPanel
        adminReady={false}
        disabledReason="先填管理令牌才能操作"
        tasks={[]}
        loading={false}
        error=""
        datasetKey="daily_bars"
        scope="all"
        startDate="2026-05-01"
        endDate="2026-05-29"
        onFieldChange={() => undefined}
        onSyncInstruments={() => undefined}
        onRefreshCloseData={() => undefined}
        onBackfill={() => undefined}
        onRefresh={() => undefined}
      />,
    );

    expect(html).toContain("先填管理令牌才能操作");
    expect(html).toContain("disabled");
  });

  it("polls runtime tasks only while visible and unfinished", () => {
    expect(shouldPollRuntimeTasks([{ status: "running" }], "visible")).toBe(true);
    expect(shouldPollRuntimeTasks([{ status: "succeeded" }], "visible")).toBe(false);
    expect(shouldPollRuntimeTasks([{ status: "queued" }], "hidden")).toBe(false);
  });

  it("renders trade gate red state with concrete reasons", () => {
    const html = renderToStaticMarkup(
      <TradeDataGateCard
        loading={false}
        error=""
        gate={{
          ok: false,
          checks: [
            { key: "sla", label: "关键 SLA", ok: false, severity: "red", detail: "日线缺数据已停用" },
            { key: "source", label: "主数据源状态", ok: false, severity: "red", detail: "source offline" },
          ],
        }}
        onRefresh={() => undefined}
      />,
    );

    expect(html).toContain("关键数据不可用，先暂停使用");
    expect(html).toContain("日线缺数据已停用");
    expect(html).toContain("数据源离线");
    expect(html).toContain("不通过");
    expect(html).not.toContain(">red<");
  });

  it("renders data center as conclusion, inspection and collapsed maintenance layers", () => {
    useDataConsoleUiStore.setState({
      adminToken: "",
      coverageStatusFilter: "all",
      coverageScopeFilter: "all",
      selectedDatasetKey: "daily_bars",
      selectedScope: "all",
      backfillStartDate: "2026-05-01",
      backfillEndDate: "2026-05-29",
      repairDatasetKey: "daily_bars",
      repairConfirmOpen: false,
      inspectorSymbol: "",
    });
    const queryClient = createAppQueryClient();
    queryClient.setQueryData(DATA_CONSOLE_SERVER_KEYS.sla, {
      items: dataQualityItemsFixture(),
      latest_repair_audits: [],
      total: 3,
    });
    queryClient.setQueryData(DATA_CONSOLE_SERVER_KEYS.sources, {
      updated_at: "2026-06-01T15:00:00+08:00",
      provider_order: ["eastmoney"],
      summary: "degraded",
      items: [{ source: "eastmoney", ok: true, quality: "degraded", latency_ms: 32, is_stale: false, warning: "" }],
    });
    queryClient.setQueryData(DATA_CONSOLE_SERVER_KEYS.coverage, {
      dataset_key: "daily_bars",
      scope: "all",
      missing_symbols: [],
      missing_dates: [],
    });
    queryClient.setQueryData(DATA_CONSOLE_SERVER_KEYS.tasks, [
      { id: 7, task_type: "daily_bar_refresh", status: "queued", progress_pct: 0, created_at: "2026-06-01T15:01:00+08:00" },
    ]);
    queryClient.setQueryData(DATA_CONSOLE_SERVER_KEYS.gate, {
      ok: false,
      checks: [{ key: "sla", label: "关键 SLA", ok: false, severity: "red", detail: "日线缺数据已停用" }],
    });

    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <DataConsolePage currentUser={ADMIN_USER} />
      </QueryClientProvider>
    );

    expect(html).toContain("数据中心");
    expect(html).toContain("今日数据能不能用");
    expect(html).toContain("今日数据状态");
    expect(html).toContain("能否用于交易");
    expect(html).toContain("日常巡检");
    expect(html).toContain("数据来源是否正常");
    expect(html).toContain("数据完整度");
    expect(html).toContain("数据维护");
    expect(html).toContain("先填管理令牌才能操作");
    expect(html).toContain("所有更新都交后台处理，不会动你的持仓和交易。");
    expect(html).toContain("质量下降");
    expect(html).not.toMatch(/[A-H] 数据|实盘前数据门|数据控制台|综合灯|阻断|过期|探测|需填写管理令牌|>red<|>degraded<|>queued</);
  });

  it("localizes data console status, dataset and scope labels", () => {
    const coverageHtml = renderToStaticMarkup(
      <CoveragePanel
        items={dataQualityItemsFixture()}
        detail={{ dataset_key: "daily_bars", scope: "all", missing_symbols: [], missing_dates: [] }}
        loading={false}
        error=""
        statusFilter="blocked"
        scopeFilter="all"
        onStatusFilterChange={() => undefined}
        onScopeFilterChange={() => undefined}
        onSelectDetail={() => undefined}
        onRefresh={() => undefined}
      />,
    );
    const staleCoverageHtml = renderToStaticMarkup(
      <CoveragePanel
        items={dataQualityItemsFixture()}
        detail={null}
        loading={false}
        error=""
        statusFilter="stale"
        scopeFilter="all"
        onStatusFilterChange={() => undefined}
        onScopeFilterChange={() => undefined}
        onSelectDetail={() => undefined}
        onRefresh={() => undefined}
      />,
    );
    const jobsHtml = renderToStaticMarkup(
      <CollectionJobsPanel
        adminReady={false}
        disabledReason="先填管理令牌才能操作"
        tasks={[
          { id: 1, task_type: "daily_bar_refresh", status: "queued", progress_pct: 0 },
          { id: 2, task_type: "data_quality_repair", status: "succeeded", progress_pct: 100 },
          { id: 3, task_type: "data_quality_backfill", status: "failed", progress_pct: 20, error_message: "daily_bars blocked_by_data failed" },
        ]}
        loading={false}
        error=""
        datasetKey="daily_bars"
        scope="production_universe"
        startDate="2026-05-01"
        endDate="2026-05-29"
        onFieldChange={() => undefined}
        onSyncInstruments={() => undefined}
        onRefreshCloseData={() => undefined}
        onBackfill={() => undefined}
        onRefresh={() => undefined}
      />,
    );
    const repairHtml = renderToStaticMarkup(
      <DataRepairPanel
        audits={[{
          id: 1,
          repair_id: "repair-1",
          dataset_key: "daily_bars",
          reason: "invalid_rows",
          backup_path: "/tmp/backup",
          refetch_result: "ok",
          deleted_rows_count: 2,
          fabricated: false,
          operator: "admin",
          created_at: "2026-06-01T15:00:00+08:00",
        }]}
        adminReady={false}
        disabledReason="先填管理令牌才能操作"
        loading={false}
        error=""
        datasetKey="daily_bars"
        confirmOpen
        onDatasetChange={() => undefined}
        onDryRun={() => undefined}
        onOpenConfirm={() => undefined}
        onConfirmApply={() => undefined}
        onCancelConfirm={() => undefined}
      />,
    );
    const inspectorHtml = renderToStaticMarkup(
      <InstrumentInspectorPanel
        symbol="600000"
        loading={false}
        error=""
        result={{
          symbol: "600000",
          quote: null,
          kline: null,
          rules: null,
          sector: null,
          events: [],
          partial_errors: [],
        }}
        onSymbolChange={() => undefined}
        onInspect={() => undefined}
      />,
    );
    const html = `${coverageHtml}${staleCoverageHtml}${jobsHtml}${repairHtml}${inspectorHtml}`;

    expect(html).toContain("日线");
    expect(html).toContain("全市场");
    expect(html).toContain("交易标的池");
    expect(html).toContain("缺数据已停用");
    expect(html).toContain("待更新");
    expect(html).toContain("应有");
    expect(html).toContain("实有");
    expect(html).toContain("异常行");
    expect(html).toContain("仅看不可用");
    expect(html).toContain("仅看待更新");
    expect(html).toContain("更新标的库");
    expect(html).toContain("拉取今日收盘数据");
    expect(html).toContain("补历史数据");
    expect(html).toContain("排队中");
    expect(html).toContain("已完成");
    expect(html).toContain("失败");
    expect(html).toContain("日线 缺数据已停用 失败");
    expect(html).toContain("是否伪造");
    expect(html).toContain("否");
    expect(html).toContain("检查");
    expect(html).not.toMatch(/title="daily_bars"|>blocked_by_data<|>stale<|>queued<|>succeeded<|>failed<|>daily_bars<|>minute_bars<|>tick_trades<|期望|实际|标的库同步|当日收盘刷新|区间回补|刷新任务|巡检|fabricated|>false<|>missing<|>partial<|>ok</);
  });

  it("keeps module errors isolated from healthy panels", () => {
    const html = renderToStaticMarkup(
      <>
        <DataHealthOverview data={null} loading={false} error="SLA 加载失败" onRefresh={() => undefined} onShowBlocked={() => undefined} />
        <DataSourceHealthPanel
          loading={false}
          error=""
          data={{
            updated_at: "2026-06-01T15:00:00+08:00",
            provider_order: ["eastmoney"],
            summary: "ok",
            items: [{ source: "eastmoney", ok: true, quality: "ok", latency_ms: 32, is_stale: false, warning: "" }],
          }}
          onRefresh={() => undefined}
        />
      </>,
    );

    expect(html).toContain("SLA 加载失败");
    expect(html).toContain("eastmoney");
  });
});

function dataQualityItemsFixture(): DataQualitySnapshotItem[] {
  return [
    {
      dataset_key: "daily_bars",
      as_of_date: "2026-05-31",
      scope: "all",
      expected_days: 20,
      actual_days: 18,
      missing_days: 2,
      invalid_rows: 1,
      duplicate_rows: 0,
      stale: false,
      coverage_pct: 90,
      status: "blocked_by_data",
      blockers: ["行情源缺日线"],
      checked_at: "2026-06-01T15:00:00+08:00",
    },
    {
      dataset_key: "minute_bars",
      as_of_date: "2026-05-31",
      scope: "production_universe",
      expected_days: 20,
      actual_days: 19,
      missing_days: 1,
      invalid_rows: 0,
      duplicate_rows: 0,
      stale: true,
      coverage_pct: 95,
      status: "stale",
      blockers: [],
      checked_at: "2026-06-01T14:00:00+08:00",
    },
    {
      dataset_key: "tick_trades",
      as_of_date: "2026-05-31",
      scope: "watchlist",
      expected_days: 20,
      actual_days: 20,
      missing_days: 0,
      invalid_rows: 0,
      duplicate_rows: 0,
      stale: false,
      coverage_pct: 100,
      status: "ok",
      blockers: [],
      checked_at: "2026-06-01T15:30:00+08:00",
    },
  ];
}
