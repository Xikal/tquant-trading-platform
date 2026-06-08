import { For, Show, type JSX } from "solid-js";
import { Icon as SharedIcon } from "../../shared/ui/Icon";

export type SettingsAccent = "indigo" | "emerald" | "amber" | "rose" | "blue" | "slate";
export type SettingsIconName =
  | "activity"
  | "alert"
  | "check"
  | "chevron"
  | "cpu"
  | "database"
  | "eye"
  | "eyeOff"
  | "info"
  | "key"
  | "layers"
  | "lock"
  | "moon"
  | "phone"
  | "qr"
  | "refresh"
  | "save"
  | "search"
  | "shield"
  | "sliders"
  | "sun"
  | "trend"
  | "unlock"
  | "x";

export function CommandCard(props: { title: string; index: string; icon: SettingsIconName; accent: SettingsAccent; action?: JSX.Element; class?: string; children: JSX.Element }) {
  return (
    <section class={`settings-command-card settings-command-card--${props.accent}${props.class ? ` ${props.class}` : ""}`}>
      <header class="settings-command-card__head">
        <div>
          <span class="settings-command-card__icon"><Icon name={props.icon} /></span>
          <h2>{props.index}. {props.title}</h2>
        </div>
        <Show when={props.action}>{props.action}</Show>
      </header>
      <div class="settings-command-card__body">{props.children}</div>
    </section>
  );
}

export function TextField(props: { label: string; value: string; onInput: (value: string) => void; type?: string; align?: "center"; readonly?: boolean }) {
  return (
    <label class={`settings-command-field${props.align === "center" ? " settings-command-field--center" : ""}`}>
      <span>{props.label}</span>
      <input type={props.type ?? "text"} value={props.value} readonly={props.readonly} onInput={(event) => props.onInput(event.currentTarget.value)} />
    </label>
  );
}

export function SelectField(props: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label class="settings-command-field">
      <span>{props.label}</span>
      <select value={props.value} onChange={(event) => props.onChange(event.currentTarget.value)}>
        <For each={props.options}>{(item) => <option value={item}>{item}</option>}</For>
      </select>
    </label>
  );
}

export function SmallBadge(props: { tone: "ok" | "warn" | "danger"; children: JSX.Element }) {
  return <span class={`settings-command-badge settings-command-badge--${props.tone}`}>{props.children}</span>;
}

export function ScoreBadge(props: { enabled: boolean }) {
  return <SmallBadge tone={props.enabled ? "ok" : "warn"}>安全评分: {props.enabled ? "95" : "70"}/100</SmallBadge>;
}

export function CardFooter(props: { text: string; onSave: () => void }) {
  return (
    <div class="settings-command-card-footer">
      <span>{props.text}</span>
      <button type="button" class="settings-command-button settings-command-button--primary" onClick={props.onSave}>
        <Icon name="save" />
        记录意图
      </button>
    </div>
  );
}

export function ModelBox(props: { title: string; accent: SettingsAccent; fields: { label: string; value: string; onInput: (value: string) => void }[] }) {
  return (
    <div class={`settings-command-model-box settings-command-model-box--${props.accent}`}>
      <strong>{props.title}</strong>
      <div>
        <For each={props.fields}>
          {(field) => <TextField label={field.label} value={field.value} align="center" onInput={field.onInput} />}
        </For>
      </div>
    </div>
  );
}

export function Icon(props: { name: SettingsIconName }) {
  return <SharedIcon name={props.name} class="settings-command-icon" />;
}
