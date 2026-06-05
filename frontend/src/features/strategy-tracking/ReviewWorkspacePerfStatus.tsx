import { Tag } from "antd";
import type { ReviewWorkspaceResponse } from "../../types";

export function ReviewWorkspacePerfStatus({ data, professional }: { data?: ReviewWorkspaceResponse; professional: boolean }) {
  if (!professional || !data) return null;
  return (
    <div className="strategy-review-perf-status">
      <Tag>总耗时 {formatMs(data.elapsed_ms)}</Tag>
      <Tag>缓存 {cacheText(data.cache_status)}</Tag>
      {(data.sources ?? []).map((source) => (
        <Tag key={source.source}>
          {sourceName(source.source)} {source.status} {formatMs(source.elapsed_ms)}
        </Tag>
      ))}
    </div>
  );
}

function formatMs(value: number | null | undefined) {
  return `${Math.round(Number(value || 0))}ms`;
}

function cacheText(value: string) {
  if (value === "fresh") return "命中";
  if (value === "stale") return "旧快照";
  return "未命中";
}

function sourceName(value: string) {
  if (value === "review_pool") return "复盘池";
  if (value === "trade_journal") return "纪律日志";
  if (value === "relative_strength") return "抗跌事实";
  return value;
}
