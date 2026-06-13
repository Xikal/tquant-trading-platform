import { describe, expect, it } from "vitest";
import { createLocalDesktopStatusModel } from "./localDesktopModel";

describe("localDesktopModel", () => {
  it("summarizes component status without recomputing backend state", () => {
    const model = createLocalDesktopStatusModel({
      generated_at: "2026-06-13T14:30:00+08:00",
      app: "tquant-local",
      environment: "local",
      version: "abc1234",
      components: [
        { name: "backend", status: "ok", latency_ms: 1, message: "ready" },
        { name: "mysql", status: "error", latency_ms: 12, message: "connection failed" },
        { name: "redis", status: "unknown", latency_ms: 0, message: "not configured" },
      ],
      directories: [{ key: "logs", path: "/tmp/logs", exists: true }],
      launch_guides: [
        {
          key: "web",
          label: "本机 Web/API",
          command: "scripts/run_platform_component.sh web",
          description: "启动 FastAPI 本机进程。",
        },
      ],
      safety: {
        deploy_allowed: false,
        restart_production_allowed: false,
        cleanup_allowed: false,
        auto_trade_allowed: false,
        strategy_mutation_allowed: false,
      },
    });

    expect(model.overallStatus).toBe("error");
    expect(model.statusText).toBe("存在异常");
    expect(model.summary).toContain("1 个异常");
    expect(model.components.map((item) => item.label)).toEqual(["后端 API", "数据库", "Redis"]);
    expect(model.components[1]?.message).toBe("connection failed");
    expect(model.launchGuides[0]?.command).toBe("scripts/run_platform_component.sh web");
    expect(model.safety.every((item) => item.allowed === false)).toBe(true);
  });

  it("returns a readable fallback when backend is unavailable", () => {
    const model = createLocalDesktopStatusModel(undefined, new Error("network down"));

    expect(model.overallStatus).toBe("error");
    expect(model.statusText).toBe("无法连接");
    expect(model.summary).toContain("本机后端不可达");
    expect(model.components[0]?.status).toBe("error");
    expect(model.launchGuides[0]?.command).toBe("scripts/run_platform_component.sh web");
  });

  it("adds a port conflict hint when the backend connection is reset or refused", () => {
    const model = createLocalDesktopStatusModel(undefined, new Error("fetch failed: ECONNREFUSED"));

    expect(model.summary).toContain("端口可能未监听或被占用");
    expect(model.components[0]?.message).toContain("端口可能未监听或被占用");
  });

  it("does not expose trading or production operation wording", () => {
    const renderedText = JSON.stringify(createLocalDesktopStatusModel(undefined, new Error("failed")));

    expect(renderedText).not.toContain("必涨");
    expect(renderedText).not.toContain("建议买入");
    expect(renderedText).not.toContain("立即买入");
    expect(renderedText).not.toContain("自动下单");
    expect(renderedText).not.toContain("一键部署");
    expect(renderedText).not.toContain("重启生产");
  });

  it("keeps launch guides as text-only local commands", () => {
    const model = createLocalDesktopStatusModel({
      generated_at: "2026-06-13T14:30:00+08:00",
      app: "tquant-local",
      environment: "local",
      components: [],
      directories: [],
      launch_guides: [
        {
          key: "runtime_worker",
          label: "Runtime Worker",
          command: "scripts/run_platform_component.sh runtime-worker",
          description: "处理已入队任务。",
          optional: false,
        },
        {
          key: "analytics_worker",
          label: "Analytics Worker",
          command: "scripts/run_platform_component.sh analytics-worker",
          description: "仅维护窗口使用。",
          optional: true,
        },
      ],
      safety: {},
    });

    expect(model.launchGuides).toHaveLength(2);
    expect(model.launchGuides[1]?.badgeText).toBe("按需");
    expect(JSON.stringify(model.launchGuides)).not.toContain("docker compose");
  });
});
