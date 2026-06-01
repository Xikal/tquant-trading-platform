import { memo } from "react";
import { Alert, Button, Card, Col, Collapse, Flex, Row, Space, Tag, Typography } from "antd";
import type {
  IntradayKeyLevelResponse,
  IntradayMarketPulse,
  MarketBreadth,
  MarketHourlySnapshotHistoryItem,
  MarketReviewReport,
  MarketReviewStatus,
  SectorEtfT0Opportunity,
} from "../../types";
import { Callout, EmptyState, InfoPill, PanelTitle, StockCard } from "../workspace-shared/WorkspaceComponents";
import { RitualCloseBag } from "../ritual-ui";
import { formatAmount, formatPct, formatPrice, shortTime } from "../workspace-shared/workspaceFormatters";
import type { StockCardView } from "../workspace-shared/workspaceTypes";
import { dataQualityTone, formatRatioPct, resolveTodayAction } from "./MonitorPage.helpers";

const MONITOR_ETF_CARD_STYLE = {
  display: "grid",
  gap: 6,
  padding: 9,
  border: "1px solid var(--line)",
  borderRadius: 8,
  background: "#fff",
};

const MONITOR_ETF_CARD_HEAD_STYLE = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 8,
};

const MONITOR_ETF_CARD_HEAD_TEXT_STYLE = {
  display: "grid",
  gap: 2,
};

const MONITOR_ETF_CARD_META_STYLE = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  color: "#64748b",
  fontSize: 12,
} as const;

const MONITOR_ETF_CARD_HINT_STYLE = {
  color: "#64748b",
  fontSize: 12,
  lineHeight: 1.4,
};
const MONITOR_BREADTH_ROW_STYLE = {
  marginTop: 10,
};
const MONITOR_HOURLY_CARD_STYLE = {
  marginTop: 10,
  borderColor: "rgba(59, 130, 246, 0.22)",
};
const MONITOR_HOURLY_BODY_STYLE = {
  padding: 8,
};
const MONITOR_HOURLY_NOTE_STYLE = {
  display: "block",
  marginTop: 6,
};
const MONITOR_FULL_WIDTH_STYLE = {
  width: "100%",
};
const MONITOR_ALERT_SPACING_STYLE = {
  marginBottom: 8,
};
const MONITOR_TREND_STRIP_STYLE = {
  display: "grid",
  gap: 6,
  marginTop: 8,
};
const MONITOR_TREND_BAR_GRID_STYLE = {
  display: "grid",
  gap: 6,
  alignItems: "end",
  minHeight: 72,
};
const MONITOR_TREND_BAR_ITEM_STYLE = {
  display: "grid",
  gap: 3,
  alignItems: "end",
  minWidth: 0,
};
const MONITOR_TREND_LABEL_STYLE = {
  fontSize: 12,
  textAlign: "center",
} as const;
const MONITOR_KEY_ALERT_WRAP_STYLE = {
  bottom: 10,
  maxWidth: "min(300px, calc(100vw - 20px))",
  position: "fixed",
  right: 10,
  zIndex: 60,
} as const;
const MONITOR_KEY_ALERT_STYLE = {
  padding: "6px 8px",
};
const MONITOR_KEY_ALERT_TITLE_STYLE = {
  fontSize: 12,
};
const MONITOR_KEY_ALERT_DESC_STYLE = {
  fontSize: 12,
};
const MONITOR_SIDE_RAIL_STYLE = {
  display: "grid",
  gap: 8,
  marginTop: 10,
  paddingTop: 10,
  borderTop: "1px solid rgba(148, 163, 184, 0.18)",
};
const MONITOR_SIDE_GRID_STYLE = {
  display: "grid",
  gap: 6,
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
};
const MONITOR_SIDE_LIST_STYLE = {
  display: "grid",
  gap: 5,
};
const MONITOR_SIDE_ROW_STYLE = {
  display: "grid",
  gap: 3,
  border: "1px solid rgba(148, 163, 184, 0.16)",
  borderRadius: 7,
  background: "#fff",
  padding: "6px 7px",
};
const MONITOR_SIDE_ROW_HEAD_STYLE = {
  display: "flex",
  justifyContent: "space-between",
  gap: 8,
  minWidth: 0,
};
const MONITOR_SIDE_ROW_TEXT_STYLE = {
  fontSize: 12,
  minWidth: 0,
};
const MONITOR_SIDE_ROW_TITLE_STYLE = {
  fontSize: 12,
};
const MONITOR_SIDE_ROW_META_STYLE = {
  color: "#64748b",
  fontSize: 12.5,
  minWidth: 0,
};
const MONITOR_TREND_BAR_DYNAMIC_STYLE = {
  borderRadius: 4,
};
const MONITOR_CARD_LIST_STYLE = {
  display: "grid",
  gap: 6,
};

