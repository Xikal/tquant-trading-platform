import type { Page } from "../workspace-shared/workspaceTypes";
import type { ModeSafetyKind } from "../../ui/feedback/ModeSafetyBadges";

export type DenoisedWorkspacePage = Extract<Page, "monitor" | "monitor-market" | "strategy-tracking" | "data">;

export interface PageResponsibility {
  page: DenoisedWorkspacePage;
  label: string;
  coreQuestion: string;
  firstScreenConclusion: string;
  commandHint: string;
  primaryQuestion: string;
  detailQuestion: string;
  drilldownPattern: string;
  primarySections: readonly string[];
  detailSections: readonly string[];
  emptyFallback: string;
  featureFlagFallback: string;
  heavyListSurface: readonly ("DataTable" | "VirtualCardList")[];
  modeBadges: readonly ModeSafetyKind[];
}

export const WORKSPACE_PAGE_RESPONSIBILITIES: Record<DenoisedWorkspacePage, PageResponsibility> = {
  monitor: {
    page: "monitor",
    label: "实时行动",
    coreQuestion: "今天行动什么",
    firstScreenConclusion: "今日结论、生产优先榜、持仓提醒和个股关键位先给可执行动作，市场上下文移到市场环境台。",
    commandHint: "今日结论、优先榜、持仓提醒",
    primaryQuestion: "今天有哪些信号需要行动或观察",
    detailQuestion: "哪个候选、持仓或关键位需要继续处理",
    drilldownPattern: "首屏结论 + 生产优先榜 + 持仓/自选 + 个股关键位",
    primarySections: ["今日结论", "生产优先榜", "持仓提醒", "个股关键位"],
    detailSections: ["策略 lane", "风险过滤", "榜单详情", "持仓编辑"],
    emptyFallback: "冷启动或慢源失败时保留上次快照，并显式显示 stale / partial / no_data。",
    featureFlagFallback: "关闭监控合包或 overlay flag 后仍展示既有监控查询和空状态。",
    heavyListSurface: ["VirtualCardList"],
    modeBadges: ["shadow", "research", "watch"],
  },
  "monitor-market": {
    page: "monitor-market",
    label: "市场环境",
    coreQuestion: "市场是否支持行动",
    firstScreenConclusion: "市场总闸、市场宽度、日内脉冲、板块轮动、ETF T0、复盘与数据质量集中展示。",
    commandHint: "市场总闸、宽度、脉冲和复盘",
    primaryQuestion: "市场是否支持行动",
    detailQuestion: "哪些市场、板块或数据质量条件影响行动",
    drilldownPattern: "市场总闸 + 宽度/脉冲 + 板块/ETF + 复盘/运行时",
    primarySections: ["市场总闸", "市场宽度", "日内脉冲", "板块轮动", "数据质量"],
    detailSections: ["ETF T0", "市场复盘", "运行时状态", "同步状态"],
    emptyFallback: "慢源、无数据或降级源时展示 stale / partial / no_data，不影响行动台既有候选。",
    featureFlagFallback: "关闭监控合包或市场上下文 flag 后保留市场环境台空态和既有监控查询。",
    heavyListSurface: ["VirtualCardList"],
    modeBadges: ["shadow", "research", "watch"],
  },
  "strategy-tracking": {
    page: "strategy-tracking",
    label: "策略跟踪",
    coreQuestion: "信号后来怎么样",
    firstScreenConclusion: "先展示信号表现、风险分布、复盘结论和抗跌事实，明细进入表格和分析面板。",
    commandHint: "信号表现、复盘、抗跌事实",
    primaryQuestion: "生产信号后续是否有效",
    detailQuestion: "哪些信号需要复盘、漂移或降级",
    drilldownPattern: "结论条 + 筛选抽屉 + 明细表 + 二级分析页签",
    primarySections: ["信号表现", "风险分布", "复盘结论", "抗跌事实"],
    detailSections: ["信号明细", "持仓分析", "漂移监控", "交易经验研究"],
    emptyFallback: "无快照或研究 flag 关闭时显示明确空态，不留空白面板。",
    featureFlagFallback: "关闭交易经验 suite 后只隐藏研究面板，策略跟踪主表和复盘仍可用。",
    heavyListSurface: ["DataTable", "VirtualCardList"],
    modeBadges: ["shadow", "research", "watch"],
  },
  data: {
    page: "data",
    label: "数据中心",
    coreQuestion: "数据是否可靠",
    firstScreenConclusion: "先展示数据源、覆盖率、补数任务和质量门禁，运行时兜底只做告警和阻断。",
    commandHint: "数据源、覆盖率、补数任务",
    primaryQuestion: "当前数据是否可用于交易判断",
    detailQuestion: "哪些数据源、覆盖率或补数任务阻塞生产",
    drilldownPattern: "健康结论 + 巡检网格 + 维护折叠区",
    primarySections: ["数据源", "覆盖率", "补数任务", "质量门禁"],
    detailSections: ["运行时兜底", "供应商状态", "任务队列", "同步日志"],
    emptyFallback: "无权限、无数据或 worker 异常时显示 blocked / stale / no_data，不伪造新数据。",
    featureFlagFallback: "关闭运行时兜底面板后保留数据健康总览和补数入口。",
    heavyListSurface: ["DataTable"],
    modeBadges: ["shadow", "preview", "research"],
  },
};

export const WORKSPACE_DENOISED_PAGES = Object.keys(WORKSPACE_PAGE_RESPONSIBILITIES) as DenoisedWorkspacePage[];

const responsibilityPages = new Set<string>(WORKSPACE_DENOISED_PAGES);

export function isDenoisedWorkspacePage(page: Page): page is DenoisedWorkspacePage {
  return responsibilityPages.has(page);
}

export function pageResponsibility(page: Page): PageResponsibility | null {
  return isDenoisedWorkspacePage(page) ? WORKSPACE_PAGE_RESPONSIBILITIES[page] : null;
}

export function pageResponsibilityHint(page: Page, fallback: string): string {
  return pageResponsibility(page)?.commandHint ?? fallback;
}
