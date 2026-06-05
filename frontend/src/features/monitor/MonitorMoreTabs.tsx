import { Card, Tabs, Typography } from "antd";
import type {
  IntradayMarketPulse,
  MarketBreadth,
  MarketHourlySnapshotHistoryItem,
  MarketReviewReport,
  MarketReviewStatus,
  PairedHedgeResearchResponse,
  RuntimeStatus,
  SectorEtfT0Response,
  InstrumentSyncStatus,
} from "../../types";
import { VirtualCardList } from "../../ui/list/VirtualCardList";
import { Callout, EmptyState, MetricGrid, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import { buildMonitorMetrics } from "./MonitorPage.helpers";
import type { StockCardView } from "../workspace-shared/workspaceTypes";
import { HourlyAllMarketPulse, MarketBreadthStrip, MonitorReviewPanel, SectorEtfOpportunityCard } from "./MonitorPage.panels";
import { InstrumentSyncProgress } from "./InstrumentSyncProgress";
import type { MonitorMoreTab } from "../../stores/workspaceMonitorStore";

export function MonitorMoreTabs({
  activeKey,
  instrumentSyncStatus,
  loading,
  marketBreadth,
  marketPulse,
  hourlySnapshotHistory,
  pairedHedge,
  priorityBoard,
  priorityCards,
  reviewReports,
  reviewStatus,
  runtime,
  sectorEtfT0,
  watchCards,
  onChange,
}: {
  activeKey: MonitorMoreTab;
  instrumentSyncStatus: InstrumentSyncStatus | null;
  loading: string;
  marketBreadth: MarketBreadth | null;
  marketPulse: IntradayMarketPulse | null;
  hourlySnapshotHistory: MarketHourlySnapshotHistoryItem[];
  pairedHedge: PairedHedgeResearchResponse | null;
  priorityBoard: Parameters<typeof buildMonitorMetrics>[0]["priorityBoard"];
  priorityCards: StockCardView[];
  reviewReports: MarketReviewReport[];
  reviewStatus: MarketReviewStatus | null;
  runtime: RuntimeStatus | null;
  sectorEtfT0: SectorEtfT0Response | null;
  watchCards: StockCardView[];
  onChange: (key: MonitorMoreTab) => void;
}) {
  const metrics = buildMonitorMetrics({ priorityBoard, priorityCards, watchCards });
  return (
    <Card
      className="monitor-secondary-panel"
      size="small"
      extra={<Typography.Text type="secondary">{runtime?.database_backend ?? "runtime"}</Typography.Text>}
    >
      <Tabs
        size="small"
        activeKey={activeKey}
        onChange={(key) => onChange(key as MonitorMoreTab)}
        items={[
          {
            key: "etf",
            label: "ETF 做T替代",
            forceRender: true,
            children: (
              <>
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
              </>
            ),
          },
          {
            key: "review",
            label: "全市场复盘",
            forceRender: true,
            children: <MonitorReviewPanel reviewStatus={reviewStatus} reviewReports={reviewReports} marketPulse={marketPulse} />,
          },
          {
            key: "snapshot",
            label: "小时快照",
            forceRender: true,
            children: (
              <>
                <PanelTitle title="盘面数字摘要" />
                <MetricGrid items={metrics} compact />
                <MarketBreadthStrip marketBreadth={marketBreadth} />
                <HourlyAllMarketPulse marketBreadth={marketBreadth} history={hourlySnapshotHistory} />
                <InstrumentSyncProgress status={instrumentSyncStatus} loading={loading === "sync"} />
              </>
            ),
          },
        ]}
      />
    </Card>
  );
}
