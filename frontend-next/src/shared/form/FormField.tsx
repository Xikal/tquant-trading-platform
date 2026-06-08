import { Show, splitProps, type JSX } from "solid-js";

export interface FormFieldProps extends JSX.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
  inputClass?: string;
  fieldClass?: string;
}

export function FormField(allProps: FormFieldProps) {
  const [local, inputProps] = splitProps(allProps, ["label", "hint", "error", "inputClass", "fieldClass", "id"]);
  const id = () => local.id ?? stableFieldId(local.label);
  const hintId = () => `${id()}-hint`;
  const errorId = () => `${id()}-error`;
  const describedBy = () => [local.hint ? hintId() : undefined, local.error ? errorId() : undefined].filter(Boolean).join(" ") || undefined;

  return (
    <label class={`tq-field${local.fieldClass ? ` ${local.fieldClass}` : ""}`} for={id()}>
      <span>{local.label}</span>
      <input
        {...inputProps}
        id={id()}
        class={`tq-input${local.inputClass ? ` ${local.inputClass}` : ""}`}
        aria-invalid={local.error ? "true" : undefined}
        aria-describedby={describedBy()}
      />
      <Show when={local.hint}>
        <span id={hintId()} class="tq-muted">
          {local.hint}
        </span>
      </Show>
      <Show when={local.error}>
        <span id={errorId()} style={{ color: "var(--error)", "font-size": "var(--font-micro)" }}>
          {local.error}
        </span>
      </Show>
    </label>
  );
}

function stableFieldId(label: string): string {
  return `field-${label.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-").replace(/(^-|-$)/g, "")}`;
}
