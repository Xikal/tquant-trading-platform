export function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export function readArray<T = Record<string, unknown>>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

export function text(value: unknown, fallback = "--"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "object") return fallback;
  return displayText(String(value));
}

export function numberText(value: unknown, fallback = "--"): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) : fallback;
}

export function pctText(value: unknown, fallback = "--"): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(0)}%` : fallback;
}

export function pickFirst(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    if (record[key] !== null && record[key] !== undefined && record[key] !== "") return record[key];
  }
  return undefined;
}

export function nested(record: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((current, key) => readRecord(current)[key], record);
}

function displayText(value: string): string {
  const labels: Record<string, string> = {
    ok: "正常",
    empty: "空",
    idle: "空闲",
    pending: "等待中",
    queued: "排队中",
    running: "运行中",
    finished: "已完成",
    failed: "失败",
    deleted: "已删除",
    shadow: "观察",
    "read-only": "观察",
    "display-only": "展示",
    live: "运行",
    enabled: "已启用",
    disabled: "已关闭",
    open: "已连接",
    closed: "已关闭",
    error: "异常",
    true: "是",
    false: "否",
    buy: "买入",
    sell: "卖出",
    watch: "观察",
    block: "阻断",
  };
  return labels[value] ?? value;
}