export const MonitorPriorityStockCard = memo(function MonitorPriorityStockCard({
  stock,
  onAnalyze,
  onSelect,
}: {
  stock: StockCardView;
  onAnalyze: (stock: StockCardView) => void;
  onSelect: (stock: StockCardView) => void;
}) {
  return (
    <div style={MONITOR_CARD_LIST_STYLE}>
      <StockCard
        stock={stock}
        actions={["详情", "分析"]}
        compact
        onAction={(action) => (action === "分析" ? onAnalyze(stock) : onSelect(stock))}
      />
    </div>
  );
});

export const MonitorWatchStockCard = memo(function MonitorWatchStockCard({
  stock,
  onAnalyze,
  onEdit,
  onRemove,
  onSelect,
}: {
  stock: StockCardView;
  onAnalyze: (stock: StockCardView) => void;
  onEdit: (stock: StockCardView) => void;
  onRemove: (symbol: string) => void;
  onSelect: (stock: StockCardView) => void;
}) {
  return (
    <div style={MONITOR_CARD_LIST_STYLE}>
      <StockCard
        stock={stock}
        actions={["详情", "分析", "编辑", "移除"]}
        compact
        onAction={(action) => {
          if (action === "移除") {
            onRemove(stock.symbol);
          } else if (action === "编辑") {
            onEdit(stock);
          } else if (action === "分析") {
            onAnalyze(stock);
          } else {
            onSelect(stock);
          }
        }}
      />
    </div>
  );
});

export const SectorEtfOpportunityCard = memo(function SectorEtfOpportunityCard({ item }: { item: SectorEtfT0Opportunity }) {
  return (
    <article style={MONITOR_ETF_CARD_STYLE}>
      <div style={MONITOR_ETF_CARD_HEAD_STYLE}>
        <div style={MONITOR_ETF_CARD_HEAD_TEXT_STYLE}>
          <strong>{item.etf_name}</strong>
          <span>{item.etf_symbol} · 来源 {item.source_signal_name}</span>
        </div>
        <span className={`pill ${item.bias === "positive_t" ? "up" : item.bias === "negative_t" ? "down" : "neutral"}`}>{item.bias_text}</span>
      </div>
      <div style={MONITOR_ETF_CARD_META_STYLE}>
        <span>板块：{item.sector_name || "未分类"}</span>
        <span>分类：{etfCategoryText(item.etf_category)}</span>
        <span>T+0：{item.t0_eligible ? "已放行" : "未放行"}</span>
        <span>信心：{formatPct(item.confidence, 0)}</span>
        <span>分钟：{item.intraday_signal_text || "待刷新"}</span>
        <span>分钟信心：{formatPct(item.intraday_signal_confidence || 0, 0)}</span>
        <span>ETF价：{formatPrice(item.last_price)}</span>
        <span>ETF涨跌：{formatPct(item.change_pct)}</span>
      </div>
      <p style={MONITOR_ETF_CARD_HINT_STYLE}>{item.reason}</p>
      <p style={MONITOR_ETF_CARD_HINT_STYLE}>{formatEtfSignalSnapshot(item)}</p>
      <p style={MONITOR_ETF_CARD_HINT_STYLE}>买点 {item.entry_zone || "--"}；卖点 {item.sell_zone || "--"}；流动性门槛 {formatLargeAmount(item.min_amount)}；风险：{item.risk}</p>
    </article>
  );
});

