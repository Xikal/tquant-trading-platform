import type { Page } from "../workspace-shared/workspaceTypes";

export type DenoisedWorkspacePage = Extract<Page, "monitor" | "strategy-tracking" | "paper" | "data" | "backtest">;

export interface PageResponsibility {
  page: DenoisedWorkspacePage;
  label: string;
  coreQuestion: string;
  firstScreenConclusion: string;
  commandHint: string;
  primarySections: readonly string[];
  detailSections: readonly string[];
  emptyFallback: string;
  featureFlagFallback: string;
  heavyListSurface: readonly ("DataTable" | "VirtualCardList")[];
}

export const WORKSPACE_PAGE_RESPONSIBILITIES: Record<DenoisedWorkspacePage, PageResponsibility> = {
  monitor: {
    page: "monitor",
    label: "实时监控",
    coreQuestion: "今天看什么",
    firstScreenConclusion: "市场状态、生产优先榜、持仓提醒和关键位先给结论，复盘与快照放到更多区。",
    commandHint: "市场状态、优先榜、持仓提醒",
    primarySections: ["市场状态", "生产优先榜", "持仓提醒", "关键位"],
    detailSections: ["ETF 做T替代", "全市场复盘", "小时快照"],
    emptyFallback: "冷启动或慢源失败时保留上次快照，并显式显示 stale / partial / no_data。",
    featureFlagFallback: "关闭监控合包或 overlay flag 后仍展示既有监控查询和空状态。",
    heavyListSurface: ["VirtualCardList"],
  },
  "strategy-tracking": {
    page: "strategy-tracking",
    label: "策略跟踪",
    coreQuestion: "信号后来怎么样",
    firstScreenConclusion: "先展示信号表现、风险分布、复盘结论和抗跌事实，明细进入表格和分析面板。",
    commandHint: "信号表现、复盘、抗跌事实",
    primarySections: ["信号表现", "风险分布", "复盘结论", "抗跌事实"],
    detailSections: ["信号明细", "持仓分析", "漂移监控", "交易经验研究"],
    emptyFallback: "无快照或研究 flag 关闭时显示明确空态，不留空白面板。",
    featureFlagFallback: "关闭交易经验 suite 后只隐藏研究面板，策略跟踪主表和复盘仍可用。",
    heavyListSurface: ["DataTable", "VirtualCardList"],
  },
  paper: {
    page: "paper",
    label: "模拟盘",
    coreQuestion: "执行结果如何",
    firstScreenConclusion: "持仓、成交、真实收益、风险和复盘分层展示，机甲与实时日志合并为执行状态区。",
    commandHint: "持仓、成交、收益和风险",
    primarySections: ["持仓", "成交", "真实收益", "风险"],
    detailSections: ["自动化日志", "策略绩效", "对账诊断", "复盘历史"],
    emptyFallback: "无持仓、无成交或纪律 flag 关闭时保留模拟盘结论区和明确空态。",
    featureFlagFallback: "关闭持仓纪律或 T 归因 flag 后只隐藏扩展面板，不影响模拟盘账户视图。",
    heavyListSurface: ["VirtualCardList"],
  },
  data: {
    page: "data",
    label: "数据中心",
    coreQuestion: "数据是否可靠",
    firstScreenConclusion: "先展示数据源、覆盖率、补数任务和质量门禁，运行时兜底只做告警和阻断。",
    commandHint: "数据源、覆盖率、补数任务",
    primarySections: ["数据源", "覆盖率", "补数任务", "质量门禁"],
    detailSections: ["运行时兜底", "供应商状态", "任务队列", "同步日志"],
    emptyFallback: "无权限、无数据或 worker 异常时显示 blocked / stale / no_data，不伪造新数据。",
    featureFlagFallback: "关闭运行时兜底面板后保留数据健康总览和补数入口。",
    heavyListSurface: ["DataTable"],
  },
  backtest: {
    page: "backtest",
    label: "回测页",
    coreQuestion: "策略是否值得保留",
    firstScreenConclusion: "先展示 24 个月报告、样本外验证、组合收益和策略建议，研究细节进入二级面板。",
    commandHint: "24个月报告和组合收益",
    primarySections: ["24 个月报告", "样本外验证", "组合收益", "策略建议"],
    detailSections: ["回测记录", "归因明细", "相关性", "容量研究"],
    emptyFallback: "数据不足 24 个月时显式 blocked 或触发 worker 补数任务，不展示半成品结论。",
    featureFlagFallback: "关闭研究或优化 flag 后保留正式回测记录、状态和空态。",
    heavyListSurface: ["DataTable", "VirtualCardList"],
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
