import type { ReactNode } from "react";
import { Button } from "antd";
import {
  DateField as SharedDateField,
  SelectField as SharedSelectField,
  SliderField as SharedSliderField,
  TextField as SharedTextField,
} from "../../components/shared/FormFields";
import type {
  BacktestAttributionResponse,
  BacktestCompareResponse,
  BacktestParamValue,
} from "../../api/backtests";
import {
  formatInteger,
  formatMoneyOrPct,
  formatNumber,
  formatPct,
  type BacktestStrategyOption,
} from "./backtestDisplay";

export function PanelTitle({ title, meta, action }: { title: string; meta?: string; action?: ReactNode }) {
  return (
    <div className="backtest-research-title">
      <h3>{title}</h3>
      {meta ? <span>{meta}</span> : null}
      {action}
    </div>
  );
}

export function TextField({
  label,
  value,
  hint,
  type = "text",
  onChange,
}: {
  label: string;
  value: string;
  hint?: string;
  type?: string;
  onChange: (value: string) => void;
}) {
  return <SharedTextField label={label} value={value} hint={hint} type={type} onChange={(event) => onChange(event.target.value)} />;
}

export function DateField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <SharedDateField label={label} value={value} onChange={(event) => onChange(event.target.value)} />;
}

export function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: ReadonlyArray<readonly [string, string]>;
  onChange: (value: string) => void;
}) {
  return (
    <SharedSelectField
      label={label}
      value={value}
      options={options.map(([optionValue, optionLabel]) => ({ value: optionValue, label: optionLabel }))}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function SliderParamField({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <SharedSliderField
      label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      suffix={suffix}
      onValueChange={(next) => onChange(Number(next))}
    />
  );
}

export function Metric({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="backtest-empty">{text}</div>;
}

export function formatParams(params?: Record<string, BacktestParamValue> | null): string {
  if (!params || !Object.keys(params).length) return "--";
  return Object.entries(params).map(([key, value]) => `${key}=${String(value)}`).join(", ");
}

export function formatProgress(progress: number | null | undefined, status: string): string {
  if (status === "completed" || status === "succeeded") return "100%";
  if (typeof progress !== "number" || !Number.isFinite(progress)) return status === "running" ? "运行中" : "--";
  return `${Math.round(progress)}%`;
}

export function isCancellable(status: string): boolean {
  return status === "pending" || status === "queued" || status === "running";
}

export function truthyFlag(value: unknown): boolean {
  return value === true || value === 1;
}

export function parseRunIdsLoose(value: string): number[] {
  return value
    .split(/[,\s]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
}

export function formatMoneyCompact(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "--";
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toFixed(0);
}

export function capacityTone(status: string): string {
  if (status === "可承载") return "up";
  if (status === "谨慎") return "pbo-medium";
  if (status === "过载") return "down";
  return "";
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err || "操作失败");
}

export function sortCompareItems(items: NonNullable<BacktestCompareResponse["items"]>, sortKey: "return" | "sharpe" | "drawdown") {
  return [...items].sort((a, b) => compareMetric(b, sortKey) - compareMetric(a, sortKey));
}

export function compareMetric(item: NonNullable<BacktestCompareResponse["items"]>[number], sortKey: "return" | "sharpe" | "drawdown") {
  if (sortKey === "sharpe") return Number(item.metrics?.sharpe ?? item.metrics?.sharpe_ratio ?? -Infinity);
  if (sortKey === "drawdown") return -Math.abs(Number(item.metrics?.max_drawdown_pct ?? Infinity));
  return Number(item.metrics?.total_return_pct ?? -Infinity);
}

export function firstNumber(value: string, fallback: number): number {
  const first = Number(String(value || "").split(",")[0]?.trim());
  return Number.isFinite(first) ? first : fallback;
}

export function percentToSlider(value: string, fallbackPct: number): number {
  const parsed = firstNumber(value, fallbackPct / 100);
  return Math.abs(parsed) <= 1 ? parsed * 100 : parsed;
}

export function ratioFromPercent(value: number): string {
  return String(Number((value / 100).toFixed(4)));
}

export function normalizeAttributionRows(group: string, rows: NonNullable<BacktestAttributionResponse["industry"]>) {
  return rows.map((item) => ({
    group,
    label: item.label || item.bucket || "--",
    tradeCount: Number(item.trade_count ?? 0),
    winRate: Number(item.win_rate_pct ?? 0),
    netPnl: item.net_pnl,
    returnValue: Number(item.contribution_pct ?? item.return_pct ?? item.net_pnl ?? 0),
  }));
}

export function TaskList<T extends { id: number; name: string; status: string; progress?: number | null; progress_pct?: number | null; strategy?: string }>({
  items,
  selectedId,
  onSelect,
  onCancel,
  onDelete,
  formatStrategy,
}: {
  items: T[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onCancel: (id: number) => void;
  onDelete: (id: number) => void;
  formatStrategy: (strategy?: string) => string;
}) {
  return (
    <div className="backtest-task-list">
      {items.map((item) => (
        <div className={`backtest-task-row${selectedId === item.id ? " active" : ""}`} key={item.id}>
          <Button type="text" onClick={() => onSelect(item.id)}>
            <strong>{item.name || `任务 #${item.id}`}</strong>
            <span>{formatStrategy(item.strategy)} · {item.status} · {formatProgress(item.progress ?? item.progress_pct, item.status)}</span>
          </Button>
          <Button onClick={() => onCancel(item.id)} disabled={!isCancellable(item.status)}>取消</Button>
          <Button danger type="text" onClick={() => onDelete(item.id)}>删除</Button>
        </div>
      ))}
      {items.length ? null : <Empty text="暂无研究任务。" />}
    </div>
  );
}

export type { BacktestStrategyOption };
