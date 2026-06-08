import { For, Show } from "solid-js";

export interface StockCardItem {
  symbol: string;
  name?: string;
  priceText?: string;
  changeText?: string;
  scoreText?: string;
  actionText?: string;
  riskText?: string;
  details?: string;
  badges?: string[];
}

export function StockCard(props: { item: StockCardItem }) {
  const tone = () => changeTone(props.item.changeText);
  const risk = () => riskTone(props.item.riskText);
  return (
    <article class={`tq-stock-card tq-stock-card--wide tq-stock-card--tone-${tone()}`}>
      <div class="tq-stock-identity">
        <div class="tq-stock-identity__main">
          <strong class="tq-stock-identity__name">{props.item.name || props.item.symbol}</strong>
          <span class="tq-stock-identity__meta">{props.item.symbol}</span>
        </div>
        <Show when={props.item.badges?.length}>
          <div class="tq-stock-identity__tags">
            <For each={(props.item.badges ?? []).slice(0, 2)}>{(badge) => <span class="tq-stock-identity__tag">{badge}</span>}</For>
          </div>
        </Show>
      </div>
      <div class="tq-stock-card__body">
        <div class="tq-stock-card__direct-action">
          <strong class="tq-stock-card__direct-action-title">{props.item.actionText ?? "观察"}</strong>
          <span class="tq-stock-card__score tnum">{props.item.scoreText ?? props.item.priceText ?? "--"}</span>
        </div>
        <div class="tq-stock-card__meta">
          <span>当前价 {props.item.priceText ?? "--"}</span>
          <Show when={props.item.changeText}>
            <span class={`tq-stock-card__meta--${tone()}`}>涨跌 {props.item.changeText}</span>
          </Show>
          <Show when={props.item.riskText}>
            <span class={`tq-stock-card__badge tq-stock-card__risk tq-stock-card__risk--${risk()}`}>风险 {props.item.riskText}</span>
          </Show>
        </div>
        <Show when={props.item.details}>
          <div class="tq-stock-card__execution-hint">{props.item.details}</div>
        </Show>
      </div>
    </article>
  );
}

function changeTone(value?: string): "up" | "down" | "warn" | "neutral" {
  const text = value ?? "";
  if (text.startsWith("-") || text.includes("跌")) return "down";
  if (text.includes("警") || text.includes("降级")) return "warn";
  if (text && text !== "--") return "up";
  return "neutral";
}

function riskTone(value?: string): "danger" | "warn" | "success" | "neutral" {
  const text = value ?? "";
  if (text.includes("高") || text.includes("阻断")) return "danger";
  if (text.includes("中") || text.includes("注意") || text.includes("降级")) return "warn";
  if (text.includes("低") || text.includes("正常") || text.includes("清晰")) return "success";
  return "neutral";
}
