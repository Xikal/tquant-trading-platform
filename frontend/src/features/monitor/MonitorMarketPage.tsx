import { memo } from "react";
import { Card, Grid, Space } from "antd";
import { InstrumentSyncProgress } from "./InstrumentSyncProgress";
import { MarketStateGatePanel } from "./MarketStateGatePanel";
import {
  HourlyAllMarketPulse,
  MarketBreadthStrip,
  MonitorReviewPanel,
} from "./MonitorPage.panels";
import { MonitorEtfT0Panel, MonitorMarketSummaryPanel } from "./MonitorSharedPanels";
import { SectorLeaderGatePanel } from "./SectorLeaderGatePanel";
import { KeyLevelPanel } from "../key-levels/KeyLevelPanel";
import { useMarketKeyLevels } from "../key-levels/queries";
import { Callout, InfoPill, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import { dataQualityTone } from "./MonitorPage.helpers";
import { buildMonitorMarketModel } from "./monitorPageModel";
import type {
  InstrumentSyncStatus,
  IntradayMarketPulse,
  LowBuyPriorityBoardResult,
  MarketBreadth,
  MarketHourlySnapshotHistoryItem,
  MarketReviewReport,
  MarketReviewStatus,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  SectorRelativeStrengthResponse,
} from "../../types";
import type { StockCardView } from "../workspace-shared/workspaceTypes";

export interface MonitorMarketPageProps {
  hourlySnapshotHistory: MarketHourlySnapshotHistoryItem[];
  instrumentSyncStatus: InstrumentSyncStatus | null;
  loading: string;
  marketBreadth: MarketBreadth | null;
  marketPulse: IntradayMarketPulse | null;
  pairedHedge: PairedHedgeResearchResponse | null;
  priorityBoard: LowBuyPriorityBoardResult | null;
  priorityCards: StockCardView[];
  reviewReports: MarketReviewReport[];
  reviewStatus: MarketReviewStatus | null;
  runtime: RuntimeStatus | null;
  sectorEtfT0: SectorEtfT0Response | null;
  sectorRelativeStrength?: SectorRelativeStrengthResponse | null;
  watchCards: StockCardView[];
}

export const MonitorMarketPage = memo(function MonitorMarketPage({
  hourlySnapshotHistory,
  instrumentSyncStatus,
  loading,
  marketBreadth,
  marketPulse,
  pairedHedge,
  priorityBoard,
  priorityCards,
  reviewReports,
  reviewStatus,
  runtime,
  sectorEtfT0,
  sectorRelativeStrength = null,
  watchCards,
}: MonitorMarketPageProps) {
  const screens = Grid.useBreakpoint();
  const wideLayout = screens.xl ?? true;
  const marketKeyLevels = useMarketKeyLevels();
  const model = buildMonitorMarketModel({ marketBreadth, marketPulse, sectorEtfT0 });

  return (
    <section className={`monitor-market-page ${wideLayout ? "monitor-market-page--wide" : "monitor-market-page--stack"}`}>
      <div className="panel monitor-market-gate">
        <PanelTitle title="市场总闸 / 数据质量" />
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <MarketStateGatePanel board={priorityBoard} defaultOpen />
          <Space wrap size={[8, 8]}>
            <InfoPill compact label="市场状态" value={priorityBoard?.market_state_text ?? marketBreadth?.state_text ?? "--"} />
            <InfoPill compact label="数据状态" value={priorityBoard?.data_quality_text ?? "--"} tone={dataQualityTone(priorityBoard?.data_quality)} />
            <InfoPill compact label="市场宽度" value={marketBreadth?.data_quality_text ?? "--"} tone={dataQualityTone(marketBreadth?.data_quality)} />
            <InfoPill compact label="盘中脉冲" value={marketPulse?.data_quality_text ?? model.pulseQuality} tone={dataQualityTone(marketPulse?.data_quality)} />
            <InfoPill compact label="ETF 机会" value={`${model.etfOpportunityCount} 个`} tone={model.etfOpportunityCount ? "up" : "neutral"} />
          </Space>
          {!model.hasMarketContext ? <Callout title="市场环境数据暂未形成" detail="保留页面结构和空态，等待监控 BFF 或后台快照刷新。" tone="warn" compact /> : null}
        </Space>
      </div>

      <div className="monitor-market-main">
        <Card className="monitor-market-card" size="small">
          <PanelTitle title="市场宽度与日内脉冲" />
          <MarketBreadthStrip marketBreadth={marketBreadth} />
          <HourlyAllMarketPulse marketBreadth={marketBreadth} history={hourlySnapshotHistory} />
          <KeyLevelPanel title="大盘关键位观察" result={marketKeyLevels.data} loading={marketKeyLevels.isFetching} compact={!wideLayout} />
        </Card>

        <Card className="monitor-market-card" size="small">
          <PanelTitle title="板块轮动与龙头确认" />
          <SectorLeaderGatePanel sectorRelativeStrength={sectorRelativeStrength} defaultOpen />
        </Card>

        <MonitorEtfT0Panel pairedHedge={pairedHedge} sectorEtfT0={sectorEtfT0} />

        <MonitorReviewPanel reviewStatus={reviewStatus} reviewReports={reviewReports} marketPulse={marketPulse} />

        <Card className="monitor-market-card" size="small">
          <PanelTitle title="运行时 / 同步状态" />
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <MonitorMarketSummaryPanel
              marketBreadth={marketBreadth}
              marketPulse={marketPulse}
              priorityBoard={priorityBoard}
              priorityCards={priorityCards}
              runtime={runtime}
              sectorEtfT0={sectorEtfT0}
              watchCards={watchCards}
            />
            <InstrumentSyncProgress status={instrumentSyncStatus} loading={loading === "sync"} />
          </Space>
        </Card>
      </div>
    </section>
  );
});