export function MarketBreadthStrip({ marketBreadth }: { marketBreadth: MarketBreadth | null }) {
  if (!marketBreadth) {
    return null;
  }
  return (
    <Row gutter={[8, 8]} style={MONITOR_BREADTH_ROW_STYLE}>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="市场宽度" value={formatRatioPct(marketBreadth.stock_up_ratio)} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="中位涨跌" value={formatPct(marketBreadth.stock_median_change)} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="涨停/跌停" value={`${marketBreadth.limit_up_count} / ${marketBreadth.limit_down_count ?? "--"}`} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="炸板率" value={formatRatioPct(marketBreadth.broken_board_ratio)} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="连板高度" value={String(marketBreadth.board_height || "--")} />
      </Col>
      <Col xs={24} sm={12} lg={8} xl={4}>
        <InfoPill compact label="数据质量" value={marketBreadth.data_quality_text || "--"} tone={dataQualityTone(marketBreadth.data_quality)} />
      </Col>
    </Row>
  );
}

export function MonitorInputSideRail({
  marketPulse,
  primaryAction,
  priorityCards,
  reviewStatus,
  watchCards,
  onAnalyze,
  onGoPlaybook,
  onRefresh,
  onSelect,
}: {
  marketPulse: IntradayMarketPulse | null;
  primaryAction: ReturnType<typeof resolveTodayAction>;
  priorityCards: StockCardView[];
  reviewStatus: MarketReviewStatus | null;
  watchCards: StockCardView[];
  onAnalyze: (stock: StockCardView) => void;
  onGoPlaybook: () => void;
  onRefresh: () => void;
  onSelect: (stock: StockCardView) => void;
}) {
  const activeHoldings = watchCards.filter((card) => card.actionText !== "暂不操作").slice(0, 3);
  const topCandidates = priorityCards.slice(0, 3);
  return (
    <div style={MONITOR_SIDE_RAIL_STYLE}>
      <PanelTitle
        title="右侧速览"
        actions={<Button size="small" onClick={primaryAction.source === "holding" ? onRefresh : onGoPlaybook}>{primaryAction.source === "holding" ? "刷新" : "榜单"}</Button>}
      />
      <div style={MONITOR_SIDE_GRID_STYLE}>
        <InfoPill compact label="复盘状态" value={reviewStatus?.status_text || "等待"} tone={reviewStatus?.has_midday || reviewStatus?.has_close ? "up" : "warn"} />
        <InfoPill compact label="下次触发" value={shortTime(reviewStatus?.next_trigger_at) || "--"} />
      </div>
      <MiniMonitorList
        emptyText="暂无可执行持仓信号"
        items={activeHoldings}
        title="持仓动作"
        onAnalyze={onAnalyze}
        onSelect={onSelect}
      />
      <MiniMonitorList
        emptyText="暂无候选"
        items={topCandidates}
        title="榜单前三"
        onAnalyze={onAnalyze}
        onSelect={onSelect}
      />
    </div>
  );
}

function MiniMonitorList({
  emptyText,
  items,
  title,
  onAnalyze,
  onSelect,
}: {
  emptyText: string;
  items: StockCardView[];
  title: string;
  onAnalyze: (stock: StockCardView) => void;
  onSelect: (stock: StockCardView) => void;
}) {
  return (
    <div style={MONITOR_SIDE_LIST_STYLE}>
      <Typography.Text strong style={MONITOR_SIDE_ROW_TITLE_STYLE}>{title}</Typography.Text>
      {items.length ? items.map((stock) => (
        <article key={`${title}-${stock.symbol}`} style={MONITOR_SIDE_ROW_STYLE}>
          <div style={MONITOR_SIDE_ROW_HEAD_STYLE}>
            <Typography.Text strong ellipsis style={MONITOR_SIDE_ROW_TEXT_STYLE}>{stock.name}</Typography.Text>
            <Typography.Text style={sideRowToneStyle(stock.tone)}>{stock.changeText}</Typography.Text>
          </div>
          <Typography.Text ellipsis={{ tooltip: stock.actionText }} style={MONITOR_SIDE_ROW_META_STYLE}>{stock.symbol} · {stock.actionText}</Typography.Text>
          <Flex gap={5} wrap>
            <Button size="small" onClick={() => onSelect(stock)}>详情</Button>
            <Button size="small" onClick={() => onAnalyze(stock)}>分析</Button>
          </Flex>
        </article>
      )) : <EmptyState text={emptyText} />}
    </div>
  );
}

