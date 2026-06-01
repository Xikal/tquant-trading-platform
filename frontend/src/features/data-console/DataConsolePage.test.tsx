import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { AuthUser } from "../../types";
import { visiblePrimaryNav } from "../trading-workspace/navConfig";
import { CollectionJobsPanel } from "./CollectionJobsPanel";
import { DataHealthOverview } from "./DataHealthOverview";
import { DataSourceHealthPanel } from "./DataSourceHealthPanel";
import { TradeDataGateCard } from "./TradeDataGateCard";
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

  it("disables write actions when admin token is missing", () => {
    const html = renderToStaticMarkup(
      <CollectionJobsPanel
        adminReady={false}
        disabledReason="需填写管理令牌"
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

    expect(html).toContain("需填写管理令牌");
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
            { key: "sla", label: "关键 SLA", ok: false, severity: "red", detail: "daily_bars blocked_by_data" },
            { key: "source", label: "主数据源状态", ok: false, severity: "red", detail: "source offline" },
          ],
        }}
        onRefresh={() => undefined}
      />,
    );

    expect(html).toContain("关键数据缺失或阻断，暂不建议据此下单");
    expect(html).toContain("daily_bars blocked_by_data");
    expect(html).toContain("source offline");
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
