import { Card, Flex, Typography } from "antd";
import type { IntradayMarketPulse, MarketBreadth } from "../../types";
import { InfoPill } from "../workspace-shared/WorkspaceComponents";
import { formatPct, shortTime } from "../workspace-shared/workspaceFormatters";

export function MarketEmotionDashboard({
  marketBreadth,
  marketPulse,
}: {
  marketBreadth: MarketBreadth | null;
  marketPulse?: IntradayMarketPulse | null;
}) {
  return (
    <Card
      size="small"
      title="市场情绪仪表盘"
      extra={<Typography.Text type="secondary">更新 {shortTime(marketBreadth?.updated_at) || "--"}</Typography.Text>}
      styles={{ body: { display: "flex", flexDirection: "column", gap: 10, padding: 10 } }}
    >
      <Flex gap={8} wrap>
        <InfoPill compact label="情绪温度" value={marketBreadth?.emotion_temperature_text || "--"} tone={emotionTone(marketBreadth?.emotion_temperature_score)} />
        <InfoPill compact label="Pulse状态" value={marketPulse?.data_quality_text || "--"} tone={pulseQualityTone(marketPulse?.data_quality)} />
        <InfoPill compact label="龙头强度" value={marketPulse?.leader_strength_text || "--"} />
        <InfoPill compact label="涨停/跌停" value={`${marketBreadth?.limit_up_count ?? "--"} / ${marketBreadth?.limit_down_count ?? "--"}`} />
        <InfoPill compact label="炸板率" value={formatRatioPct(marketBreadth?.broken_board_ratio)} tone={(marketBreadth?.broken_board_ratio ?? 0) > 0.25 ? "down" : "neutral"} />
        <InfoPill compact label="连板高度" value={String(marketBreadth?.board_height || "--")} />
        <InfoPill compact label="上涨比例" value={formatRatioPct(marketBreadth?.stock_up_ratio)} />
        <InfoPill compact label="热点行业" value={(marketBreadth?.hot_industries ?? []).slice(0, 3).join(" / ") || "--"} />
        <InfoPill compact label="数据状态" value={marketBreadth?.data_quality_text || "--"} tone={marketBreadth?.emotion_ready ? "up" : "warn"} />
      </Flex>
      {marketBreadth?.autofill_details?.length ? (
        <Typography.Text type="secondary" style={{ fontSize: 11, lineHeight: 1.45 }}>
          自动补全：{marketBreadth.autofill_details.map((item) => item.detail || item.source).join("；")}
        </Typography.Text>
      ) : null}
      <BoardDistribution items={buildBoardDistribution(marketBreadth?.board_height ?? 0)} height={108} />
    </Card>
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

function pulseQualityTone(quality?: string): "up" | "warn" | "down" | "neutral" {
  if (quality === "fresh") return "up";
  if (quality === "partial" || quality === "stale") return "warn";
  if (quality === "unavailable") return "down";
  return "neutral";
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
