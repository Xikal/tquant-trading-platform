import { For, Show, createMemo, type JSX } from "solid-js";
import { Button } from "../../shared/ui/Button";
import { DataTable } from "../../shared/ui/DataTable";
import { EmptyState } from "../../shared/ui/EmptyState";
import { StatusPill } from "../../shared/ui/StatusPill";
import {
  chips,
  field,
  idOf,
  nameOf,
  numericText,
  pctValue,
  raw,
  strategyOf,
  symbolOf,
  toneFromRecord,
  type TableColumn,
  type TrackingRecord,
  type ViewMode,
} from "./strategyTrackingModel";

export function StrategyTrackingTable(props: {
  items: TrackingRecord[];
  page: number;
  pageSize: number;
  total: number;
  selectedId: string;
  mode: ViewMode;
  onPageChange: (page: number) => void;
  onSelect: (item: TrackingRecord, index: number) => void;
}) {
  const totalPages = createMemo(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
  const pageItems = createMemo(() => props.items.slice((props.page - 1) * props.pageSize, props.page * props.pageSize));
  const columns = createMemo<TableColumn[]>(() => buildColumns(props.mode, props.selectedId));

  return (
    <div class="strategy-tracking-table-shell" data-testid="strategy-tracking-table">
      <Show when={props.items.length > 0} fallback={<EmptyState text="当前筛选条件下暂无策略跟踪数据" />}>
        <DataTable
          data={pageItems()}
          columns={columns()}
          emptyText="当前页暂无策略跟踪数据"
          ariaLabel="策略跟踪列表"
          minWidth={props.mode === "production" ? 880 : 1040}
          rowKey={(row, index) => idOf(row, index)}
          rowTone={(row) => toneFromRecord(row)}
          onRowClick={props.onSelect}
          data-testid="strategy-tracking-data-table"
        />
        <div class="strategy-tracking-card-list" aria-label="策略跟踪移动卡片">
          <For each={pageItems()}>
            {(item, index) => (
              <button
                type="button"
                class={`strategy-tracking-card${idOf(item, index()) === props.selectedId ? " strategy-tracking-card--active" : ""}`}
                onClick={() => props.onSelect(item, index())}
              >
                <span class="strategy-tracking-card__head">
                  <strong>{symbolOf(item)}</strong>
                  <span>{nameOf(item) || strategyOf(item)}</span>
                </span>
                <span>{field(item, ["plain_language_summary", "user_friendly_reason", "review_text", "reason"], "暂无说明")}</span>
                <span class="tq-tag-row">
                  <StatusPill label="状态" value={field(item, ["signal_text", "signal_state", "status"])} />
                  <StatusPill label="收益" value={pctValue(raw(item, ["current_return_pct", "return_pct"]))} tone={toneFromRecord(item)} />
                </span>
              </button>
            )}
          </For>
        </div>
        <div class="strategy-tracking-pagination">
          <span>
            第 {props.page} / {totalPages()} 页，共 {props.total} 条
          </span>
          <div class="tq-tag-row">
            <Button size="compact" disabled={props.page <= 1} onClick={() => props.onPageChange(props.page - 1)}>
              上一页
            </Button>
            <Button size="compact" disabled={props.page >= totalPages()} onClick={() => props.onPageChange(props.page + 1)}>
              下一页
            </Button>
          </div>
        </div>
      </Show>
    </div>
  );
}

function buildColumns(mode: ViewMode, selectedId: string): TableColumn[] {
  const base: TableColumn[] = [
    {
      header: "标的 / 策略",
      cell: (ctx) => (
        <div class="strategy-tracking-cell">
          <button type="button" class="strategy-tracking-link" aria-label={`查看 ${symbolOf(ctx.row.original)} 详情`}>
            {symbolOf(ctx.row.original)}
          </button>
          <span>{nameOf(ctx.row.original) || strategyOf(ctx.row.original)}</span>
          <Show when={idOf(ctx.row.original, ctx.row.index) === selectedId}>
            <small>已选中</small>
          </Show>
        </div>
      ),
    },
    {
      header: "信号",
      cell: (ctx) => (
        <div class="strategy-tracking-cell">
          <strong>{field(ctx.row.original, ["signal_text", "signal_state", "status"])}</strong>
          <span>{field(ctx.row.original, ["lifecycle_status_text", "user_friendly_status_text", "data_quality_text"])}</span>
        </div>
      ),
    },
    {
      header: "表现",
      cell: (ctx) => (
        <div class="strategy-tracking-cell">
          <strong class="tnum">{pctValue(raw(ctx.row.original, ["current_return_pct", "return_pct", "avg_current_return_pct"]))}</strong>
          <span>最大 {pctValue(raw(ctx.row.original, ["max_gain_pct", "avg_max_gain_pct"]))}</span>
        </div>
      ),
    },
    {
      header: "风险",
      cell: (ctx) => (
        <div class="strategy-tracking-cell">
          <span>{field(ctx.row.original, ["review_priority", "exit_quality", "failure_reason_text"], "常规")}</span>
          <span>回撤 {pctValue(raw(ctx.row.original, ["max_drawdown_pct", "avg_max_drawdown_pct"]))}</span>
        </div>
      ),
    },
    {
      header: "说明",
      cell: (ctx) => <span>{field(ctx.row.original, ["plain_language_summary", "user_friendly_reason", "review_text", "reason"], "暂无说明")}</span>,
      meta: { mobileHidden: true },
    },
  ];

  if (mode === "research") {
    return [
      ...base,
      {
        header: "持有",
        cell: (ctx) => (
          <div class="strategy-tracking-cell">
            <span>{field(ctx.row.original, ["hold_extension_text", "holding_bucket", "suggested_holding_plan"])}</span>
            <span>{numericText(ctx.row.original, ["best_holding_days"], " 天")}</span>
          </div>
        ),
      },
      {
        header: "标签",
        cell: (ctx) => <ChipRow values={chips(ctx.row.original, ["warning_tags", "failure_tags", "display_sectors", "concept_sectors"])} />,
        meta: { mobileHidden: true },
      },
    ];
  }
  return base;
}

function ChipRow(props: { values: string[] }): JSX.Element {
  return (
    <Show when={props.values.length > 0} fallback={<span class="tq-muted">--</span>}>
      <span class="tq-tag-row">
        <For each={props.values}>{(value) => <span class="tq-tag">{value}</span>}</For>
      </span>
    </Show>
  );
}
