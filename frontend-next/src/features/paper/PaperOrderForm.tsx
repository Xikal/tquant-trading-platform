import { createEffect, createMemo, createSignal, For, Show } from "solid-js";
import { errorMessage } from "../../shared/api/errors";
import { mutationClient } from "../../shared/api/mutations";
import { Button } from "../../shared/ui/Button";
import { Panel } from "../../shared/ui/Panel";
import { Segmented } from "../../shared/ui/Segmented";
import { StatusPill } from "../../shared/ui/StatusPill";
import { paperOrderPayload } from "../shared/mutationPayloads";
import { numberText, text } from "../shared/dataAccess";
import { mergePaperOrderDraft, normalizePaperSymbol, type PaperOrderDraft, type PaperOrderSide, type PaperOrderType } from "./paperOrderDraft";

export function PaperOrderForm(props: { orders: Record<string, unknown>[]; positions: Record<string, unknown>[]; embedded?: boolean; initialDraft?: Partial<PaperOrderDraft> | null; draftKey?: string }) {
  const [draft, setDraft] = createSignal<PaperOrderDraft>(mergePaperOrderDraft(props.initialDraft));
  const [confirmed, setConfirmed] = createSignal(false);
  const [result, setResult] = createSignal("等待确认");
  const [submitting, setSubmitting] = createSignal(false);
  const [lastDraftKey, setLastDraftKey] = createSignal(props.draftKey ?? "");
  const quantity = createMemo(() => positiveNumber(draft().quantity));
  const orderPrice = createMemo(() => positiveNumber(draft().price));
  const recommendation = createMemo(() => props.orders[0] ?? props.positions[0] ?? null);
  const matchingPosition = createMemo(() => {
    const symbol = normalizePaperSymbol(draft().symbol);
    return props.positions.find((position) => normalizePaperSymbol(text(position.symbol)) === symbol) ?? null;
  });
  const positionQuantity = createMemo(() => positiveNumber(matchingPosition()?.available_quantity ?? matchingPosition()?.available ?? matchingPosition()?.quantity));
  const estimate = createMemo(() => estimateOrderCost(draft().side, quantity(), orderPrice()));
  const canSubmit = createMemo(() => normalizePaperSymbol(draft().symbol).length === 6 && quantity() > 0 && (draft().order_type === "market" || orderPrice() > 0));

  createEffect(() => {
    const nextDraftKey = props.draftKey ?? "";
    if (!nextDraftKey || nextDraftKey === lastDraftKey()) return;
    setDraft(mergePaperOrderDraft(props.initialDraft));
    setConfirmed(false);
    setResult("分析结果已导入草稿");
    setLastDraftKey(nextDraftKey);
  });

  function updateDraft(key: keyof PaperOrderDraft, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
    setConfirmed(false);
    setResult("已更新，等待确认");
  }

  function importRecommendation() {
    const source = recommendation() ?? {};
    const price = source.price ?? source.avg_fill_price ?? source.latest_price ?? source.cost_basis ?? draft().price;
    setDraft((current) => ({
      ...current,
      side: source.side === "sell" ? "sell" : current.side,
      symbol: normalizePaperSymbol(text(source.symbol, current.symbol)),
      name: text(source.name ?? source.stock_name, current.name),
      quantity: text(source.quantity ?? source.available_quantity ?? current.quantity, current.quantity),
      price: text(price, current.price),
      strategy_key: text(source.strategy_key, current.strategy_key),
      reason: text(source.reason ?? source.entry_reason ?? current.reason, current.reason),
    }));
    setConfirmed(false);
    setResult(recommendation() ? "推荐已导入草稿" : "暂无推荐数据，保留手工草稿");
  }

  function importPosition(position: Record<string, unknown>) {
    setDraft((current) => ({
      ...current,
      side: "sell",
      symbol: normalizePaperSymbol(text(position.symbol, current.symbol)),
      name: text(position.name ?? position.stock_name, current.name),
      quantity: text(position.available_quantity ?? position.available ?? position.quantity, current.quantity),
      price: text(position.latest_price ?? position.cost_basis ?? current.price, current.price),
      strategy_key: text(position.strategy_key, current.strategy_key),
      reason: "持仓卖出复盘",
    }));
    setConfirmed(false);
    setResult("持仓已导入草稿");
  }

  function applyQuantity(nextQuantity: number) {
    updateDraft("quantity", String(Math.max(100, roundToLot(nextQuantity))));
  }

  function applyPositionRatio(ratio: number) {
    if (!positionQuantity()) return;
    applyQuantity(positionQuantity() * ratio);
  }

  async function submitOrder() {
    if (!canSubmit()) {
      setResult("代码和数量为必填项");
      return;
    }
    if (!confirmed()) {
      setConfirmed(true);
      setResult("模拟委托已进入二次确认");
      return;
    }
    setSubmitting(true);
    try {
      const result = await mutationClient.createPaperOrder(paperOrderPayload({ ...draft() }));
      setResult(result.mode === "live" ? "提交委托已发送" : "提交委托已记录");
    } catch (error) {
      setResult(`提交失败：${errorMessage(error)}`);
    } finally {
      setSubmitting(false);
    }
  }

  const form = () => (
      <div class="paper-order-form" data-testid="paper-order-form">
        <div class="paper-order-form__toolbar">
          <Segmented<PaperOrderSide>
            label="买卖方向"
            value={draft().side}
            onChange={(value) => updateDraft("side", value)}
            options={[
              { value: "buy", label: "买入" },
              { value: "sell", label: "卖出" },
            ]}
          />
          <Segmented<PaperOrderType>
            label="委托类型"
            value={draft().order_type}
            onChange={(value) => updateDraft("order_type", value)}
            options={[
              { value: "limit", label: "限价" },
              { value: "market", label: "市价" },
            ]}
          />
          <Button variant="subtle" onClick={importRecommendation}>
            导入推荐
          </Button>
        </div>

        <div class="paper-order-form__fields">
          <label class="tq-field">
            <span>代码</span>
            <input class="tq-input" value={draft().symbol} aria-label="代码" onInput={(event) => updateDraft("symbol", event.currentTarget.value)} />
          </label>
          <label class="tq-field">
            <span>名称</span>
            <input class="tq-input" value={draft().name} aria-label="名称" onInput={(event) => updateDraft("name", event.currentTarget.value)} />
          </label>
          <label class="tq-field">
            <span>数量</span>
            <input class="tq-input" inputMode="numeric" value={draft().quantity} aria-label="数量" onInput={(event) => updateDraft("quantity", event.currentTarget.value)} />
          </label>
          <label class="tq-field">
            <span>价格</span>
            <input class="tq-input" inputMode="decimal" value={draft().price} aria-label="价格" onInput={(event) => updateDraft("price", event.currentTarget.value)} disabled={draft().order_type === "market"} />
          </label>
          <label class="tq-field">
            <span>策略</span>
            <input class="tq-input" value={draft().strategy_key} aria-label="策略" onInput={(event) => updateDraft("strategy_key", event.currentTarget.value)} />
          </label>
          <label class="tq-field paper-order-form__reason">
            <span>理由</span>
            <input class="tq-input" value={draft().reason} aria-label="理由" onInput={(event) => updateDraft("reason", event.currentTarget.value)} />
          </label>
        </div>

        <div class="paper-order-form__assist">
          <div class="paper-order-form__quick">
            <span>数量快捷</span>
            <Button size="sm" onClick={() => applyQuantity(quantity() + 100)}>+100</Button>
            <Button size="sm" onClick={() => applyQuantity(quantity() + 500)}>+500</Button>
            <Button size="sm" onClick={() => applyQuantity(quantity() + 1000)}>+1000</Button>
            <Button size="sm" disabled={!positionQuantity()} onClick={() => applyPositionRatio(0.25)}>1/4 仓</Button>
            <Button size="sm" disabled={!positionQuantity()} onClick={() => applyPositionRatio(0.5)}>1/2 仓</Button>
            <Button size="sm" disabled={!positionQuantity()} onClick={() => applyPositionRatio(1)}>全仓</Button>
          </div>
          <Show when={props.positions.length}>
            <div class="paper-order-form__positions" aria-label="持仓导入">
              <For each={props.positions.slice(0, 4)}>
                {(position) => (
                  <button type="button" onClick={() => importPosition(position)}>
                    <strong>{text(position.symbol)}</strong>
                    <span>{text(position.name ?? position.stock_name, "")}</span>
                    <small>可用 {text(position.available_quantity ?? position.available ?? position.quantity, "--")}</small>
                  </button>
                )}
              </For>
            </div>
          </Show>
        </div>

        <div class="paper-order-form__review" aria-label="委托二次确认摘要">
          <StatusPill label="确认" value={confirmed() ? "已确认" : "待确认"} tone={confirmed() ? "up" : "warn"} />
          <span>
            {draft().side === "buy" ? "买入" : "卖出"} {draft().symbol || "--"} · {draft().quantity || "--"} 股 · {draft().order_type === "market" ? "市价" : `限价 ${draft().price || "--"}`}
          </span>
          <span>
            金额 {moneyText(estimate().grossAmount)} · 费用 {moneyText(estimate().fees)} · {draft().side === "buy" ? "预计占用" : "预计回收"} {moneyText(estimate().netAmount)}
          </span>
        </div>

        <div class="paper-order-form__footer">
          <StatusPill label="模式" value="本地确认" tone="info" />
          <Button variant="primary" onClick={submitOrder} disabled={!canSubmit() || submitting()}>
            <Show when={confirmed()} fallback="确认">
              提交委托
            </Show>
          </Button>
        </div>

        <div class="execution-log" aria-live="polite">
          <div class="execution-log__item">
            <strong>委托状态：</strong>
            <span>{result()}</span>
          </div>
        </div>
      </div>
  );

  if (props.embedded) {
    return form();
  }

  return (
    <Panel
      title="模拟委托"
      actions={<StatusPill label="状态" value="待确认" tone="info" />}
      class="paper-order-preview tq-page__full"
    >
      {form()}
    </Panel>
  );
}

function positiveNumber(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function roundToLot(value: number): number {
  return Math.floor(value / 100) * 100;
}

function estimateOrderCost(side: PaperOrderSide, quantity: number, price: number) {
  const grossAmount = quantity * price;
  const commission = grossAmount > 0 ? Math.max(grossAmount * 0.0003, 5) : 0;
  const stampTax = side === "sell" ? grossAmount * 0.0005 : 0;
  const transferFee = grossAmount * 0.00001;
  const fees = commission + stampTax + transferFee;
  return {
    grossAmount,
    fees,
    netAmount: side === "buy" ? grossAmount + fees : Math.max(0, grossAmount - fees),
  };
}

function moneyText(value: number): string {
  return Number.isFinite(value) && value > 0 ? numberText(value, "--") : "--";
}
