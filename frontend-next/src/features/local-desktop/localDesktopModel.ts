export type LocalDesktopStatusValue = "ok" | "error" | "unknown";

export interface LocalDesktopComponentStatus {
  name: string;
  status: LocalDesktopStatusValue;
  latency_ms?: number;
  message?: string;
  details?: Record<string, unknown>;
}

export interface LocalDesktopDirectoryStatus {
  key: string;
  path: string;
  exists: boolean;
}

export interface LocalDesktopStatusResponse {
  generated_at: string;
  app: string;
  environment: string;
  version?: string;
  components: LocalDesktopComponentStatus[];
  directories: LocalDesktopDirectoryStatus[];
  launch_guides?: LocalDesktopLaunchGuide[];
  safety: Record<string, boolean>;
}

export interface LocalDesktopLaunchGuide {
  key: string;
  label: string;
  command: string;
  description: string;
  optional?: boolean;
}

export interface LocalDesktopStatusModel {
  overallStatus: LocalDesktopStatusValue;
  statusText: string;
  summary: string;
  generatedAt: string;
  app: string;
  environment: string;
  version: string;
  components: LocalDesktopComponentView[];
  directories: LocalDesktopDirectoryView[];
  launchGuides: LocalDesktopLaunchGuideView[];
  safety: LocalDesktopSafetyView[];
}

export interface LocalDesktopComponentView {
  key: string;
  label: string;
  status: LocalDesktopStatusValue;
  statusText: string;
  message: string;
  latencyText: string;
}

export interface LocalDesktopDirectoryView {
  key: string;
  label: string;
  path: string;
  exists: boolean;
}

export interface LocalDesktopLaunchGuideView {
  key: string;
  label: string;
  command: string;
  description: string;
  badgeText: string;
}

export interface LocalDesktopSafetyView {
  key: string;
  label: string;
  allowed: boolean;
  stateText: string;
}

const COMPONENT_LABELS: Record<string, string> = {
  backend: "后端 API",
  mysql: "数据库",
  sqlite: "数据库",
  database: "数据库",
  redis: "Redis",
  runtime_worker: "Runtime Worker",
  runtime_scheduler: "Runtime Scheduler",
};

const DIRECTORY_LABELS: Record<string, string> = {
  project: "项目目录",
  logs: "日志目录",
  data: "数据目录",
  reports: "报告目录",
  frontend_dist: "前端构建目录",
};

const SAFETY_LABELS: Record<string, string> = {
  deploy_allowed: "部署入口",
  restart_production_allowed: "生产重启入口",
  cleanup_allowed: "清理入口",
  auto_trade_allowed: "交易执行入口",
  strategy_mutation_allowed: "策略修改入口",
};

export function createLocalDesktopStatusModel(payload: unknown, error?: unknown): LocalDesktopStatusModel {
  if (error || !isStatusResponse(payload)) return fallbackModel(error);
  const components = payload.components.map(componentView);
  const directories = payload.directories.map(directoryView);
  const launchGuides = (payload.launch_guides ?? []).map(launchGuideView);
  const safety = safetyViews(payload.safety);
  const errorCount = components.filter((item) => item.status === "error").length;
  const unknownCount = components.filter((item) => item.status === "unknown").length;
  const overallStatus: LocalDesktopStatusValue = errorCount > 0 ? "error" : unknownCount > 0 ? "unknown" : "ok";

  return {
    overallStatus,
    statusText: statusLabel(overallStatus),
    summary: summaryText(errorCount, unknownCount),
    generatedAt: payload.generated_at || "--",
    app: payload.app || "tquant-local",
    environment: payload.environment || "local",
    version: payload.version || "--",
    components,
    directories,
    launchGuides,
    safety,
  };
}

