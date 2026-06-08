import { For, Show, createSignal } from "solid-js";
import { mutationClient } from "../../shared/api/mutations";
import { Button } from "../../shared/ui/Button";
import { ShadowActionPanel } from "../../shared/ui/ShadowActionPanel";
import { genericMutationPayload } from "../shared/mutationPayloads";
import { field, pctValue, raw, recordsFrom, strategyOf, symbolOf, type OperationDataState, type TrackingRecord } from "./strategyTrackingModel";
import { TabState } from "./StrategyTrackingTabs";

export function StrategyTrackingReviewCenter(props: {
  journal: OperationDataState;
  relativeStrength: OperationDataState;
  selected: TrackingRecord | undefined;
}) {
  const [actionResult, setActionResult] = createSignal("编辑和删除会先记录为待确认动作");
  const journalItems = () => recordsFrom(props.journal.data());
  const rsItems = () => recordsFrom(props.relativeStrength.data());
  const selectedSymbol = () => (props.selected ? symbolOf(props.selected) : "");
  return (
    <section class="strategy-tracking-tab-panel strategy-tracking-review-center" data-testid="strategy-tracking-review-center">
      <div class="strategy-tracking-review-grid">
        <ShadowActionPanel
          title="复盘记录"
          actionLabel="记录复盘"
          resultTitle="复盘动作"
          fields={[
            { key: "strategy", label: "策略", value: props.selected ? strategyOf(props.selected) : "N形洗盘低吸" },
            { key: "symbol", label: "代码", value: selectedSymbol() },
            { key: "verdict", label: "结论", value: "继续观察" },
            { key: "reason", label: "原因", value: "等待样本外验证" },
          ]}
          confirmText="复盘结论已进入二次确认"
          onSubmit={async (draft) => {
            const result = await mutationClient.recordStrategyReviewShadow(genericMutationPayload(draft));
            return result.mode === "live" ? "记录复盘已发送" : "记录复盘已记录";
          }}
        />
        <ShadowActionPanel
          title="交易日志"
          actionLabel="提交日志"
          resultTitle="交易日志动作"
          fields={[
            { key: "symbol", label: "代码", value: selectedSymbol() },
            { key: "action", label: "动作", value: "note" },
            { key: "reason_text", label: "复盘理由", value: "纪律记录，仅用于复盘" },
            { key: "signal_source", label: "来源", value: "本地复盘" },
          ]}
          confirmText="交易日志已进入二次确认"
          onSubmit={async (draft) => {
            const result = await mutationClient.createTradeJournalShadow({
              symbol: draft.symbol || selectedSymbol(),
              action: normalizeJournalAction(draft.action),
              reason_text: draft.reason_text || draft.reason || "纪律记录，仅用于复盘",
              signal_source: draft.signal_source || "frontend-next-shadow",
            });
            return result.mode === "live" ? "交易日志已发送" : "交易日志已本地记录，正式保存待复验后开启";
          }}
        />
      </div>
      <div class="strategy-tracking-review-actions">
        <Button size="sm" onClick={() => setActionResult("编辑日志已本地记录，正式保存待复验后开启")}>
          编辑日志
        </Button>
        <Button size="sm" variant="danger" onClick={() => setActionResult("删除日志已本地记录，正式保存待复验后开启")}>
          删除日志
        </Button>
        <span aria-live="polite">{actionResult()}</span>
      </div>
      <div class="strategy-tracking-diagnostics-grid">
        <article class="strategy-tracking-mini-card">
          <strong>纪律日志</strong>
          <TabState query={props.journal} fallbackText="交易日志读取暂不可用。" />
          <Show when={journalItems().length > 0} fallback={<span>暂无日志记录</span>}>
            <For each={journalItems().slice(0, 5)}>
              {(entry) => <span>{`${symbolOf(entry)} · ${field(entry, ["action"])} · ${field(entry, ["reason_text"], "无理由")}`}</span>}
            </For>
          </Show>
        </article>
        <article class="strategy-tracking-mini-card">
          <strong>抗跌事实</strong>
          <TabState query={props.relativeStrength} fallbackText="抗跌事实读取暂不可用。" />
          <Show when={rsItems().length > 0} fallback={<span>暂无相对强弱数据</span>}>
            <For each={rsItems().slice(0, 5)}>
              {(item) => (
                <span>
                  {symbolOf(item)} · 个股 {pctValue(raw(item, ["stock_pct"]))} · 相对板块 {pctValue(raw(item, ["rs_vs_sector"]))}
                </span>
              )}
            </For>
          </Show>
        </article>
      </div>
    </section>
  );
}

function normalizeJournalAction(value: string): "buy" | "sell" | "trim" | "add" | "t_trade" | "note" {
  if (value === "buy" || value === "sell" || value === "trim" || value === "add" || value === "t_trade" || value === "note") return value;
  return "note";
}
