import type { MarketBreadth, SectorRelativeStrengthItem, SectorRelativeStrengthResponse } from "../../types";
import { Card, Col, Flex, Row, Typography } from "antd";
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
          size="small"
          title="市场情绪仪表盘"
          extra={<Typography.Text type="secondary">更新 {shortTime(marketBreadth?.updated_at) || "--"}</Typography.Text>}
          styles={{ body: { display: "flex", flexDirection: "column", gap: 10, padding: 10 } }}
        >
          <Flex gap={8} wrap>
            <InfoPill compact label="情绪温度" value={marketBreadth?.emotion_temperature_text || "--"} tone={emotionTone(marketBreadth?.emotion_temperature_score)} />
            <InfoPill compact label="涨停/跌停" value={`${marketBreadth?.limit_up_count ?? "--"} / ${marketBreadth?.limit_down_count ?? "--"}`} />
            <InfoPill compact label="炸板率" value={formatRatioPct(marketBreadth?.broken_board_ratio)} tone={(marketBreadth?.broken_board_ratio ?? 0) > 0.25 ? "down" : "neutral"} />
            <InfoPill compact label="连板高度" value={String(marketBreadth?.board_height || "--")} />
            <InfoPill compact label="上涨比例" value={formatRatioPct(marketBreadth?.stock_up_ratio)} />
            <InfoPill compact label="热点行业" value={(marketBreadth?.hot_industries ?? []).slice(0, 3).join(" / ") || "--"} />
            <InfoPill compact label="数据状态" value={marketBreadth?.data_quality_text || "--"} tone={marketBreadth?.emotion_ready ? "up" : "warn"} />
          </Flex>
          <BoardDistribution items={buildBoardDistribution(marketBreadth?.board_height ?? 0)} height={108} />
        </Card>
      </Col>
      <Col xs={24} xl={13}>
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
      </Col>
    </Row>
  );
}

function BoardDistribution({ items, height }: { items: Array<{ label: string; height: number }>; height: number }) {
  return (
    <Flex align="flex-end" gap={6} style={{ height, padding: "0 6px 8px" }}>
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
