import { Alert, Drawer, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { AnalysisResponse } from "../../types";
import type { StrategyTrackingDetailResponse, StrategyTrackingTimelinePoint } from "../../types";
import { TqEmpty, TqPageLoading } from "../../ui/feedback/StateViews";
import { MiniKline } from "../workspace-shared/MiniKlineChart";
import { formatPct, formatPrice } from "../workspace-shared/workspaceFormatters";

interface StrategyTrackingDetailDrawerProps {
  open: boolean;
  loading: boolean;
  detail?: StrategyTrackingDetailResponse;
  errorText?: string;
  onClose: () => void;
}

export function StrategyTrackingDetailDrawer({
  open,
  loading,
  detail,
  errorText,
  onClose,
}: StrategyTrackingDetailDrawerProps) {
  const item = detail?.item;
  return (
    <Drawer title={item ? `${item.name || item.symbol} · ${item.strategy_name}` : "单票详情"} open={open} onClose={onClose} width={680}>
      {loading ? <TqPageLoading label="详情加载中" rows={3} /> : null}
      {errorText ? <Alert type="error" showIcon title={errorText} /> : null}
      {!loading && !errorText && !detail ? (
        <TqEmpty title="这只股票后续行情数据不足" description="暂时不能判断推荐后的表现。" />
      ) : null}
      {detail ? <StrategyTrackingDetailContent detail={detail} /> : null}
    </Drawer>
  );
}

export function StrategyTrackingDetailContent({ detail }: { detail: StrategyTrackingDetailResponse }) {
  const item = detail.item;
  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      {detail.partial_errors.length ? <Alert type="warning" showIcon title={detail.partial_errors.join("；")} /> : null}
      <strong>{item.name || item.symbol} · {item.symbol}</strong>
      <Space wrap size={8}>
        <Tag color="blue">{item.signal_text}</Tag>
        <Tag color={item.stop_triggered ? "red" : "green"}>{item.lifecycle_status_text}</Tag>
        <Tag>{item.data_quality_text}</Tag>
        <Tag>推荐价 {formatPrice(item.first_signal_price)}</Tag>
        <Tag>首次推荐 {item.first_signal_date}</Tag>
        <Tag>买点 {formatPrice(item.entry_zone_low)}~{formatPrice(item.entry_zone_high)}</Tag>
        <Tag>止损 {formatPrice(item.stop_loss)}</Tag>
      </Space>
      <p>{detail.review_text}</p>
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
  { title: "开", dataIndex: "open", width: 70, render: (value) => formatPrice(value) },
  { title: "高", dataIndex: "high", width: 70, render: (value) => formatPrice(value) },
  { title: "低", dataIndex: "low", width: 70, render: (value) => formatPrice(value) },
  { title: "收", dataIndex: "close", width: 70, render: (value) => formatPrice(value) },
  { title: "收益", dataIndex: "current_return_pct", width: 80, render: (value) => formatPct(value) },
  { title: "最高", dataIndex: "max_return_pct", width: 80, render: (value) => formatPct(value) },
  { title: "回撤", dataIndex: "max_drawdown_pct", width: 80, render: (value) => formatPct(value) },
  {
    title: "标记",
    width: 130,
    render: (_, point) => (
      <>
        {point.hit_entry_zone ? <Tag color="green">买点</Tag> : null}
        {point.hit_target ? <Tag color="blue">止盈</Tag> : null}
        {point.hit_stop_loss ? <Tag color="red">止损</Tag> : null}
      </>
    ),
  },
];
