import { Collapse, Space, Tag, Typography } from "antd";
import type { SectorRelativeStrengthResponse } from "../../types";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { EmptyState, InfoPill } from "../workspace-shared/WorkspaceComponents";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function SectorLeaderGatePanel({
  sectorRelativeStrength,
  defaultOpen = false,
}: {
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
  defaultOpen?: boolean;
}) {
  const items = sectorRelativeStrength?.items ?? [];
  const healthyCount = items.filter((item) => item.leader_status === "healthy").length;
  return (
    <Collapse
      size="small"
      defaultActiveKey={defaultOpen ? ["sector-leader-gate"] : []}
      items={[{
        key: "sector-leader-gate",
        label: `板块/龙头确认 · 健康 ${healthyCount}/${items.length}`,
        children: (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Space wrap size={[6, 6]}>
              <InfoPill compact label="交易日" value={sectorRelativeStrength?.trade_date || "--"} />
              <InfoPill compact label="板块数" value={String(sectorRelativeStrength?.sector_count ?? 0)} />
              <InfoPill compact label="状态" value={healthyCount ? "有健康龙头" : "等待扩散"} tone={healthyCount ? "up" : "warn"} />
            </Space>
            <VirtualGrid
              rowKey={(item) => `${item.sector_name}-${item.symbol}`}
              dataSource={items}
              defaultScrollY={260}
              locale={{ emptyText: <EmptyState text="暂无板块/龙头确认数据" /> }}
              columns={[
                {
                  title: "板块/标的",
                  width: 180,
                  render: (_, item) => (
                    <Space direction="vertical" size={0}>
                      <strong>{item.sector_name}</strong>
                      <Typography.Text type="secondary">{item.symbol} {item.name}</Typography.Text>
                    </Space>
                  ),
                },
                { title: "龙头分", dataIndex: "leader_score", width: 90, align: "right", render: (value) => Number(value || 0).toFixed(1) },
                { title: "扩散", dataIndex: "diffusion_score", width: 90, align: "right", render: (value) => Number(value || 0).toFixed(1) },
                { title: "涨停数", dataIndex: "same_sector_limit_up_count", width: 90, align: "right" },
                { title: "涨幅", dataIndex: "change_pct", width: 90, align: "right", render: (value) => formatPct(value) },
                {
                  title: "门控",
                  dataIndex: "sector_leader_gate_decision",
                  width: 110,
                  render: (value) => {
                    const decision = String(value || "research_only");
                    return <Tag color={decision === "allow" ? "green" : decision === "reduce" ? "orange" : "default"}>{sectorLeaderGateDecisionText(decision)}</Tag>;
                  },
                },
              ]}
              scroll={{ x: 760 }}
            />
            {sectorRelativeStrength?.notes?.[0] ? (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>{sectorRelativeStrength.notes[0]}</Typography.Text>
            ) : null}
          </Space>
        ),
      }]}
    />
  );
}

function sectorLeaderGateDecisionText(value: string): string {
  if (value === "allow") return "允许生产";
  if (value === "reduce") return "降权观察";
  if (value === "block") return "生产阻断";
  if (value === "no_data") return "数据缺失";
  if (value === "research_only") return "仅研究观察";
  return value || "--";
}
