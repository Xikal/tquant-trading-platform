import { For, Show, createEffect, createMemo, createSignal, type JSX } from "solid-js";
import { errorMessage } from "../api/errors";
import { Button } from "./Button";
import { Panel } from "./Panel";
import { StatusPill } from "./StatusPill";

export interface ShadowActionField {
  key: string;
  label: string;
  value: string;
}

export interface ShadowActionPanelProps {
  title: string;
  subtitle?: string;
  actionLabel: string;
  fields: ShadowActionField[];
  confirmText?: string;
  resultTitle?: string;
  class?: string;
  embedded?: boolean;
  beforeFields?: JSX.Element;
  onSubmit?: (draft: Record<string, string>) => Promise<string> | string;
}

export function ShadowActionPanel(props: ShadowActionPanelProps) {
  const fieldSnapshot = createMemo(() => fieldsToDraft(props.fields));
  const fieldSnapshotKey = createMemo(() => stableDraftKey(fieldSnapshot()));
  const [draft, setDraft] = createSignal<Record<string, string>>(fieldSnapshot());
  const [lastFieldSnapshotKey, setLastFieldSnapshotKey] = createSignal(fieldSnapshotKey());
  const [confirmed, setConfirmed] = createSignal(false);
  const [submitting, setSubmitting] = createSignal(false);
  const [result, setResult] = createSignal("等待确认");
  const canSubmit = createMemo(() => !submitting() && Object.values(draft()).some((value) => value.trim().length > 0));

  createEffect(() => {
    const nextKey = fieldSnapshotKey();
    if (nextKey === lastFieldSnapshotKey()) return;
    setDraft(fieldSnapshot());
    setConfirmed(false);
    setSubmitting(false);
    setResult("等待确认");
    setLastFieldSnapshotKey(nextKey);
  });

  function updateDraft(key: string, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
    setConfirmed(false);
    setSubmitting(false);
    setResult("已更新，等待确认");
  }

  async function submitShadowAction() {
    if (submitting()) return;
    if (!confirmed()) {
      setConfirmed(true);
      setResult(props.confirmText ?? "已进入二次确认");
      return;
    }
    setSubmitting(true);
    setResult("处理中");
    try {
      const message = props.onSubmit ? await props.onSubmit(draft()) : `${props.actionLabel} 已记录`;
      setResult(message);
    } catch (error) {
      setResult(`提交失败：${errorMessage(error)}`);
    } finally {
      setSubmitting(false);
    }
  }

  const content = () => (
    <div class="tq-shadow-action" data-testid={`shadow-action-${slug(props.title)}`}>
      {props.beforeFields}
      <div class="tq-shadow-action__fields">
        <For each={props.fields}>
          {(field) => (
            <label class="tq-field">
              <span>{field.label}</span>
              <input
                class="tq-input"
                value={draft()[field.key] ?? ""}
                aria-label={field.label}
                onInput={(event) => updateDraft(field.key, event.currentTarget.value)}
              />
            </label>
          )}
        </For>
      </div>
      <div class="tq-shadow-action__footer">
        <div class="tq-tag-row">
          <Show when={confirmed()} fallback={<StatusPill label="确认" value="待确认" />}>
            <StatusPill label="确认" value="已确认" tone="up" />
          </Show>
        </div>
        <Button variant="primary" onClick={submitShadowAction} disabled={!canSubmit()} aria-label={submitting() ? `${props.actionLabel}处理中` : undefined}>
          {submitting() ? "处理中" : confirmed() ? props.actionLabel : "确认"}
        </Button>
      </div>
      <div class="execution-log" aria-live="polite">
        <div class="execution-log__item">
          <strong>{props.resultTitle ?? "交互结果"}：</strong>
          <span>{result()}</span>
        </div>
      </div>
    </div>
  );

  if (props.embedded) {
    return (
      <div class={`tq-shadow-action-card${props.class ? ` ${props.class}` : ""}`}>
        <div class="tq-shadow-action-card__head">
          <h3>{props.title}</h3>
          <Show when={props.subtitle}>
            <p>{props.subtitle}</p>
          </Show>
        </div>
        {content()}
      </div>
    );
  }

  return (
    <Panel title={props.title} subtitle={props.subtitle} class={`tq-page__full${props.class ? ` ${props.class}` : ""}`}>
      {content()}
    </Panel>
  );
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^\p{Letter}\p{Number}]+/gu, "-").replace(/(^-|-$)/g, "") || "panel";
}

function fieldsToDraft(fields: ShadowActionField[]): Record<string, string> {
  return Object.fromEntries(fields.map((field) => [field.key, field.value]));
}

function stableDraftKey(draft: Record<string, string>): string {
  return Object.keys(draft).sort().map((key) => `${key}:${draft[key]}`).join("|");
}
