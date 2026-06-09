import { Button, Tag } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import type { StrategyTrackingViewMode } from "../../stores/strategyTrackingStore";
import type { StrategyTrackingItem } from "../../types";
import { VirtualCardList } from "../../ui/list/VirtualCardList";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { formatPct, formatPrice } from "../workspace-shared/workspaceFormatters";
import {
  displayReturn,
  entryZoneText,
  holdingBucketText,
  holdExtensionTone,
} from "./strategyTrackingFormatters";
import { signalStateHelpText, signalStateKindText, signalStateText } from "./signalStateCopy";
import { StrategyTrackingSectorTags } from "./StrategyTrackingSectorTags";
import { RitualSignalSeal } from "../ritual-ui";

interface StrategyTrackingTableProps {
  items: StrategyTrackingItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  viewMode?: StrategyTrackingViewMode;
  onPageChange: (page: number, pageSize: number) => void;
  onOpenDetail: (itemId: string) => void;
}

export function StrategyTrackingTable({
  items,
  total,
  page,
  pageSize,
  loading,
  viewMode = "beginner",
  onPageChange,
  onOpenDetail,
}: StrategyTrackingTableProps) {
  return (
    <>
      <div className="strategy-tracking-table-grid">
        <VirtualGrid<StrategyTrackingItem>
          rowKey="id"
          loading={loading}
          dataSource={items}
          columns={columns(onOpenDetail, viewMode)}
          scroll={{ x: viewMode === "professional" ? 1260 : 1040 }}
          defaultScrollY={560}
          paginated
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: [20, 30, 50],
          }}
          onChange={(pagination: TablePaginationConfig) => onPageChange(pagination.current || 1, pagination.pageSize || 30)}
        />
      </div>
      <div className="strategy-tracking-card-list">
        <VirtualCardList
          items={items}
          estimateSize={214}
          maxHeight={680}
          getItemKey={(item) => item.id}
          empty={loading ? <p className="hint">策略跟踪加载中...</p> : null}
          renderItem={(item) => <StrategyTrackingMobileCard item={item} onOpenDetail={onOpenDetail} />}
        />
        {total > pageSize ? (
          <div className="strategy-tracking-card-pagination">
            <Button size="small" disabled={page <= 1 || loading} onClick={() => onPageChange(Math.max(1, page - 1), pageSize)}>
              上一页
            </Button>
            <span>第 {page} 页 / 共 {total} 条</span>
            <Button size="small" disabled={page * pageSize >= total || loading} onClick={() => onPageChange(page + 1, pageSize)}>
              下一页
            </Button>
          </div>
        ) : null}
      </div>
    </>
  );
}

function StrategyTrackingMobileCard({
  item,
  onOpenDetail,
}: {
  item: StrategyTrackingItem;
  onOpenDetail: (itemId: string) => void;
}) {
  return (
    <article className="strategy-tracking-mobile-card">
      <div className="strategy-tracking-mobile-card__head">
        <Button className="strategy-tracking-stock-link" type="link" size="small" onClick={() => onOpenDetail(item.id)}>
          <span>{item.name || item.symbol}</span>
          <small>{item.symbol}</small>
        </Button>
        <Tag color={friendlyTone(item.user_friendly_status)}>{item.user_friendly_status_text}</Tag>
      </div>
      <StrategyTrackingSectorTags sectors={item.display_sectors} boardType={item.board_type} boardText={item.board_type_text} />
      <div className="strategy-tracking-mobile-card__section">
        <strong>结论与原因</strong>
        <span>{item.user_friendly_reason}</span>
        <small>{item.failure_reason_text || item.plain_language_summary || item.data_quality_text}</small>
      </div>
      <div className="strategy-tracking-mobile-card__section">
        <strong>信号性质</strong>
        <Tag color={signalTone(item.signal_state)}>{signalStateText(item)}</Tag>
        <span>{mobileSignalStateText(item.signal_state)}</span>
      </div>
      <div className="strategy-tracking-mobile-card__metrics">
        <span>计划买入区 {entryZoneText(item)}</span>
        <span>风险线 {formatPrice(item.stop_loss)}</span>
        <span>目标 {formatPrice(item.target_price)}</span>
        <span>最高 {displayReturn(item.max_gain_pct)}</span>
        <span>回撤 {formatPct(item.max_drawdown_pct)}</span>
        <span>现涨跌 {displayReturn(item.current_return_pct)}</span>
      </div>
      <div className="strategy-tracking-tag-row">
        {item.entry_touched ? <Tag color="green">已到计划买入区</Tag> : <Tag>还没到计划买入价</Tag>}
        {item.stop_triggered ? <Tag color="red">已跌破风险线</Tag> : null}
        {item.target_touched ? <Tag color="blue">已触达目标位</Tag> : null}
      </div>
    </article>
  );
}

function mobileSignalStateText(signalState: string): string {
  if (signalState === "near_entry") return "观察提醒：接近买点但不是买入";
  if (signalState === "observe_confirmed") return "观察提醒：确认观察但不是买入";
  if (signalState === "watch" || signalState === "front_row_only") return "观察提醒：只跟踪，不是买入";
  return signalStateKindText(signalState);
}

