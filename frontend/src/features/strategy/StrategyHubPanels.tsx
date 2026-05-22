import type { BacktestRunSummary } from "../../api/backtests";
import { Button } from "antd";
import { EmptyPlaceholder } from "../../components/shared/Feedback";
import type { AuthUser } from "../../types";
import {
  formatBacktestStrategies,
  formatDateTime,
  formatMoney,
  formatPct,
} from "../backtest/backtestDisplay";
import { DataTable } from "../../ui/table/DataTable";
import { StrategySignalReplayPanel } from "./StrategySignalReplayPanel";
import { strategyDoctorVerdict, strategyHealthLabel } from "./strategyVerdict";
import { canOptimize, canResearchFactors, canValidate, isAdmin } from "./strategyPermissions";
import type { StrategyHubTab } from "./useStrategyHub";

export function RecentRuns({ runs, onRerun }: { runs: BacktestRunSummary[]; onRerun?: (run: BacktestRunSummary) => void }) {
  if (!runs.length) {
    return <EmptyPlaceholder title="暂无回测任务" description="提交快速回测后会显示最近任务。" />;
  }
  return (
    <div className="strategy-run-list">
      {runs.map((run, index) => (
        <article key={run.id}>
          <div>
            <strong>{run.name}</strong>
            <span>{formatBacktestStrategies(run.strategies)}</span>
          </div>
          <div>
            <b className={`strategy-status ${run.status}`}>{statusText(run.status)}</b>
            <small>{formatDateTime(run.created_at)}</small>
          </div>
          <RunVerdictSummary run={run} />
          <RunProgress run={run} />
          <div className="strategy-run-metrics">
            <span>收益 {runMetricPct(run, "total_return_pct")}</span>
            <span>胜率 {runMetricPct(run, "win_rate_pct")}</span>
            <span>资产 {runEquityText(run)}</span>
          </div>
          <RunDeltaSummary current={run} previous={runs[index + 1]} />
          {onRerun ? (
            <Button type="default" size="small" className="strategy-rerun-button" onClick={() => onRerun(run)}>
              重新运行
            </Button>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function RunVerdictSummary({ run }: { run: BacktestRunSummary }) {
  if (run.status === "running" || run.status === "queued" || run.status === "pending") {
    return (
      <div className="strategy-run-verdict warn">
        <strong>正在计算</strong>
        <span>完成后会显示是否值得继续使用。</span>
      </div>
    );
  }
  if (run.status === "failed") {
    return (
      <div className="strategy-run-verdict bad">
        <strong>任务失败</strong>
        <span>先查看失败原因，再重新提交体检。</span>
      </div>
    );
  }
  if (run.status === "cancelled" || run.status === "deleted") {
    return (
      <div className="strategy-run-verdict warn">
        <strong>任务已取消</strong>
        <span>这条任务没有产出体检结论，可以重新提交。</span>
      </div>
    );
  }
  if (run.status === "timeout") {
    return (
      <div className="strategy-run-verdict bad">
        <strong>任务超时</strong>
        <span>建议缩短时间范围，或改用轻量体检。</span>
      </div>
    );
  }
  const verdict = strategyDoctorVerdict([run]);
  return (
    <div className={`strategy-run-verdict ${verdict.tone}`}>
      <strong>{strategyHealthLabel(verdict.tone)}</strong>
      <span>{verdict.action}</span>
    </div>
  );
}

export function StrategyHistoryPanel({
  runs,
  onRefresh,
  onRerun,
}: {
  runs: BacktestRunSummary[];
  onRefresh: () => void;
  onRerun: (run: BacktestRunSummary) => void;
}) {
  const summary = summarizeRuns(runs);
  return (
    <section className="panel strategy-history">
      <div className="strategy-panel-title">
        <div>
          <h2>策略历史</h2>
          <span>集中追踪最近回测、验证和策略任务，避免在多个页面来回查找。</span>
        </div>
        <Button type="default" onClick={onRefresh}>刷新历史</Button>
      </div>
      <div className="strategy-history-summary">
        <article>
          <span>最近任务</span>
          <strong>{runs.length}</strong>
        </article>
        <article>
          <span>完成任务</span>
          <strong>{summary.completed}</strong>
        </article>
        <article>
          <span>平均收益</span>
          <strong>{formatPct(summary.avgReturnPct)}</strong>
        </article>
        <article>
          <span>平均胜率</span>
          <strong>{formatPct(summary.avgWinRatePct)}</strong>
        </article>
      </div>
      <DataTable<BacktestRunSummary>
        rowKey="id"
        dataSource={runs}
        locale={{ emptyText: <EmptyPlaceholder title="暂无策略历史" description="提交快速回测后会自动出现在这里。" /> }}
        scroll={{ x: 980 }}
        columns={[
          {
            title: "任务",
            dataIndex: "name",
            render: (_value, run) => <strong>{run.name || `任务 #${run.id}`}</strong>,
          },
          {
            title: "策略",
            dataIndex: "strategies",
            render: (_value, run) => formatBacktestStrategies(run.strategies),
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (_value, run) => <b className={`strategy-status ${run.status}`}>{statusText(run.status)}</b>,
          },
          {
            title: "收益",
            render: (_value, run) => runMetricPct(run, "total_return_pct"),
          },
          {
            title: "胜率",
            render: (_value, run) => runMetricPct(run, "win_rate_pct"),
          },
          {
            title: "创建时间",
            dataIndex: "created_at",
            render: (_value, run) => formatDateTime(run.created_at),
          },
          {
            title: "操作",
            render: (_value, run, index) => (
              <span className="strategy-history-actions">
                <RunDeltaSummary current={run} previous={runs[index + 1]} compact />
                <Button type="default" size="small" onClick={() => onRerun(run)}>重新运行</Button>
              </span>
            ),
          },
        ]}
      />
    </section>
  );
}

export function StrategyBridge({
  tab,
}: {
  tab: Extract<StrategyHubTab, "signals">;
}) {
  if (tab === "signals") {
    return <StrategySignalReplayPanel title="最近信号" />;
  }
  return null;
}

export function PanelTitle({ title }: { title: string }) {
  return (
    <div className="strategy-panel-title">
      <h2>{title}</h2>
    </div>
  );
}

export function visibleTabsForUser(user: AuthUser) {
  return TABS.filter((tab) => {
    if (tab.key === "optimize") return canOptimize(user);
    if (tab.key === "validate") return canValidate(user);
    if (tab.key === "capacity") return isAdmin(user);
    if (tab.key === "factor") return canResearchFactors(user);
    return true;
  });
}

export function executionModelText(value: string): string {
  if (value === "vwap") return "VWAP 近似";
  if (value === "next_open") return "次日开盘";
  if (value === "close_price") return "收盘价成交";
  return "开盘价成交";
}

function statusText(status: string): string {
  if (status === "running") return "运行中";
  if (status === "queued" || status === "pending") return "排队";
  if (status === "completed" || status === "succeeded") return "完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "取消";
  return status || "--";
}

function summarizeRuns(runs: BacktestRunSummary[]) {
  const completedRuns = runs.filter((run) => run.status === "completed" || run.status === "succeeded");
  const avgReturnPct = average(completedRuns.map((run) => run.summary?.total_return_pct));
  const avgWinRatePct = average(completedRuns.map((run) => run.summary?.win_rate_pct));
  return {
    completed: completedRuns.length,
    avgReturnPct,
    avgWinRatePct,
  };
}

function runMetricPct(run: BacktestRunSummary, key: "total_return_pct" | "win_rate_pct"): string {
  if (isFinished(run.status) && runTradeCount(run) === 0) return "无成交";
  const value = run.summary?.[key];
  if (typeof value === "number" && Number.isFinite(value)) return formatPct(value);
  if (run.status === "running" || run.status === "queued" || run.status === "pending") return "完成后显示";
  if (run.status === "failed") return "失败";
  return "暂无结果";
}

function isFinished(status?: string | null): boolean {
  return status === "completed" || status === "succeeded";
}

function runTradeCount(run: BacktestRunSummary): number | null {
  const value = run.summary?.total_trades ?? run.summary?.trade_count;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function runEquityText(run: BacktestRunSummary): string {
  if (typeof run.final_equity === "number" && Number.isFinite(run.final_equity) && run.final_equity > 0) {
    return formatMoney(run.final_equity);
  }
  if (run.status === "running" || run.status === "queued" || run.status === "pending") return "计算中";
  return "--";
}

function average(values: Array<number | null | undefined>): number | undefined {
  const filtered = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!filtered.length) return undefined;
  return filtered.reduce((sum, value) => sum + value, 0) / filtered.length;
}

const TABS: Array<{ key: StrategyHubTab; label: string; hint: string }> = [
  { key: "quick", label: "策略体检", hint: "一键判断能不能用" },
  { key: "history", label: "任务记录", hint: "看进度和结果" },
  { key: "signals", label: "最近信号", hint: "看入选股票和原因" },
  { key: "optimize", label: "专家：参数", hint: "研究员调参" },
  { key: "validate", label: "专家：验证", hint: "防过拟合" },
  { key: "compare", label: "策略对比", hint: "选更稳的策略" },
  { key: "factor", label: "因子实验室", hint: "挖掘和验证新因子" },
  { key: "capacity", label: "管理员：ML", hint: "在线学习和容量" },
];

function RunProgress({ run }: { run: BacktestRunSummary }) {
  if (!(run.status === "running" || run.status === "queued" || run.status === "pending")) return null;
  const pct = Math.max(0, Math.min(100, Number(run.progress_pct ?? run.progress ?? 0)));
  const estimate = typeof run.estimated_wait_seconds === "number" && run.estimated_wait_seconds > 0
    ? `预计剩余 ${Math.ceil(run.estimated_wait_seconds / 60)} 分钟`
    : "正在等待结果";
  return (
    <div className="strategy-run-progress" aria-label="任务进度">
      <span style={{ width: `${pct}%` }} />
      <small>{pct ? `${pct.toFixed(0)}% · ${estimate}` : estimate}</small>
    </div>
  );
}

function RunDeltaSummary({
  current,
  previous,
  compact = false,
}: {
  current: BacktestRunSummary;
  previous?: BacktestRunSummary;
  compact?: boolean;
}) {
  if (!previous) return compact ? <small>首次记录</small> : null;
  const winDelta = numericDelta(current.summary?.win_rate_pct, previous.summary?.win_rate_pct);
  const drawdownDelta = numericDelta(current.summary?.max_drawdown_pct, previous.summary?.max_drawdown_pct);
  const returnDelta = numericDelta(current.summary?.total_return_pct, previous.summary?.total_return_pct);
  if (!winDelta && !drawdownDelta && !returnDelta) return compact ? <small>暂无对比</small> : null;
  return (
    <div className={compact ? "strategy-run-delta compact" : "strategy-run-delta"}>
      {winDelta ? <span>{deltaText("胜率", winDelta)}</span> : null}
      {drawdownDelta ? <span>{deltaText("回撤", drawdownDelta)}</span> : null}
      {returnDelta ? <span>{deltaText("收益", returnDelta)}</span> : null}
    </div>
  );
}

function numericDelta(current?: number | null, previous?: number | null): number | null {
  if (typeof current !== "number" || typeof previous !== "number") return null;
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return null;
  return current - previous;
}

function deltaText(label: string, delta: number): string {
  const better = delta > 0;
  const arrow = delta === 0 ? "→" : better ? "▲" : "▼";
  return `${label} ${arrow}${Math.abs(delta).toFixed(1)}%`;
}
