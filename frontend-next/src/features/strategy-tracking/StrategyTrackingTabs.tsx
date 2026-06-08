import { For, Show } from "solid-js";
import { DataTable } from "../../shared/ui/DataTable";
import { EmptyState } from "../../shared/ui/EmptyState";
import { StatusPill } from "../../shared/ui/StatusPill";
import { Tabs } from "../../shared/ui/Tabs";
import {
  field,
  firstRecord,
  pctValue,
  raw,
  recordsFrom,
  safeJsonPreview,
  strategyOf,
  symbolOf,
  toneFromRecord,
  type AnalysisTab,
  type OperationDataState,
  type TrackingRecord,
} from "./strategyTrackingModel";
import { StrategyTrackingReviewCenter } from "./StrategyTrackingReviewCenter";

const TAB_ITEMS = [
  { key: "performance", label: "表现" },
  { key: "holding", label: "持有" },
  { key: "drift", label: "漂移" },
  { key: "diagnostics", label: "诊断" },
  { key: "review", label: "复盘中心" },
] satisfies { key: AnalysisTab; label: string }[];

export function StrategyTrackingTabs(props: {
  active: AnalysisTab;
  onChange: (tab: AnalysisTab) => void;
  queries: {
    performance: OperationDataState;
    holding: OperationDataState;
    review: OperationDataState;
    journal: OperationDataState;
    relativeStrength: OperationDataState;
  };
  selected: TrackingRecord | undefined;
  filteredItems: TrackingRecord[];
}) {
  return (
    <div class="strategy-tracking-tabs" data-testid="strategy-tracking-tabs">
      <Tabs items={TAB_ITEMS} value={props.active} onChange={props.onChange} label="策略分析标签" />
      <Show when={props.active === "performance"}>
        <PerformanceTab query={props.queries.performance} fallbackItems={props.filteredItems} />
      </Show>
      <Show when={props.active === "holding"}>
        <HoldingTab query={props.queries.holding} />
      </Show>
      <Show when={props.active === "drift"}>
        <DriftTab review={props.queries.review} fallbackItems={props.filteredItems} />
      </Show>
      <Show when={props.active === "diagnostics"}>
        <DiagnosticsTab query={props.queries.review} selected={props.selected} />
      </Show>
      <Show when={props.active === "review"}>
        <StrategyTrackingReviewCenter journal={props.queries.journal} relativeStrength={props.queries.relativeStrength} selected={props.selected} />
      </Show>
    </div>
  );
}

function PerformanceTab(props: { query: OperationDataState; fallbackItems: TrackingRecord[] }) {
  const items = () => recordsFrom(props.query.data(), firstRecord(props.query.data()).performance);
  const data = () => (items().length ? items() : props.fallbackItems);
  return (
    <section class="strategy-tracking-tab-panel">
      <TabState query={props.query} fallbackText="表现接口暂不可用，已回退到当前列表表现字段。" />
      <DataTable
        data={data().slice(0, 20)}
        columns={[
          { header: "策略", cell: (ctx) => strategyOf(ctx.row.original) },
          { header: "样本", cell: (ctx) => field(ctx.row.original, ["recommendation_count", "active_count", "sample_count"]) },
          { header: "胜率", cell: (ctx) => pctValue(raw(ctx.row.original, ["win_rate_5d", "win_rate_3d", "entry_touch_rate"])) },
          { header: "平均收益", cell: (ctx) => pctValue(raw(ctx.row.original, ["avg_current_return_pct", "current_return_pct"])) },
          { header: "健康", cell: (ctx) => field(ctx.row.original, ["health_grade", "sample_quality", "data_quality"]) },
        ]}
        emptyText="暂无表现数据"
        compact
      />
    </section>
  );
}

function HoldingTab(props: { query: OperationDataState }) {
  const items = () => recordsFrom(props.query.data());
  return (
    <section class="strategy-tracking-tab-panel">
      <TabState query={props.query} fallbackText="持有分析暂不可用。" />
      <Show when={items().length > 0} fallback={<EmptyState text="暂无持有分析数据" />}>
        <div class="strategy-tracking-card-grid">
          <For each={items().slice(0, 8)}>
            {(item) => (
              <article class="strategy-tracking-mini-card">
                <strong>{strategyOf(item)}</strong>
                <span>{field(item, ["conclusion", "dominant_holding_bucket_text"], "暂无结论")}</span>
                <div class="strategy-tracking-bars">
                  <Bar label="短" value={raw(item, ["short_hold_ratio"])} />
                  <Bar label="波" value={raw(item, ["swing_hold_ratio"])} />
                  <Bar label="趋" value={raw(item, ["trend_hold_ratio"])} />
                </div>
              </article>
            )}
          </For>
        </div>
      </Show>
    </section>
  );
}

