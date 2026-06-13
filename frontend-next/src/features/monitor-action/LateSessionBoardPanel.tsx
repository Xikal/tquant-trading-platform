import { createQuery } from "@tanstack/solid-query";
import { For, Show, createMemo } from "solid-js";
import { apiClient } from "../../shared/api/client";
import { queryKeys } from "../../shared/api/queryKeys";
import { createLateSessionBoardModel } from "./lateSessionBoardModel";

export function LateSessionBoardPanel() {
  const query = createQuery(() => ({
    queryKey: queryKeys.lateSessionBoard("latest"),
    queryFn: ({ signal }) => apiClient.lateSessionBoard({ limit: 12, slot: "latest", refresh: "cache", signal }),
    staleTime: 8_000,
  }));
  const model = createMemo(() => createLateSessionBoardModel(query.data));

  return (
    <section class="monitor-card monitor-card--late-session" data-testid="late-session-board-panel">
      <header class="monitor-card__header">
        <div class="monitor-card__title-row">
          <span class="monitor-icon-chip monitor-icon-chip--blue">尾</span>
          <h3>尾盘推荐榜</h3>
        </div>
        <div class="monitor-late-session__meta">
          <span>{model().slotLabel}</span>
          <strong>{model().statusText}</strong>
        </div>
      </header>

      <Show when={query.isError}>
        <div class="monitor-late-session__empty">尾盘榜接口异常，当前仅保留原优先榜。</div>
      </Show>
      <Show when={!query.isError}>
        <div class="monitor-late-session__summary">
          <span>确认 {model().confirmedCount}</span>
          <span>观察 {model().watchCount}</span>
          <span>{model().generatedAt.slice(0, 19) || "--"}</span>
          <Show when={model().degradationText}>
            <em>{model().degradationText}</em>
          </Show>
        </div>
        <Show when={model().items.length > 0} fallback={<div class="monitor-late-session__empty">{model().emptyText}</div>}>
          <div class="monitor-late-session__list">
            <For each={model().items}>
              {(item) => (
                <article class={`monitor-late-session-row monitor-late-session-row--${item.state}`}>
                  <span class="monitor-late-session-row__order">{String(item.order + 1).padStart(2, "0")}</span>
                  <div class="monitor-late-session-row__main">
                    <strong>{item.name || item.symbol}</strong>
                    <small>{item.symbol} · {item.strategy}</small>
                    <p>{item.reason}</p>
                  </div>
                  <div class="monitor-late-session-row__facts">
                    <span>{item.stateLabel}</span>
                    <small>分 {item.score}</small>
                    <small>价 {item.price}</small>
                    <small>VWAP {item.vwap}</small>
                  </div>
                </article>
              )}
            </For>
          </div>
        </Show>
      </Show>
    </section>
  );
}
