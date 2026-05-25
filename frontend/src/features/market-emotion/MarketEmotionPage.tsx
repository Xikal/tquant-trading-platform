import type { MarketBreadth, SectorRelativeStrengthItem, SectorRelativeStrengthResponse } from "../../types";
import { Card, Col, Flex, Row, Space, Typography } from "antd";
import { EmptyState, InfoPill } from "../workspace-shared/WorkspaceComponents";
import { formatPct, shortTime } from "../workspace-shared/workspaceFormatters";
import { DataTable } from "../../ui/table/DataTable";

export interface MarketEmotionPageProps {
  marketBreadth: MarketBreadth | null;
  sectorRelativeStrength: SectorRelativeStrengthResponse | null;
}

export function MarketEmotionPage({ marketBreadth, sectorRelativeStrength }: MarketEmotionPageProps) {
  const leaders = sectorRelativeStrength?.items ?? [];
  return (
    <Row gutter={[12, 12]}>
      <Col xs={24} xl={11}>
        <Card
          title="市场情绪仪表盘"
          extra={<Typography.Text type="secondary">更新 {shortTime(marketBreadth?.updated_at) || "--"}</Typography.Text>}
          styles={{ body: { display: "flex", flexDirection: "column", gap: 16 } }}
        >
          <Flex gap={8} wrap>
            <InfoPill label="情绪温度" value={marketBreadth?.emotion_temperature_text || "--"} tone={emotionTone(marketBreadth?.emotion_temperature_score)} />
            <InfoPill label="涨停/跌停" value={`${marketBreadth?.limit_up_count ?? "--"} / ${marketBreadth?.limit_down_count ?? "--"}`} />
            <InfoPill label="炸板率" value={formatRatioPct(marketBreadth?.broken_board_ratio)} tone={(marketBreadth?.broken_board_ratio ?? 0) > 0.25 ? "down" : "neutral"} />
            <InfoPill label="连板高度" value={String(marketBreadth?.board_height || "--")} />
            <InfoPill label="上涨比例" value={formatRatioPct(marketBreadth?.stock_up_ratio)} />
            <InfoPill label="热点行业" value={(marketBreadth?.hot_industries ?? []).slice(0, 3).join(" / ") || "--"} />
            <InfoPill label="数据状态" value={marketBreadth?.data_quality_text || "--"} tone={marketBreadth?.emotion_ready ? "up" : "warn"} />
          </Flex>
          <Space direction="vertical" size={12}>
            <BoardDistribution items={buildBoardDistribution(marketBreadth?.board_height ?? 0)} height={150} />
            <Typography.Text type="secondary">
              连板高度越高，说明短线情绪越活跃；炸板率过高时，低吸和做 T 都应降仓。
            </Typography.Text>
          </Space>
        </Card>
      </Col>
      <Col xs={24} xl={13}>
        <Card
          title="实时龙头强度排行"
          extra={<Typography.Text type="secondary">{sectorRelativeStrength?.trade_date || "--"}</Typography.Text>}
        >
          <DataTable<SectorRelativeStrengthItem>
            rowKey={(item) => `${item.sector_name}-${item.symbol}`}
            dataSource={leaders.slice(0, 30)}
            locale={{ emptyText: <EmptyState text="暂无板块龙头强度数据，等待市场快照刷新。" /> }}
            scroll={{ x: 760, y: 520 }}
            columns={[
              {
                title: "标的",
                render: (_value, item) => <strong>{item.name} <small>{item.symbol}</small></strong>,
              },
              {
                title: "板块",
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
      </Col>
    </Row>
  );
}

function BoardDistribution({ items, height }: { items: Array<{ label: string; height: number }>; height: number }) {
  return (
    <Flex align="flex-end" gap={8} style={{ height, padding: "0 8px 24px" }}>
      {items.map((item) => (
        <Flex align="center" justify="flex-end" vertical key={item.label} style={{ flex: 1, height: "100%" }}>
          <div
            style={{
              background: "linear-gradient(180deg, #ef4444, #f59e0b)",
              borderRadius: "8px 8px 3px 3px",
              height: `${item.height}%`,
              minHeight: 12,
              width: "100%",
            }}
          />
          <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 4 }}>
            {item.label}
          </Typography.Text>
        </Flex>
      ))}
    </Flex>
  );
}

function emotionTone(score?: number): "up" | "warn" | "down" | "neutral" {
  if (typeof score !== "number") return "neutral";
  if (score >= 65) return "up";
  if (score >= 45) return "warn";
  return "down";
}

function formatRatioPct(value?: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  const normalized = Math.abs(value) <= 1 ? value * 100 : value;
  return `${normalized.toFixed(0)}%`;
}

function buildBoardDistribution(boardHeight: number): Array<{ label: string; height: number }> {
  const current = Math.max(0, Math.min(6, Math.round(boardHeight || 0)));
  return ["1板", "2板", "3板", "4板", "5+"].map((label, index) => ({
    label,
    height: Math.max(14, index + 1 <= current ? 34 + index * 13 : 14),
  }));
}
