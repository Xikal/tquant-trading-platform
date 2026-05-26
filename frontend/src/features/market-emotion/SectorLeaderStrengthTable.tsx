import { Card, Typography } from "antd";
import type { SectorRelativeStrengthItem, SectorRelativeStrengthResponse } from "../../types";
import { DataTable } from "../../ui/table/DataTable";
import { EmptyState } from "../workspace-shared/WorkspaceComponents";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function SectorLeaderStrengthTable({
  sectorRelativeStrength,
}: {
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
}) {
  const leaders = sectorRelativeStrength?.items ?? [];
  return (
    <Card
      size="small"
      title="实时龙头强度排行"
      extra={<Typography.Text type="secondary">{sectorRelativeStrength?.trade_date || "--"}</Typography.Text>}
      styles={{ body: { padding: 10 } }}
    >
      <DataTable<SectorRelativeStrengthItem>
        rowKey={(item) => `${item.sector_name}-${item.symbol}`}
        dataSource={leaders.slice(0, 30)}
        locale={{ emptyText: <EmptyState text="暂无板块龙头强度数据，等待市场快照刷新。" /> }}
        scroll={{ y: 430 }}
        columns={[
          {
            title: "标的",
            width: "28%",
            render: (_value, item) => <strong>{item.name} <small>{item.symbol}</small></strong>,
          },
          {
            title: "板块",
            width: "27%",
            render: (_value, item) => `${item.sector_name} #${item.rank}`,
          },
          {
            title: "涨跌",
            dataIndex: "change_pct",
            align: "right",
            render: (value) => formatPct(value),
          },
          {
            title: "量比",
            dataIndex: "volume_ratio",
            align: "right",
            render: (value) => value.toFixed(2),
          },
          {
            title: "龙头分",
            dataIndex: "leader_score",
            align: "right",
            render: (value) => <b>{value.toFixed(0)}</b>,
          },
        ]}
      />
    </Card>
  );
}