function fallbackModel(error: unknown): LocalDesktopStatusModel {
  const rawMessage = error instanceof Error && error.message ? error.message : "本机后端不可达，请检查 API 地址或后端进程。";
  const message = `${rawMessage}${portHint(rawMessage)}`;
  return {
    overallStatus: "error",
    statusText: "无法连接",
    summary: `本机后端不可达：${message}`,
    generatedAt: "--",
    app: "tquant-local",
    environment: "local",
    version: "--",
    components: [
      {
        key: "backend",
        label: "后端 API",
        status: "error",
        statusText: "异常",
        message,
        latencyText: "--",
      },
    ],
    directories: [],
    launchGuides: defaultLaunchGuides().map(launchGuideView),
    safety: safetyViews({}),
  };
}

function portHint(message: string): string {
  const normalized = message.toLowerCase();
  if (
    normalized.includes("econnrefused") ||
    normalized.includes("connection refused") ||
    normalized.includes("failed to fetch") ||
    normalized.includes("load failed")
  ) {
    return "；端口可能未监听或被占用，请检查本机 API 地址和后端端口。";
  }
  return "";
}

function componentView(component: LocalDesktopComponentStatus): LocalDesktopComponentView {
  return {
    key: component.name,
    label: COMPONENT_LABELS[component.name] ?? component.name,
    status: component.status,
    statusText: statusLabel(component.status),
    message: component.message || statusLabel(component.status),
    latencyText: typeof component.latency_ms === "number" && component.latency_ms > 0 ? `${Math.round(component.latency_ms)} ms` : "--",
  };
}

function directoryView(directory: LocalDesktopDirectoryStatus): LocalDesktopDirectoryView {
  return {
    key: directory.key,
    label: DIRECTORY_LABELS[directory.key] ?? directory.key,
    path: directory.path,
    exists: directory.exists,
  };
}

function launchGuideView(guide: LocalDesktopLaunchGuide): LocalDesktopLaunchGuideView {
  return {
    key: guide.key,
    label: guide.label,
    command: guide.command,
    description: guide.description,
    badgeText: guide.optional ? "按需" : "常用",
  };
}

function defaultLaunchGuides(): LocalDesktopLaunchGuide[] {
  return [
    {
      key: "web",
      label: "本机 Web/API",
      command: "scripts/run_platform_component.sh web",
      description: "启动 FastAPI 本机进程，默认监听 127.0.0.1:8000。",
    },
    {
      key: "runtime_worker",
      label: "Runtime Worker",
      command: "scripts/run_platform_component.sh runtime-worker",
      description: "处理已入队的数据刷新、物化和修复任务；不会由桌面端自动启动。",
    },
    {
      key: "runtime_scheduler",
      label: "Runtime Scheduler",
      command: "scripts/run_platform_component.sh scheduler",
      description: "按本地配置入队周期任务；启动前需确认不会与其他 scheduler 重复运行。",
    },
    {
      key: "analytics_worker",
      label: "Analytics Worker",
      command: "scripts/run_platform_component.sh analytics-worker",
      description: "仅在维护窗口处理 DuckDB/Parquet/分析类任务；默认可不常驻。",
      optional: true,
    },
  ];
}

function safetyViews(safety: Record<string, boolean>): LocalDesktopSafetyView[] {
  return Object.entries(SAFETY_LABELS).map(([key, label]) => {
    const allowed = safety[key] === true;
    return {
      key,
      label,
      allowed,
      stateText: allowed ? "开放" : "关闭",
    };
  });
}

function statusLabel(status: LocalDesktopStatusValue): string {
  if (status === "ok") return "正常";
  if (status === "error") return "存在异常";
  return "未知";
}

function summaryText(errorCount: number, unknownCount: number): string {
  if (errorCount > 0) return `${errorCount} 个异常，${unknownCount} 个未知；请先处理异常组件。`;
  if (unknownCount > 0) return `${unknownCount} 个未知；可继续使用已可用模块。`;
  return "本机服务状态正常，安全边界已关闭。";
}

function isStatusResponse(value: unknown): value is LocalDesktopStatusResponse {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return Array.isArray(record.components) && Array.isArray(record.directories) && typeof record.safety === "object";
}