function DriftTab(props: { review: OperationDataState; fallbackItems: TrackingRecord[] }) {
  const root = () => firstRecord(props.review.data());
  const abnormal = () => recordsFrom(root().abnormal_return_items);
  const needsReview = () => recordsFrom(root().needs_review_items);
  const driftItems = () => (abnormal().length ? abnormal() : needsReview().length ? needsReview() : props.fallbackItems.filter((item) => toneFromRecord(item) === "warn" || toneFromRecord(item) === "danger"));
  return (
    <section class="strategy-tracking-tab-panel">
      <TabState query={props.review} fallbackText="漂移诊断接口暂不可用，已回退到当前筛选结果。" />
      <Show when={driftItems().length > 0} fallback={<EmptyState text="暂无漂移或异常收益样本" />}>
        <div class="strategy-tracking-card-grid">
          <For each={driftItems().slice(0, 6)}>
            {(item) => (
              <article class="strategy-tracking-mini-card">
                <strong>
                  {symbolOf(item)} {strategyOf(item)}
                </strong>
                <span>{field(item, ["failure_reason_text", "review_text", "plain_language_summary"], "等待复盘")}</span>
                <div class="tq-tag-row">
                  <StatusPill label="当前" value={pctValue(raw(item, ["current_return_pct"]))} tone={toneFromRecord(item)} />
                  <StatusPill label="回撤" value={pctValue(raw(item, ["max_drawdown_pct"]))} tone="down" />
                </div>
              </article>
            )}
          </For>
        </div>
      </Show>
    </section>
  );
}

function DiagnosticsTab(props: { query: OperationDataState; selected: TrackingRecord | undefined }) {
  const root = () => firstRecord(props.query.data());
  const failureTags = () => firstRecord(root().failure_tags);
  const segments = () => recordsFrom(root().market_segments);
  return (
    <section class="strategy-tracking-tab-panel">
      <TabState query={props.query} fallbackText="诊断接口暂不可用。" />
      <div class="strategy-tracking-diagnostics-grid">
        <article class="strategy-tracking-mini-card">
          <strong>选中项诊断</strong>
          <Show when={props.selected} fallback={<span>未选中策略跟踪项</span>}>
            <span>{field(props.selected ?? {}, ["review_text", "user_friendly_reason", "plain_language_summary"], "暂无诊断")}</span>
            <pre>{safeJsonPreview(firstRecord(props.selected?.score_components, props.selected?.sector_detail))}</pre>
          </Show>
        </article>
        <article class="strategy-tracking-mini-card">
          <strong>失败标签</strong>
          <Show when={Object.keys(failureTags()).length > 0} fallback={<span>暂无失败标签统计</span>}>
            <div class="tq-tag-row">
              <For each={Object.entries(failureTags()).slice(0, 8)}>
                {([key, value]) => <span class="tq-tag">{`${key}: ${String(value)}`}</span>}
              </For>
            </div>
          </Show>
        </article>
        <article class="strategy-tracking-mini-card strategy-tracking-mini-card--wide">
          <strong>市场状态分层</strong>
          <Show when={segments().length > 0} fallback={<span>暂无市场分层数据</span>}>
            <DataTable
              data={segments().slice(0, 6)}
              columns={[
                { header: "策略", cell: (ctx) => strategyOf(ctx.row.original) },
                { header: "市场", cell: (ctx) => field(ctx.row.original, ["market_state_text", "market_state"]) },
                { header: "板块", cell: (ctx) => field(ctx.row.original, ["sector_state_text", "sector_state"]) },
                { header: "胜率", cell: (ctx) => pctValue(raw(ctx.row.original, ["win_rate_5d"])) },
              ]}
              compact
            />
          </Show>
        </article>
      </div>
    </section>
  );
}

export function TabState(props: { query: OperationDataState; fallbackText: string }) {
  return (
    <>
      <Show when={props.query.pending()}>
        <p class="tq-muted">数据加载中</p>
      </Show>
      <Show when={props.query.error()}>
        <p class="strategy-tracking-warning">{props.fallbackText}</p>
      </Show>
    </>
  );
}

function Bar(props: { label: string; value: unknown }) {
  const pct = () => {
    const numeric = Number(props.value);
    if (!Number.isFinite(numeric)) return 0;
    return Math.max(0, Math.min(100, Math.abs(numeric) <= 1 ? numeric * 100 : numeric));
  };
  return (
    <div class="strategy-tracking-bars__row">
      <span>{props.label}</span>
      <div>
        <i style={{ width: `${pct()}%` }} />
      </div>
      <strong>{pctValue(props.value)}</strong>
    </div>
  );
}
