import type { LatestLowBuyDataStatus } from "../../types";
import { InfoPill, PanelTitle } from "./WorkspaceComponents";

export function LatestDataStatusCard({
  status,
  loading,
  adminTokenError,
  onRefresh,
}: {
  status: LatestLowBuyDataStatus | null;
  loading: boolean;
  adminTokenError: string;
  onRefresh: () => void | Promise<void>;
}) {
  const view = latestDataView(status);
  return (
    <div className={`panel setting-card latest-data-card ${view.tone}`}>
      <PanelTitle title="每日最新数据" />
      <div className="setting-fields">
        <div className="latest-data-headline">
          <strong>{view.title}</strong>
          <span>{view.description}</span>
        </div>
        <div className="metric-grid compact">
          <InfoPill label="目标交易日" value={status?.expected_trade_date || "--"} tone={view.tone} />
          <InfoPill label="已发布交易日" value={status?.published_trade_date || "--"} tone={view.tone} />
          <InfoPill label="日线数量" value={dailyCountText(status)} tone={view.tone} />
          <InfoPill label="待补策略" value={`${status?.missing_strategies?.length ?? 0} 个`} tone={view.tone} />
        </div>
        {status?.missing_strategies?.length ? (
          <p className="hint">待补策略：{status.missing_strategies.join("、")}</p>
        ) : null}
        <p className="hint">更新时间：{status?.updated_at || "--"}</p>
      </div>
      <button className="primary" onClick={() => void onRefresh()} disabled={loading || Boolean(adminTokenError)}>
        {loading ? "补全中..." : "一键补全当日最新数据"}
      </button>
      {adminTokenError ? <p className="hint warn">需要填写管理令牌后才能手动补全。</p> : null}
    </div>
  );
}

function latestDataView(status: LatestLowBuyDataStatus | null): {
  title: string;
  description: string;
  tone: "up" | "down" | "neutral" | "warn";
} {
  if (!status) {
    return { title: "暂无数据状态", description: "填写管理令牌并刷新后查看最新数据链路。", tone: "neutral" };
  }
  if (status.published_trade_date && status.published_trade_date === status.expected_trade_date && status.status === "success") {
    return { title: "最新数据已更新", description: "前端榜单和选股宝典可使用已发布交易日数据。", tone: "up" };
  }
  if ((status.daily_bar_count ?? 0) < (status.min_daily_bar_count ?? 4500)) {
    return { title: "日线数据待补齐", description: "收盘后兜底任务会自动拉取，也可手动触发补全。", tone: "warn" };
  }
  if (status.missing_strategies?.length) {
    return { title: "策略快照待补齐", description: "日线已满足要求，仍需重建部分策略快照。", tone: "warn" };
  }
  return { title: "等待最新数据发布", description: "数据检查通过后会自动发布给前端使用。", tone: "neutral" };
}

function dailyCountText(status: LatestLowBuyDataStatus | null): string {
  if (!status) return "--";
  const count = status.daily_bar_count ?? 0;
  const min = status.min_daily_bar_count ?? 4500;
  return `${count}/${min}`;
}
