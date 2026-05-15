import type { BacktestRunSummary } from "../../api/backtests";
import { backtestVerdict } from "../../utils/uxClarity";
import { backtestVerdictThresholds } from "../backtest/backtestDisplay";

export type StrategyDoctorTone = "ok" | "warn" | "bad";

export interface StrategyDoctorVerdict {
  title: string;
  detail: string;
  action: string;
  tone: StrategyDoctorTone;
  run?: BacktestRunSummary;
}

export function latestFinishedRun(runs: BacktestRunSummary[]): BacktestRunSummary | undefined {
  return runs.find((run) => run.status === "completed" || run.status === "succeeded");
}

export function strategyDoctorVerdict(runs: BacktestRunSummary[]): StrategyDoctorVerdict {
  const run = latestFinishedRun(runs);
  if (!run) {
    const running = runs.find((item) => item.status === "running" || item.status === "queued" || item.status === "pending");
    if (running) {
      return {
        title: "体检正在进行",
        detail: "任务还在计算，完成后会自动显示收益、胜率和最大回撤。",
        action: "先等待任务完成",
        tone: "warn",
        run: running,
      };
    }
    return {
      title: "还没有策略体检结果",
      detail: "先运行一次一键体检，系统会用默认参数检查生产策略最近表现。",
      action: "点击一键体检",
      tone: "warn",
    };
  }
  const summary = run.summary ?? {};
  const verdict = backtestVerdict(
    numberOrUndefined(summary.total_return_pct),
    numberOrUndefined(summary.sharpe_ratio ?? summary.sharpe),
    numberOrUndefined(summary.max_drawdown_pct),
    backtestVerdictThresholds(run.resource_tier),
  );
  return {
    title: verdict.title,
    detail: plainLanguageDetail(verdict.tone, run),
    action: nextAction(verdict.tone),
    tone: verdict.tone,
    run,
  };
}

export function strategyHealthLabel(tone: StrategyDoctorTone): string {
  if (tone === "ok") return "可以继续观察";
  if (tone === "bad") return "暂不建议使用";
  return "谨慎观察";
}

function plainLanguageDetail(tone: StrategyDoctorTone, run: BacktestRunSummary): string {
  const summary = run.summary ?? {};
  const winRate = formatMaybePct(summary.win_rate_pct);
  const drawdown = formatMaybePct(summary.max_drawdown_pct);
  if (tone === "ok") {
    return `最近体检通过，胜率 ${winRate}，最大回撤 ${drawdown}，可以继续做样本外验证或小仓模拟跟踪。`;
  }
  if (tone === "bad") {
    return `最近体检不达标，胜率 ${winRate}，最大回撤 ${drawdown}，先不要用于自动交易。`;
  }
  return `结果不够强，胜率 ${winRate}，最大回撤 ${drawdown}，建议先看失败案例再决定。`;
}

function nextAction(tone: StrategyDoctorTone): string {
  if (tone === "ok") return "下一步：查看信号复盘或做样本外验证";
  if (tone === "bad") return "下一步：查看失败信号，暂停参数晋级";
  return "下一步：复盘最近信号，必要时重新体检";
}

function numberOrUndefined(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function formatMaybePct(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "暂无";
  return `${value.toFixed(1)}%`;
}
