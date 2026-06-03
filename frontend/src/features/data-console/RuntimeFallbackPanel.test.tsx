import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { RuntimeFallbackStatus } from "../../api/dataQuality";
import { RuntimeFallbackPanel } from "./RuntimeFallbackPanel";

describe("RuntimeFallbackPanel", () => {
  it("renders missing heartbeat state", () => {
    const html = renderToStaticMarkup(
      <RuntimeFallbackPanel
        status={statusFixture({ worker_status: "missing", blocking: true, heartbeat_age_seconds: null })}
        loading={false}
        error=""
        onRefresh={() => undefined}
      />,
    );

    expect(html).toContain("后台未运行");
    expect(html).toContain("启动或重启 后台刷新进程");
  });

  it("renders queued critical task state", () => {
    const html = renderToStaticMarkup(
      <RuntimeFallbackPanel
        status={statusFixture({
          blocking: true,
          critical_queued_count: 1,
          oldest_critical_queued_age_seconds: 900,
        })}
        loading={false}
        error=""
        onRefresh={() => undefined}
      />,
    );

    expect(html).toContain("关键刷新排队过久");
    expect(html).toContain("待处理");
  });

  it("renders normal state", () => {
    const html = renderToStaticMarkup(
      <RuntimeFallbackPanel
        status={statusFixture()}
        loading={false}
        error=""
        onRefresh={() => undefined}
      />,
    );

    expect(html).toContain("后台正常");
    expect(html).toContain("无积压");
  });
});

function statusFixture(overrides: Partial<RuntimeFallbackStatus> = {}): RuntimeFallbackStatus {
  return {
    worker_status: "running",
    worker_id: "runtime-test",
    heartbeat_updated_at: "2026-06-03T16:00:00",
    heartbeat_age_seconds: 10,
    critical_queued_count: 0,
    oldest_critical_queued_at: "",
    oldest_critical_queued_age_seconds: null,
    blocking: false,
    message: "runtime worker running and critical refresh queue is clear",
    recovery_actions: ["启动或重启 runtime-worker"],
    ...overrides,
  };
}