export function IntradayPulseCard({ pulse }: { pulse: IntradayMarketPulse | null }) {
  if (!pulse) {
    return (
      <Card size="small" title="盘中 Pulse" style={MONITOR_HOURLY_CARD_STYLE} styles={{ body: MONITOR_HOURLY_BODY_STYLE }}>
        <EmptyState text="Pulse 暂无数据" />
      </Card>
    );
  }
  return (
    <Card
      size="small"
      title="盘中 Pulse"
      extra={<Tag color={pulseTagColor(pulse.data_quality)}>{pulse.data_quality_text || pulse.data_quality}</Tag>}
      style={MONITOR_HOURLY_CARD_STYLE}
      styles={{ body: MONITOR_HOURLY_BODY_STYLE }}
    >
      <Space direction="vertical" size={8} style={MONITOR_FULL_WIDTH_STYLE}>
        <Callout
          title={pulse.pulse_text || "等待盘中数据刷新"}
          detail={pulse.suggested_action || "只读观察，不触发交易。"}
          tone={pulseTone(pulse.pulse_level)}
          compact
        />
        <Row gutter={[8, 8]}>
          <Col xs={24} sm={12} xl={12}>
            <InfoPill compact label="市场宽度" value={pulse.market_strength_text || "--"} />
          </Col>
          <Col xs={24} sm={12} xl={12}>
            <InfoPill compact label="情绪温度" value={pulse.emotion_text || "--"} />
          </Col>
        </Row>
        <InfoPill compact label="小时快照" value={pulse.hourly_snapshot_text || "--"} />
        {pulse.partial_errors?.length ? <InfoPill compact label="降级源" value={pulse.partial_errors.map((item) => item.source).join(" / ")} tone="warn" /> : null}
      </Space>
    </Card>
  );
}

