import { For, Show } from "solid-js";
import { Button } from "../../shared/ui/Button";
import { Drawer } from "../../shared/ui/Drawer";
import { EmptyState } from "../../shared/ui/EmptyState";
import { StatusPill } from "../../shared/ui/StatusPill";
import {
  calloutClass,
  chips,
  field,
  firstRecord,
  idOf,
  nameOf,
  numericText,
  pctValue,
  raw,
  recordsFrom,
  safeJsonPreview,
  strategyOf,
  symbolOf,
  toneFromRecord,
  type OperationDataState,
  type TrackingRecord,
} from "./strategyTrackingModel";

export function StrategyTrackingDetailPanel(props: {
  open: boolean;
  selected: TrackingRecord | undefined;
  detail: OperationDataState;
  onClose: () => void;
}) {
  const detailRoot = () => firstRecord(props.detail.data());
  const detailItem = () => firstRecord(detailRoot().item, props.selected);
  const timeline = () => recordsFrom(detailRoot().timeline);
  const markers = () => recordsFrom(detailRoot().markers);
  const selectedTitle = () => {
    const item = detailItem();
    return `${symbolOf(item)} ${nameOf(item) || strategyOf(item)}`;
  };

  return (
    <Drawer
      open={props.open}
      title={<span>策略详情 · {selectedTitle()}</span>}
      onClose={props.onClose}
      width={520}
      footer={<Button onClick={props.onClose}>关闭</Button>}
    >
      <Show when={props.selected} fallback={<EmptyState text="未找到选中项，已回退到列表视图" />}>
        <div class="strategy-tracking-detail" data-testid="strategy-tracking-detail-panel">
          <Show when={props.detail.error()}>
            <div class="strategy-tracking-warning">详情接口暂不可用，当前展示列表中的安全摘要。</div>
          </Show>
          <Show when={props.detail.pending()}>
            <p class="tq-muted">详情加载中</p>
          </Show>
          <section class="strategy-tracking-detail__hero">
            <div>
              <strong>{selectedTitle()}</strong>
              <span>{field(detailItem(), ["plain_language_summary", "user_friendly_reason", "review_text"], "暂无详情说明")}</span>
            </div>
            <StatusPill label="状态" value={field(detailItem(), ["signal_text", "signal_state", "status"])} tone={toneFromRecord(detailItem())} />
          </section>
          <section class="strategy-tracking-callout-grid">
            <Metric label="当前收益" value={pctValue(raw(detailItem(), ["current_return_pct", "return_pct"]))} tone={toneFromRecord(detailItem())} />
            <Metric label="最大涨幅" value={pctValue(raw(detailItem(), ["max_gain_pct", "best_exit_return_pct"]))} tone="up" />
            <Metric label="最大回撤" value={pctValue(raw(detailItem(), ["max_drawdown_pct", "best_exit_drawdown_pct"]))} tone="down" />
            <Metric label="持有天数" value={numericText(detailItem(), ["best_holding_days"], " 天")} />
          </section>
          <section class="strategy-tracking-detail__section">
            <h3>交易边界</h3>
            <div class="strategy-tracking-kv">
              <span>入场区间</span>
              <strong>
                {numericText(detailItem(), ["entry_zone_low", "entry_price"])} / {numericText(detailItem(), ["entry_zone_high", "target_price"])}
              </strong>
              <span>止损 / 目标</span>
              <strong>
                {numericText(detailItem(), ["stop_loss"])} / {numericText(detailItem(), ["target_price"])}
              </strong>
              <span>生产状态</span>
              <strong>{field(detailItem(), ["production_decision", "readiness_status", "production_enabled"])}</strong>
              <span>数据状态</span>
              <strong>{field(detailItem(), ["data_quality_text", "data_quality", "future_leak_check"])}</strong>
            </div>
          </section>
          <section class="strategy-tracking-detail__section">
            <h3>解释标签</h3>
            <Show when={chips(detailItem(), ["warning_tags", "failure_tags", "hold_extension_reasons", "readiness_blockers"], 8).length} fallback={<p class="tq-muted">暂无解释标签</p>}>
              <div class="tq-tag-row">
                <For each={chips(detailItem(), ["warning_tags", "failure_tags", "hold_extension_reasons", "readiness_blockers"], 8)}>{(chip) => <span class="tq-tag">{chip}</span>}</For>
              </div>
            </Show>
          </section>
          <section class="strategy-tracking-detail__section">
            <h3>时间线</h3>
            <Show when={timeline().length > 0} fallback={<p class="tq-muted">暂无时间线数据</p>}>
              <div class="strategy-tracking-timeline">
                <For each={timeline().slice(0, 8)}>
                  {(point) => (
                    <div class="strategy-tracking-timeline__item">
                      <strong>{field(point, ["trade_date", "date", "as_of"])}</strong>
                      <span>
                        收盘 {numericText(point, ["close"])} / 收益 {pctValue(raw(point, ["current_return_pct", "pct_chg"]))}
                      </span>
                    </div>
                  )}
                </For>
              </div>
            </Show>
          </section>
          <section class="strategy-tracking-detail__section">
            <h3>标记 / 上下文</h3>
            <Show when={markers().length > 0} fallback={<pre>{safeJsonPreview(detailRoot().decision_context ?? detailRoot().signal_snapshot ?? { selected_id: idOf(detailItem()) })}</pre>}>
              <div class="tq-tag-row">
                <For each={markers()}>{(marker) => <span class="tq-tag">{field(marker, ["label", "kind", "trade_date"])}</span>}</For>
              </div>
            </Show>
          </section>
        </div>
      </Show>
    </Drawer>
  );
}

function Metric(props: { label: string; value: string; tone?: "up" | "down" | "warn" | "danger" | "neutral" }) {
  return (
    <div class={calloutClass(props.tone)}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}
