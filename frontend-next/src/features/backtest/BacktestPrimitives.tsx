import { For, Show, type JSX } from "solid-js";
import { Icon as SharedIcon } from "../../shared/ui/Icon";
import { StatusBadge } from "../../shared/ui/StatusBadge";
import { text } from "../shared/dataAccess";
import { exitKind, pct, toneClass } from "./backtestFormatters";

export type ChartRange = "1M" | "3M" | "6M" | "ALL";

export function Icon(props: { name: string }) {
  return <SharedIcon name={props.name} class="backtest-icon" />;
}

export function PanelHead(props: { title: string; icon?: string; badge?: string; action?: JSX.Element }) {
  return (
    <div class="backtest-panel-head">
      <h2>{props.icon ? <Icon name={props.icon} /> : null}{props.title}</h2>
      <div>
        <Show when={props.badge}><span>{props.badge}</span></Show>
        {props.action}
      </div>
    </div>
  );
}

export function Field(props: { label: string; value: string; wide?: boolean }) {
  return (
    <label class={props.wide ? "wide" : ""}>
      <span>{props.label}</span>
      <input value={props.value} onInput={() => undefined} />
    </label>
  );
}

export function Badge(props: { children: JSX.Element; tone?: string }) {
  return <StatusBadge class={`backtest-badge tone-${props.tone ?? "slate"}`}>{props.children}</StatusBadge>;
}

export function InfoBox(props: { tone: "amber" | "blue" | "green"; title: string; desc: string; meta: string }) {
  return (
    <div class={`backtest-info-box tone-${props.tone}`}>
      <Icon name={props.tone === "blue" ? "compass" : "alert"} />
      <div><strong>{props.title}</strong><span>{props.desc}</span><em>{props.meta}</em></div>
    </div>
  );
}

export function MetricTable(props: { totalReturn: unknown; maxDrawdown: unknown; winRate: unknown; tradesCount: number; profitFactor: unknown }) {
  const rows = [
    ["总收益", pct(props.totalReturn), "最大回撤", pct(props.maxDrawdown), "down"],
    ["基准", "0.00%", "胜率", pct(props.winRate), "up"],
    ["Alpha", pct(props.totalReturn), "交易数", String(props.tradesCount || "--"), "neutral"],
    ["Sharpe", "--", "利润因子", text(props.profitFactor), "neutral"],
    ["Sortino", "--", "队列深度", "0", "neutral"],
    ["Calmar", "--", "等待时间", "--", "neutral"],
    ["IR", "--", "风控", "+30% / 8仓", "neutral"],
  ];
  return (
    <div class="backtest-metric-table">
      <table>
        <thead><tr><th>核心指标</th><th>数值</th><th>核心指标</th><th>数值</th></tr></thead>
        <tbody>
          <For each={rows}>
            {(row) => <tr><td>{row[0]}</td><td class={toneClass(row[1])}>{row[1]}</td><td>{row[2]}</td><td class={row[4] === "up" ? "is-up" : row[4] === "down" ? "is-down" : ""}>{row[3]}</td></tr>}
          </For>
        </tbody>
      </table>
    </div>
  );
}

export function ChartRangeControl(props: { value: ChartRange; onChange: (range: ChartRange) => void }) {
  const ranges: ChartRange[] = ["1M", "3M", "6M", "ALL"];
  return (
    <div class="backtest-chart-range">
      <For each={ranges}>
        {(range) => <button type="button" class={props.value === range ? "is-active" : ""} onClick={() => props.onChange(range)}>{range === "ALL" ? "全部" : range.replace("M", "月")}</button>}
      </For>
    </div>
  );
}

export function ChartMetric(props: { label: string; value: string; tone?: string }) {
  return <div class={`backtest-chart-metric tone-${props.tone ?? "slate"}`}><span>{props.label}</span><strong>{props.value}</strong></div>;
}

export function MetricCompact(props: { label: string; value: string; tone?: string }) {
  return <div class={`backtest-compact-metric tone-${props.tone ?? "slate"}`}><span>{props.label}</span><strong>{props.value}</strong></div>;
}

export function StepCard(props: { step: string; title: string; desc: string; active?: boolean }) {
  return <div class={props.active ? "is-active" : ""}><span>{props.step}</span><strong>{props.title}</strong><p>{props.desc}</p></div>;
}

export function StatusDot(props: { status: "running" | "completed" | "other" }) {
  const label = props.status === "completed" ? "已完成" : props.status === "running" ? "运行中" : "已终止";
  return <span class={`backtest-status-dot is-${props.status}`}><i />{label}</span>;
}

export function ExitBadge(props: { value: string }) {
  const kind = exitKind(props.value);
  const label = kind === "take_profit" ? "止盈 (TP)" : kind === "stop_loss" ? "止损 (SL)" : kind === "max_holding_days" ? "期满退出 (HD)" : props.value;
  return <StatusBadge class={`backtest-exit-badge is-${kind}`}>{label}</StatusBadge>;
}