function columns(onOpenDetail: (itemId: string) => void, viewMode: StrategyTrackingViewMode): ColumnsType<StrategyTrackingItem> {
  return [
    {
      title: "股票 / 板块",
      dataIndex: "symbol",
      fixed: "left",
      width: 170,
      render: (_, item) => (
        <Button className="strategy-tracking-stock-link" type="link" size="small" onClick={() => onOpenDetail(item.id)}>
          <span>{item.name || item.symbol}</span>
          <small>{item.symbol}</small>
          <StrategyTrackingSectorTags sectors={item.display_sectors} boardType={item.board_type} boardText={item.board_type_text} />
        </Button>
      ),
    },
    {
      title: "结论与原因",
      width: 190,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <Tag color={friendlyTone(item.user_friendly_status)}>{item.user_friendly_status_text}</Tag>
          <RitualSignalSeal signalState={item.signal_state} riskLevel={item.stop_triggered ? "stop" : item.user_friendly_status} compact />
          <span>{item.user_friendly_reason}</span>
          <small>{item.failure_reason_text || item.plain_language_summary || item.data_quality_text}</small>
        </div>
      ),
    },
    {
      title: "信号性质",
      width: 180,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack" title={signalStateHelpText(item.signal_state)}>
          <Tag color={signalTone(item.signal_state)}>{signalStateText(item)}</Tag>
          <strong>{signalStateKindText(item.signal_state)}</strong>
        </div>
      ),
    },
    {
      title: "计划与触发",
      width: 200,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <strong>{item.strategy_name}</strong>
          <span>计划买入区 {entryZoneText(item)}</span>
          <span>风险线 {formatPrice(item.stop_loss)} · 目标 {formatPrice(item.target_price)}</span>
          <div className="strategy-tracking-tag-row">
            {item.entry_touched ? <Tag color="green">已到计划买入区</Tag> : <Tag>还没到计划买入价</Tag>}
            {item.stop_triggered ? <Tag color="red">已跌破风险线</Tag> : null}
            {item.target_touched ? <Tag color="blue">已触达目标位</Tag> : null}
          </div>
        </div>
      ),
    },
    {
      title: "策略线",
      width: 130,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <Tag color={laneTone(item.display_lane)}>{item.display_lane_title || "原低吸策略"}</Tag>
          <span>{laneRoleText(item)}</span>
          {item.strategy_engine_shadow ? (
            <small>{strategyEngineShadowText(item.strategy_engine_parity_status)}</small>
          ) : null}
          {item.matched_strategy_variants?.length && item.matched_strategy_variants.length > 1 ? (
            <small>同时命中：{item.matched_strategy_variants.map(laneName).join(" / ")}</small>
          ) : null}
        </div>
      ),
    },
    {
      title: "信号后表现",
      width: 170,
      render: (_, item) => (
        <div className="strategy-tracking-cell-stack">
          <span>信号后最高涨过 {displayReturn(item.max_gain_pct)}</span>
          <span>信号后最多跌过 {formatPct(item.max_drawdown_pct)}</span>
          <span>现在涨跌 {displayReturn(item.current_return_pct)}</span>
        </div>
      ),
    },
    ...(viewMode === "professional" ? [holdingColumn(), reviewColumn()] : []),
    ...(viewMode === "professional" ? [professionalColumn()] : []),
  ];
}

function holdingColumn(): ColumnsType<StrategyTrackingItem>[number] {
  return {
    title: "适合持有",
    width: 190,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>{item.best_holding_days ? `更适合：${holdingBucketText(item.holding_bucket)}` : "暂无持有窗口"}</span>
        <span>{item.best_holding_days ? `最优：${item.best_holding_days} 天` : "样本不足"}</span>
        <Tag color={holdExtensionTone(item.hold_extension_state)}>{item.hold_extension_text}</Tag>
      </div>
    ),
  };
}

function reviewColumn(): ColumnsType<StrategyTrackingItem>[number] {
  return {
    title: "复核",
    width: 160,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>{item.first_signal_date} 信号</span>
        <span>现价 {formatPrice(item.current_price)}</span>
        {item.needs_review ? <Tag color="orange">需复核</Tag> : null}
      </div>
    ),
  };
}

function professionalColumn(): ColumnsType<StrategyTrackingItem>[number] {
  return {
    title: "专业审计",
    width: 220,
    render: (_, item) => (
      <div className="strategy-tracking-cell-stack">
        <span>数据截止 {item.data_cutoff_at || "--"}</span>
        <span>后验起点 {item.posterior_start_date || "--"}</span>
        <span>审计 {item.future_leak_check}</span>
      </div>
    ),
  };
}

function friendlyTone(status: string): string {
  if (status === "focus") return "green";
  if (status === "wait_entry") return "gold";
  if (status === "weakening") return "red";
  if (status === "take_profit_watch") return "blue";
  if (status === "review_needed") return "orange";
  return "default";
}

function signalTone(signalState: string): string {
  if (signalState === "buy_now" || signalState === "soft_buy_now") return "green";
  if (signalState === "near_entry" || signalState === "observe_confirmed") return "gold";
  return "default";
}

function laneTone(lane?: string): string {
  if (lane === "front_row_weighted") return "gold";
  if (lane === "front_row_only") return "blue";
  return "default";
}

function laneRoleText(item: StrategyTrackingItem): string {
  if (item.display_lane === "front_row_weighted") return "影子验证中 · 未接生产";
  if (item.display_lane === "front_row_only") return "仅观察 · 不参与生产排序";
  return "旧策略排序 · 保留具体策略名";
}

function strategyEngineShadowText(status?: string): string {
  return status === "match" ? "影子校验一致 · 不影响真实排序" : "影子校验待复核 · 不影响真实排序";
}

function laneName(lane: string): string {
  if (lane === "front_row_weighted") return "前排加权";
  if (lane === "front_row_only") return "前排极精选";
  return "原低吸";
}
