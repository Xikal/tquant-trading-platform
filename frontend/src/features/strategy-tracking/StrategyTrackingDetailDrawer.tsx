import { Alert, Collapse, Drawer, Space, Table, Tag, Timeline } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { StrategyTrackingViewMode } from "../../stores/strategyTrackingStore";
import type { AnalysisResponse } from "../../types";
import type { StrategyTrackingDetailResponse, StrategyTrackingTimelinePoint } from "../../types";
import { TqEmpty, TqPageLoading } from "../../ui/feedback/StateViews";
import { MiniKline } from "../workspace-shared/MiniKlineChart";
import { formatPct, formatPrice } from "../workspace-shared/workspaceFormatters";
import { exitQualityTone, holdingBucketText, holdExtensionTone, suggestedPlanText } from "./strategyTrackingFormatters";
import { StrategyTrackingSectorTags } from "./StrategyTrackingSectorTags";

interface StrategyTrackingDetailDrawerProps {
  open: boolean;
  loading: boolean;
  detail?: StrategyTrackingDetailResponse;
  errorText?: string;
  viewMode?: StrategyTrackingViewMode;
  onClose: () => void;
}

export function StrategyTrackingDetailDrawer({
  open,
  loading,
  detail,
  errorText,
  viewMode = "beginner",
  onClose,
}: StrategyTrackingDetailDrawerProps) {
  const item = detail?.item;
  return (
    <Drawer title={item ? `${item.name || item.symbol} · ${item.strategy_name}` : "单票详情"} open={open} onClose={onClose} width={720}>
      {loading ? <TqPageLoading label="详情加载中" rows={3} /> : null}
      {errorText ? <Alert type="error" showIcon title={errorText} /> : null}
      {!loading && !errorText && !detail ? (
        <TqEmpty title="这只股票后续行情数据不足" description="暂时不能判断推荐后的表现。" />
      ) : null}
      {detail ? <StrategyTrackingDetailContent detail={detail} viewMode={viewMode} /> : null}
    </Drawer>
  );
}

export function StrategyTrackingDetailContent({ detail, viewMode = "beginner" }: { detail: StrategyTrackingDetailResponse; viewMode?: StrategyTrackingViewMode }) {
  const item = detail.item;
  return (
    <Space className="strategy-tracking-detail" orientation="vertical" size={12}>
      {detail.partial_errors.length ? <Alert type="warning" showIcon title={detail.partial_errors.join("；")} /> : null}
      <Alert type={item.user_friendly_status === "weakening" ? "warning" : "info"} showIcon title="当前结论" description={item.plain_language_summary || item.user_friendly_reason} />
      <div className="strategy-tracking-detail-head">
        <strong>{item.name || item.symbol} · {item.symbol}</strong>
        <div className="strategy-tracking-tag-row">
          <Tag color="blue">{item.signal_text}</Tag>
          <Tag color={item.stop_triggered ? "red" : "green"}>{item.lifecycle_status_text}</Tag>
          <Tag>{item.data_quality_text}</Tag>
        </div>
      </div>
      <div className="strategy-tracking-cell-stack">
        <span>所属板块</span>
        <StrategyTrackingSectorTags sectors={fullSectors(item)} boardType={item.board_type} boardText={item.board_type_text} max={8} />
      </div>
      <div className="strategy-tracking-detail-metrics">
        <span>推荐价 {formatPrice(item.first_signal_price)}</span>
        <span>首次推荐 {item.first_signal_date}</span>
        <span>买点 {formatPrice(item.entry_zone_low)}~{formatPrice(item.entry_zone_high)}</span>
        <span>风险线 {formatPrice(item.stop_loss)}</span>
        <span>目标 {formatPrice(item.target_price)}</span>
      </div>
      <div className="strategy-tracking-detail-metrics">
        <span>支撑/最低 {formatPrice(item.actual_low_price)}</span>
        <span>最高日 {item.actual_high_date || "--"}</span>
        <span>最优持有 {item.best_holding_days || "--"}天</span>
        <span>最优收益 {formatPct(item.best_exit_return_pct)}</span>
      </div>
      <div className="strategy-tracking-tag-row">
        <Tag color={exitQualityTone(item.exit_quality)}>{item.exit_reason || "暂无退出评价"}</Tag>
        <Tag>{holdingBucketText(item.holding_bucket)}</Tag>
        <Tag color={holdExtensionTone(item.hold_extension_state)}>{item.hold_extension_text}</Tag>
        <Tag>{suggestedPlanText(item.suggested_holding_plan)}</Tag>
        {item.needs_review ? <Tag color="orange">需复核</Tag> : null}
      </div>
      {item.failure_reason_text ? <Alert type="warning" showIcon title="失败归因" description={item.failure_reason_text} /> : null}
      {item.hold_extension_reasons.length || item.hold_extension_risks.length ? (
        <Alert
          type={item.hold_extension_state === "qualified" ? "success" : "info"}
          showIcon
          title={`延长持有评分 ${item.hold_extension_score}`}
          description={[...item.hold_extension_reasons, ...item.hold_extension_risks].join("；")}
        />
      ) : null}
      <p className="strategy-tracking-review-text">{detail.review_text}</p>
      <section className="strategy-tracking-detail-section">
        <strong>推荐后发生了什么</strong>
        <Timeline items={timelineItems(detail)} />
      </section>
      {viewMode === "professional" ? (
        <Collapse
          size="small"
          items={[
            {
              key: "audit",
              label: "专业审计字段",
              children: (
                <div className="strategy-tracking-detail-metrics">
                  <span>数据截止 {item.data_cutoff_at || "--"}</span>
                  <span>回看窗口 {item.lookback_start_date || "--"} ~ {item.lookback_end_date || "--"}</span>
                  <span>后验起点 {item.posterior_start_date || "--"}</span>
                  <span>数据源 {item.market_data_source || "--"}</span>
                  <span>审计 {item.future_leak_check}</span>
                </div>
              ),
            },
          ]}
        />
      ) : null}
      <MiniKline bars={timelineToKlineBars(detail.timeline)} />
      <Table
        rowKey="trade_date"
        size="small"
        dataSource={detail.timeline}
        pagination={{ pageSize: 12 }}
        columns={timelineColumns}
      />
    </Space>
  );
}

