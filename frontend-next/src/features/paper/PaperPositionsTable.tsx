import { For, Show } from "solid-js";
import { readRecord, text } from "../shared/dataAccess";

export function PaperPositionsTable(props: { positions: Record<string, unknown>[]; isPending: boolean; isError: boolean }) {
  return (
    <div class="paper-positions-embedded">
      <div class="paper-positions-embedded__header">
        <strong>当前持仓</strong>
        <span class="tq-muted">{paperDataStatus(props.isPending, props.isError, props.positions.length)}</span>
      </div>
      <div class="paper-positions-embedded__body">
        <Show
          when={props.positions.length}
          fallback={<div class="tq-empty-state paper-positions-empty">{props.isPending ? "正在读取模拟盘持仓" : "暂无模拟持仓"}</div>}
        >
          <div class="paper-position-card-grid">
            <For each={props.positions}>{(item) => <PositionCard item={item} />}</For>
          </div>
        </Show>
      </div>
    </div>
  );
}

function PositionCard(props: { item: Record<string, unknown> }) {
  const item = () => props.item;
  const pnl = () => item().unrealized_pnl_pct ?? item().unrealized_pnl ?? item().pnl;
  const tone = () => pnlTone(pnl());
  return (
    <article class={`paper-position-card paper-position-card--${tone()}`} style={{ "box-shadow": `inset 3px 0 0 ${toneColor(tone())}` }}>
      <strong class="paper-position-card__line paper-position-card__line--identity">
        {text(item().name ?? item().stock_name ?? item().symbol)} / {text(item().symbol)}
      </strong>
      <span class="paper-position-card__line">
        持/可 {text(item().quantity ?? item().shares)} / {text(item().available_quantity ?? item().available)}
      </span>
      <span class="paper-position-card__line">
        成本/现价 {text(item().cost_basis ?? item().avg_cost)} / {text(item().latest_price ?? item().last_price)}
      </span>
      <strong class="paper-position-card__line" style={{ color: toneColor(tone()) }}>
        盈亏 {text(item().unrealized_pnl_pct ?? item().unrealized_pnl ?? item().pnl)}
      </strong>
      <span class="paper-position-card__line">{text(item().smart_exit_text ?? readRecord(item().exit_model_shadow).action, "观察")}</span>
    </article>
  );
}

function paperDataStatus(isPending: boolean, isError: boolean, positionCount: number): string {
  if (isPending) return "正在加载";
  if (isError) return "接口暂不可用";
  return positionCount ? `${positionCount} 个标的` : "暂无持仓";
}

function pnlTone(value: unknown): "up" | "down" | "neutral" {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed === 0) return "neutral";
  return parsed > 0 ? "up" : "down";
}

function toneColor(tone: string): string {
  if (tone === "up") return "var(--price-up)";
  if (tone === "down") return "var(--price-down)";
  return "var(--text-1)";
}