export function MonitorReviewPanel({
  reviewStatus,
  reviewReports,
  marketPulse,
}: {
  reviewStatus: MarketReviewStatus | null;
  reviewReports: MarketReviewReport[];
  marketPulse: IntradayMarketPulse | null;
}) {
  const midday = reviewReports.find((item) => item.report_slot === "midday");
  const close = reviewReports.find((item) => item.report_slot === "close");
  return (
    <Card
      size="small"
      title="今日全市场午盘 / 收盘复盘"
      extra={<Typography.Text type="secondary">下次 {reviewStatus?.next_trigger_at || "--"}</Typography.Text>}
      style={MONITOR_HOURLY_CARD_STYLE}
      styles={{ body: MONITOR_HOURLY_BODY_STYLE }}
    >
      <Space direction="vertical" size={8} style={MONITOR_FULL_WIDTH_STYLE}>
        <Row gutter={[8, 8]}>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="今日状态" value={reviewStatus?.status_text || "今日暂无市场复盘"} tone={reviewStatus?.has_midday || reviewStatus?.has_close ? "up" : "warn"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="市场午盘复盘" value={midday ? "已生成" : "等待触发"} tone={midday ? "up" : "warn"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="市场收盘复盘" value={close ? "已生成" : "等待触发"} tone={close ? "up" : "warn"} />
          </Col>
          <Col xs={24} sm={12} xl={6}>
            <InfoPill compact label="风险提示" value={String(reviewStatus?.risk_alert_count ?? 0)} tone={(reviewStatus?.risk_alert_count ?? 0) > 0 ? "down" : "neutral"} />
          </Col>
        </Row>
        <Callout
          title="建议动作"
          detail={reviewStatus?.suggested_action || "等待午盘或收盘市场复盘生成，盘中按市场 pulse、既有风控和仓位约束执行。"}
          tone={(reviewStatus?.risk_alert_count ?? 0) > 0 ? "down" : "neutral"}
          compact
        />
        <Row gutter={[8, 8]}>
          <Col xs={24} md={12}>
            <ReviewSnippet title="全市场午盘复盘" report={midday} />
          </Col>
          <Col xs={24} md={12}>
            <ReviewSnippet title="全市场收盘复盘" report={close} />
          </Col>
        </Row>
        <RitualCloseBag visible={Boolean(close)} />
        {marketPulse?.autofill_details?.length ? (
          <Collapse
            ghost
            size="small"
            items={[{
              key: "autofill",
              label: "自动补全明细",
              children: marketPulse.autofill_details.map((item) => item.detail || item.source).join("；"),
            }]}
          />
        ) : null}
      </Space>
    </Card>
  );
}

function ReviewSnippet({ title, report }: { title: string; report?: MarketReviewReport }) {
  if (!report) {
    return <EmptyState text={`${title}暂未生成。`} />;
  }
  return (
    <article style={MONITOR_ETF_CARD_STYLE}>
      <Flex justify="space-between" gap={8}>
        <Typography.Text strong>{title}</Typography.Text>
        <Typography.Text type="secondary">{shortTime(report.generated_at) || report.report_date}</Typography.Text>
      </Flex>
      <Typography.Text ellipsis={{ tooltip: report.overall_summary || "--" }}>{report.overall_summary || "--"}</Typography.Text>
      <Typography.Text type="secondary" ellipsis={{ tooltip: report.suggestion || "--" }}>{report.suggestion || "--"}</Typography.Text>
      {(report.autofill_details?.length || report.missing_data?.length || report.risk_alerts?.length) ? (
        <Collapse
          ghost
          size="small"
          items={[{
            key: "detail",
            label: "明细",
            children: (
              <Space direction="vertical" size={2}>
                {report.autofill_details?.length ? <Typography.Text type="secondary">自动补全：{report.autofill_details.map((item) => item.detail || item.source).join("；")}</Typography.Text> : null}
                {report.missing_data?.length ? <Typography.Text type="secondary">缺少：{report.missing_data.map((item) => item.name || item.source).join("；")}</Typography.Text> : null}
                {report.risk_alerts?.length ? <Typography.Text type="danger">风险：{report.risk_alerts.map((item) => item.content).join("；")}</Typography.Text> : null}
              </Space>
            ),
          }]}
        />
      ) : null}
    </article>
  );
}

function pulseTagColor(quality?: string): string {
  if (quality === "fresh") return "green";
  if (quality === "partial" || quality === "stale") return "gold";
  return "red";
}

function pulseTone(level?: string): "up" | "warn" | "down" | "neutral" {
  if (level === "weak" || level === "defensive" || level === "unavailable" || level === "risk_off") return "down";
  if (level === "strong" || level === "repair" || level === "risk_on") return "up";
  if (level === "neutral" || level === "balanced") return "warn";
  return "neutral";
}

function toneColor(tone: string): string {
  if (tone === "up") return "var(--price-up)";
  if (tone === "down") return "var(--price-down)";
  if (tone === "warn") return "var(--warning)";
  return "var(--muted)";
}

export function HourlyAllMarketPulse({
  marketBreadth,
  history,
}: {
  marketBreadth: MarketBreadth | null;
  history: MarketHourlySnapshotHistoryItem[];
}) {
  const snapshot = marketBreadth?.hourly_all_market_snapshot;
  const points = buildHourlyTrendPoints(history, snapshot);
  if ((!snapshot || Object.keys(snapshot).length === 0) && !points.length) {
    return null;
  }
  const weakening = hourlyTrendWeakening(points);
  const latestPoint = points.length ? points[points.length - 1] : undefined;
  const firstHistory = history.length ? history[0] : undefined;
  return (
    <Card
      size="small"
      title="小时全市场快照"
      extra={<Typography.Text type="secondary">{shortTime(snapshot?.updated_at) || latestPoint?.label || "--"}</Typography.Text>}
      style={MONITOR_HOURLY_CARD_STYLE}
      styles={{ body: MONITOR_HOURLY_BODY_STYLE }}
    >
      {weakening ? (
        <Alert
          type="warning"
          showIcon
          message="全市场强弱分连续走弱"
          description="最近两个小时快照都在回落，短线追高要降速，优先观察已验证方向。"
          style={MONITOR_ALERT_SPACING_STYLE}
        />
      ) : null}
      <Row gutter={[8, 8]}>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="样本数" value={String(snapshot?.snapshot_count ?? firstHistory?.snapshot_count ?? "--")} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="上涨比例" value={formatRatioPct(snapshot?.stock_up_ratio)} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="下跌比例" value={formatRatioPct(snapshot?.stock_down_ratio)} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="中位涨跌" value={formatPct(snapshot?.stock_median_change)} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="强/弱" value={`${snapshot?.strong_count ?? "--"} / ${snapshot?.weak_count ?? "--"}`} />
        </Col>
        <Col xs={12} sm={8} xl={4}>
          <InfoPill compact label="强弱分" value={String(snapshot?.market_strength_score ?? latestPoint?.score ?? "--")} tone={hourlyPulseTone(snapshot?.market_strength_score ?? latestPoint?.score)} />
        </Col>
      </Row>
      {points.length >= 2 ? <HourlyTrendStrip points={points} /> : null}
      <Typography.Text type="secondary" style={MONITOR_HOURLY_NOTE_STYLE}>
        {snapshot?.market_strength_text || snapshot?.data_quality_text || latestPoint?.quality || "等待全市场快照刷新"}
      </Typography.Text>
    </Card>
  );
}

function HourlyTrendStrip({ points }: { points: Array<{ label: string; score: number; quality: string }> }) {
  const min = Math.min(...points.map((item) => item.score), -20);
  const max = Math.max(...points.map((item) => item.score), 20);
  const span = Math.max(max - min, 1);
  return (
    <div style={MONITOR_TREND_STRIP_STYLE}>
      <Flex justify="space-between" align="center">
        <Typography.Text strong>日内强弱趋势</Typography.Text>
        <Typography.Text type="secondary">{points.length} 个快照</Typography.Text>
      </Flex>
      <div style={trendBarGridStyle(points.length)}>
        {points.map((item) => {
          const height = Math.max(14, Math.round(((item.score - min) / span) * 54) + 10);
          return (
            <div key={item.label} style={MONITOR_TREND_BAR_ITEM_STYLE}>
              <div
                title={`${item.label} 强弱分 ${item.score.toFixed(1)} · ${item.quality}`}
                style={trendBarStyle(item.score, height)}
              />
              <Typography.Text type="secondary" style={MONITOR_TREND_LABEL_STYLE}>
                {item.label}
              </Typography.Text>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function sideRowToneStyle(tone: string) {
  return {
    ...MONITOR_SIDE_ROW_TEXT_STYLE,
    color: toneColor(tone),
  };
}

function etfCategoryText(category?: string): string {
  const mapping: Record<string, string> = {
    broad_base: "宽基",
    sector: "行业",
    cross_border: "跨境",
    bond: "债券",
    gold: "黄金",
    money: "货币",
    commodity: "商品",
  };
  return mapping[String(category || "")] || "未分类";
}

function formatLargeAmount(value?: number | null): string {
  return formatAmount(value);
}

function formatEtfSignalSnapshot(item: SectorEtfT0Opportunity): string {
  const snapshot = item.intraday_signal_snapshot || {};
  const current = Number(snapshot.current_price || 0);
  const vwap = Number(snapshot.vwap || 0);
  const rsi = Number(snapshot.rsi || 0);
  const edge = Number(snapshot.expected_edge_pct || 0);
  const riskFlags = item.intraday_risk_flags?.length ? `；阻断：${item.intraday_risk_flags.join("/")}` : "";
  if (!current && !vwap && !rsi) {
    return `分钟信号 ${item.intraday_signal_text || "待刷新"}${riskFlags}`;
  }
  return `分钟价 ${formatPrice(current)}；VWAP ${formatPrice(vwap)}；RSI ${rsi.toFixed(1)}；净边际 ${formatPct(edge)}${riskFlags}`;
}

function trendBarGridStyle(points: number) {
  return {
    ...MONITOR_TREND_BAR_GRID_STYLE,
    gridTemplateColumns: `repeat(${points}, minmax(0, 1fr))`,
  };
}

function trendBarStyle(score: number, height: number) {
  return {
    ...MONITOR_TREND_BAR_DYNAMIC_STYLE,
    height,
    background: score >= 10 ? "var(--price-down)" : score <= -10 ? "var(--price-up)" : "var(--warning)",
  };
}

function buildHourlyTrendPoints(
  history: MarketHourlySnapshotHistoryItem[],
  snapshot?: MarketBreadth["hourly_all_market_snapshot"],
): Array<{ label: string; score: number; quality: string }> {
  const points = history
    .slice()
    .sort((left, right) => String(left.snapshot_bucket).localeCompare(String(right.snapshot_bucket)))
    .map((item) => ({
      label: hourlyBucketLabel(item.snapshot_bucket) || shortTime(item.updated_at) || "--",
      score: Number(item.market_strength_score ?? item.payload?.market_strength_score ?? 0),
      quality: item.data_quality || String(item.payload?.data_quality_text || ""),
    }))
    .filter((item) => Number.isFinite(item.score));
  if (snapshot && Number.isFinite(Number(snapshot.market_strength_score))) {
    const label = shortTime(snapshot.updated_at) || "最新";
    const latestScore = Number(snapshot.market_strength_score);
    const exists = points.some((item) => item.label === label && Math.abs(item.score - latestScore) < 0.001);
    if (!exists) {
      points.push({
        label,
        score: latestScore,
        quality: snapshot.data_quality_text || "",
      });
    }
  }
  return points.slice(-8);
}

function hourlyTrendWeakening(points: Array<{ score: number }>): boolean {
  if (points.length < 3) return false;
  const recent = points.slice(-3);
  return recent[2].score < recent[1].score - 5 && recent[1].score < recent[0].score - 5;
}

function hourlyBucketLabel(bucket: string): string {
  const compact = String(bucket || "").replace(/\D/g, "");
  if (compact.length >= 12) {
    return `${compact.slice(8, 10)}:${compact.slice(10, 12)}`;
  }
  return "";
}

function hourlyPulseTone(score?: number): "up" | "warn" | "down" | "neutral" {
  if (typeof score !== "number" || !Number.isFinite(score)) return "neutral";
  if (score >= 10) return "up";
  if (score <= -10) return "down";
  return "warn";
}

export function KeyLevelAlerts({ alerts }: { alerts: IntradayKeyLevelResponse[] }) {
  const triggered = alerts.filter((item) => item.alert_triggered).slice(0, 2);
  if (!triggered.length) {
    return null;
  }
  return (
    <Space
      direction="vertical"
      role="alert"
      aria-live="polite"
      style={MONITOR_KEY_ALERT_WRAP_STYLE}
    >
      {triggered.map((item) => (
        <Alert
          key={item.symbol}
          type="warning"
          showIcon
          style={MONITOR_KEY_ALERT_STYLE}
          message={<span style={MONITOR_KEY_ALERT_TITLE_STYLE}>{item.name} 接近关键价位</span>}
          description={<span style={MONITOR_KEY_ALERT_DESC_STYLE}>{item.alert_text || `现价 ${formatPrice(item.latest_price)}`}</span>}
        />
      ))}
    </Space>
  );
}