function fullSectors(item: StrategyTrackingDetailResponse["item"]): string[] {
  return Array.from(new Set([
    item.board_type_text,
    ...(item.industry_sectors || []),
    ...(item.concept_sectors || []),
    ...(item.display_sectors || []),
  ].filter(Boolean)));
}

function timelineItems(detail: StrategyTrackingDetailResponse) {
  const item = detail.item;
  const rows = [
    { key: "signal", children: `推荐日 ${item.first_signal_date}，推荐价 ${formatPrice(item.first_signal_price)}` },
  ];
  if (item.entry_touched) rows.push({ key: "entry", children: "已到计划买入区" });
  if (item.actual_high_date) rows.push({ key: "high", children: `实际最高点 ${item.actual_high_date}，推荐后最高涨过 ${formatPct(item.max_gain_pct)}` });
  if ((item.spike_retrace_pct || 0) >= 4) rows.push({ key: "retrace", children: `曾经涨过，但后来回落 ${formatPct(item.spike_retrace_pct)}` });
  if (item.stop_triggered_date) rows.push({ key: "stop", children: `已跌破风险线 ${item.stop_triggered_date}` });
  if (item.invalidated_date) rows.push({ key: "invalid", children: `信号已失效 ${item.invalidated_date}` });
  if (item.best_exit_date) rows.push({ key: "best", children: `最优退出点 ${item.best_exit_date}，最优持有 ${item.best_holding_days} 天` });
  return rows;
}

function timelineToKlineBars(timeline: StrategyTrackingTimelinePoint[]): AnalysisResponse["bars"] {
  return timeline.map((point) => ({
    timestamp: `${point.trade_date}T15:00:00`,
    open: point.open,
    close: point.close,
    high: point.high,
    low: point.low,
    volume: 0,
    amount: 0,
    change_pct: point.pct_chg,
  }));
}

const timelineColumns: ColumnsType<StrategyTrackingTimelinePoint> = [
  { title: "日期", dataIndex: "trade_date", width: 100 },
  { title: "持有", dataIndex: "holding_day", width: 70, render: (value) => value ? `${value}天` : "--" },
  { title: "开", dataIndex: "open", width: 70, render: (value) => formatPrice(value) },
  { title: "高", dataIndex: "high", width: 70, render: (value) => formatPrice(value) },
  { title: "低", dataIndex: "low", width: 70, render: (value) => formatPrice(value) },
  { title: "收", dataIndex: "close", width: 70, render: (value) => formatPrice(value) },
  { title: "现在涨跌", dataIndex: "current_return_pct", width: 90, render: (value) => formatPct(value) },
  { title: "最高涨过", dataIndex: "max_return_pct", width: 90, render: (value) => formatPct(value) },
  { title: "最多跌过", dataIndex: "max_drawdown_pct", width: 90, render: (value) => formatPct(value) },
  {
    title: "标记",
    width: 130,
    render: (_, point) => (
      <>
        {point.hit_entry_zone ? <Tag color="green">到买入区</Tag> : null}
        {point.hit_target ? <Tag color="blue">到目标位</Tag> : null}
        {point.hit_stop_loss ? <Tag color="red">跌破风险线</Tag> : null}
        {point.is_best_exit ? <Tag color="gold">最优退出</Tag> : null}
      </>
    ),
  },
];
