import { memo } from "react";
import { Card, Space, Typography } from "antd";
import type {
  IntradayMarketPulse,
  LowBuyPriorityBoardResult,
  MarketBreadth,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
} from "../../types";
import { VirtualCardList } from "../../ui/list/VirtualCardList";
import { Callout, EmptyState, InfoPill, MetricGrid, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import type { StockCardView } from "../workspace-shared/workspaceTypes";
import { buildMonitorMetrics } from "./MonitorPage.helpers";
import { SectorEtfOpportunityCard } from "./MonitorPage.panels";

export const MonitorMarketSummaryPanel = memo(function MonitorMarketSummaryPanel({
  marketBreadth,
  marketPulse,
  priorityBoard,
  priorityCards,
  runtime,
  sectorEtfT0,
  watchCards,
}: {
  marketBreadth: MarketBreadth | null;
  marketPulse: IntradayMarketPulse | null;
  priorityBoard: LowBuyPriorityBoardResult | null;
  priorityCards: StockCardView[];
  runtime: RuntimeStatus | null;
  sectorEtfT0: SectorEtfT0Response | null;
  watchCards: StockCardView[];
}) {
  const metrics = buildMonitorMetrics({ priorityBoard, priorityCards, watchCards });
  return (
    <Card
      className="monitor-shared-summary"
      size="small"
      title="市场环境摘要"
      extra={<Typography.Text type="secondary">{runtime?.database_backend ?? "runtime"}</Typography.Text>}
    >
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <MetricGrid items={metrics} compact />
        <Space wrap size={[8, 8]}>
          <InfoPill compact label="市场宽度" value={marketBreadth?.state_text ?? "--"} />
          <InfoPill compact label="盘中脉冲" value={marketPulse?.pulse_text || marketPulse?.pulse_level || "--"} />
          <InfoPill compact label="ETF T0" value={`${sectorEtfT0?.opportunities?.length ?? 0} 个机会`} />
        </Space>
      </Space>
    </Card>
  );
});

export const MonitorEtfT0Panel = memo(function MonitorEtfT0Panel({
  pairedHedge,
  sectorEtfT0,
}: {
  pairedHedge: PairedHedgeResearchResponse | null;
  sectorEtfT0: SectorEtfT0Response | null;
}) {
  return (
    <Card className="monitor-market-card" size="small">
      <PanelTitle title="ETF T0 与对冲研究" />
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        {pairedHedge?.disclaimer ? <Callout title={pairedHedge.disclaimer} tone="down" compact /> : null}
        <VirtualCardList
          items={sectorEtfT0?.opportunities ?? []}
          empty={<EmptyState text="暂无 ETF 做T替代信号。只有板块低吸/热点信号明确时才展示。" />}
          estimateSize={155}
          maxHeight={420}
          className="monitor-secondary-panel__list"
          getItemKey={(item) => `${item.etf_symbol}-${item.source_signal_symbol}`}
          renderItem={(item) => <SectorEtfOpportunityCard item={item} />}
        />
        {sectorEtfT0?.notes?.length ? <p className="hint">{sectorEtfT0.notes[0]}</p> : null}
      </Space>
    </Card>
  );
});
