import type { CSSProperties } from "react";
import type { LatestLowBuyDataStatus } from "../../types";
import { Button } from "antd";
import { MetricGrid, PanelTitle } from "../workspace-shared/WorkspaceComponents";

const LATEST_DATA_CARD_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: 216,
};

const LATEST_DATA_FIELDS_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
};

const LATEST_DATA_BUTTON_STYLE: CSSProperties = {
  width: "fit-content",
  marginTop: "auto",
};

const LATEST_DATA_WARNING_STYLE: CSSProperties = {
  color: "var(--warning)",
};

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
    <div className={`panel ${view.tone}`} style={LATEST_DATA_CARD_STYLE}>
      <PanelTitle title="每日最新数据" />
      <div style={LATEST_DATA_FIELDS_STYLE}>
        <div className="latest-data-headline">
          <strong>{view.title}</strong>
          <span>{view.description}</span>
        </div>
        <MetricGrid
          className="compact"
          items={[
            { label: "目标交易日", value: status?.expected_trade_date || "--", tone: view.tone },
            { label: "本地最新", value: status?.local_latest_trade_date || "--", tone: stalenessTone(status?.local_staleness_trade_days) },
            { label: "已发布交易日", value: status?.published_trade_date || "--", tone: view.tone },
            { label: "发布滞后", value: stalenessText(status?.staleness_trade_days), tone: stalenessTone(status?.staleness_trade_days) },
            { label: "日线数量", value: dailyCountText(status), tone: view.tone },
            { label: "待补策略", value: `${status?.missing_strategies?.length ?? 0} 个`, tone: view.tone },
          ]}
        />
        {(status?.local_staleness_trade_days ?? 0) > 0 ? (
          <p className="hint" style={LATEST_DATA_WARNING_STYLE}>
            本地日线停留在 {status?.local_latest_trade_date || "--"}，距目标交易日 {status?.calendar_expected_trade_date || status?.expected_trade_date || "--"} 落后 {status?.local_staleness_trade_days} 个交易日。
          </p>
        ) : null}
        {status?.missing_strategies?.length ? (
          <p className="hint">待补策略：{status.missing_strategies.join("、")}</p>
        ) : null}
        <p className="hint">更新时间：{status?.updated_at || "--"}</p>
      </div>
      <Button type="primary" style={LATEST_DATA_BUTTON_STYLE} onClick={() => void onRefresh()} loading={loading} disabled={Boolean(adminTokenError)}>
        {loading ? "补全中..." : "一键补全当日最新数据"}
      </Button>
      {adminTokenError ? <p className="hint" style={LATEST_DATA_WARNING_STYLE}>需要填写管理令牌后才能手动补全。</p> : null}
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
  if ((status.local_staleness_trade_days ?? 0) > 0) {
    return { title: "本地数据已滞后", description: "目标交易日已有变化，当前推荐只应作为历史复盘查看。", tone: "warn" };
  }
  if ((status.daily_bar_count ?? 0) < (status.min_daily_bar_count ?? 4500)) {
    return { title: "日线数据待补齐", description: "收盘后兜底任务会自动拉取，也可手动触发补全。", tone: "warn" };
  }
  if (status.missing_strategies?.length) {
    return { title: "策略快照待补齐", description: "日线已满足要求，仍需重建部分策略快照。", tone: "warn" };
  }
  return { title: "等待最新数据发布", description: "数据检查通过后会自动发布给前端使用。", tone: "neutral" };
}

function stalenessText(value: number | undefined): string {
  if (!value || value <= 0) return "0 个交易日";
  return `${value} 个交易日`;
}

function stalenessTone(value: number | undefined): "up" | "warn" | "down" | "neutral" {
  if (!value || value <= 0) return "up";
  return value >= 3 ? "down" : "warn";
}

function dailyCountText(status: LatestLowBuyDataStatus | null): string {
  if (!status) return "--";
  const count = status.daily_bar_count ?? 0;
  const min = status.min_daily_bar_count ?? 4500;
  return `${count}/${min}`;
}
