import type { CSSProperties, ChangeEvent, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { useEffect, useId, useRef } from "react";
import { Form, Input, Select, Slider } from "antd";
import { strategiesApi, type SymbolSearchItem } from "../../api/strategies";
import { useSharedUiStore } from "../../stores/sharedUiStore";

const EMPTY_SEARCH_RESULT = {
  items: [] as SymbolSearchItem[],
  total: 0,
  open: false,
  error: "",
};

const FIELD_FRAME_STYLE: CSSProperties = {
  minWidth: 0,
  marginBottom: 0,
};

const FIELD_LABEL_STYLE: CSSProperties = {
  color: "#62708a",
  fontSize: 12,
  fontWeight: 700,
};

const FIELD_EXTRA_STYLE: CSSProperties = {
  color: "#7b879d",
  fontSize: 11,
};

const FIELD_CONTROL_STYLE: CSSProperties = {
  minHeight: 34,
  borderRadius: 10,
  background: "#f8fafc",
  color: "#0f172a",
};

const NUMBER_INPUT_WRAP_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  minHeight: 34,
  border: "1px solid #dbe3ef",
  borderRadius: 10,
  background: "#f8fafc",
  padding: "0 11px",
};

const NUMBER_INPUT_STYLE: CSSProperties = {
  flex: 1,
  minHeight: 32,
  border: 0,
  boxShadow: "none",
  background: "transparent",
  padding: 0,
};

const INPUT_SUFFIX_STYLE: CSSProperties = {
  color: "#7b879d",
  fontSize: 12,
};

const SLIDER_FIELD_STYLE: CSSProperties = {
  ...FIELD_FRAME_STYLE,
  border: "1px solid #e3e9f2",
  borderRadius: 12,
  background: "#f8fafc",
  padding: "10px 12px",
};

const SLIDER_LABEL_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 8,
  width: "100%",
  ...FIELD_LABEL_STYLE,
};

const SEARCH_FIELD_STYLE: CSSProperties = {
  position: "relative",
};

const SEARCH_POPOVER_STYLE: CSSProperties = {
  position: "absolute",
  zIndex: 20,
  top: "calc(100% + 6px)",
  right: 0,
  left: 0,
  maxHeight: 260,
  overflow: "auto",
  border: "1px solid #dbe3ef",
  borderRadius: 12,
  background: "#fff",
  boxShadow: "0 16px 32px rgba(15, 23, 42, 0.12)",
};

const SEARCH_OPTION_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "74px 1fr auto",
  alignItems: "center",
  gap: 4,
  width: "100%",
  border: 0,
  borderBottom: "1px solid #eef2f7",
  background: "transparent",
  color: "#0f172a",
  cursor: "pointer",
  padding: "9px 11px",
  textAlign: "left",
};

const SEARCH_MESSAGE_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 12,
  padding: "9px 11px",
};

const SEARCH_ERROR_STYLE: CSSProperties = {
  ...SEARCH_MESSAGE_STYLE,
  color: "#b91c1c",
};

interface FieldFrameProps {
  label: string;
  hint?: string;
  error?: string;
  className?: string;
  children: ReactNode;
}

function FieldFrame({ label, hint, error, className = "", children }: FieldFrameProps) {
  return (
    <Form.Item
      className={className || undefined}
      style={FIELD_FRAME_STYLE}
      label={<span style={FIELD_LABEL_STYLE}>{label}</span>}
      validateStatus={error ? "error" : undefined}
      help={error || undefined}
      extra={!error && hint ? <span style={FIELD_EXTRA_STYLE}>{hint}</span> : undefined}
    >
      {children}
    </Form.Item>
  );
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
  fieldClassName?: string;
};

export function TextField({ label, hint, error, fieldClassName = "", className = "", size: _nativeSize, style, ...props }: TextFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <Input className={className || undefined} style={{ ...FIELD_CONTROL_STYLE, ...style }} {...props} />
    </FieldFrame>
  );
}

export function DateField(props: TextFieldProps) {
  return <TextField {...props} type="date" />;
}

type NumberFieldProps = TextFieldProps & {
  suffix?: string;
};

export function NumberField({ label, hint, error, suffix, fieldClassName = "", className = "", size: _nativeSize, style, ...props }: NumberFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <span style={NUMBER_INPUT_WRAP_STYLE}>
        <Input className={className || undefined} style={{ ...NUMBER_INPUT_STYLE, ...style }} {...props} type="number" />
        {suffix ? <span style={INPUT_SUFFIX_STYLE}>{suffix}</span> : null}
      </span>
    </FieldFrame>
  );
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: string;
  error?: string;
  fieldClassName?: string;
  options: Array<{ value: string; label: string }>;
};

export function SelectField({ label, hint, error, options, fieldClassName = "", className = "", value, disabled, onChange, style, ...props }: SelectFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <Select
        className={className || undefined}
        style={{ width: "100%", ...FIELD_CONTROL_STYLE, ...style }}
        value={String(value ?? "")}
        disabled={disabled}
        options={options}
        onChange={(nextValue) => {
          onChange?.({ target: { value: String(nextValue) } } as ChangeEvent<HTMLSelectElement>);
        }}
        aria-label={props["aria-label"] || label}
      />
    </FieldFrame>
  );
}

type SliderFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  value: string | number;
  suffix?: string;
  onValueChange: (value: string) => void;
};

export function SliderField({ label, value, suffix, onValueChange, ...props }: SliderFieldProps) {
  const { min, max, step, disabled } = props;
  return (
    <Form.Item
      style={SLIDER_FIELD_STYLE}
      label={(
        <span style={SLIDER_LABEL_STYLE}>
          {label}
          <strong>{value}{suffix ?? ""}</strong>
        </span>
      )}
    >
      <Slider
        min={typeof min === "number" ? min : Number(min ?? 0)}
        max={typeof max === "number" ? max : Number(max ?? 100)}
        step={typeof step === "number" ? step : Number(step ?? 1)}
        disabled={disabled}
        value={Number(value)}
        onChange={(nextValue) => onValueChange(String(nextValue))}
      />
    </Form.Item>
  );
}

interface SearchFieldProps {
  label: string;
  value: string;
  placeholder?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  onSelect?: (item: SymbolSearchItem) => void;
}

export function SearchField({ label, value, placeholder, disabled = false, onChange, onSelect }: SearchFieldProps) {
  const fieldKey = useId();
  const { items, total, open, error } = useSharedUiStore((state) => state.symbolSearch[fieldKey] ?? EMPTY_SEARCH_RESULT);
  const setSymbolSearch = useSharedUiStore((state) => state.setSymbolSearch);
  const resetSymbolSearch = useSharedUiStore((state) => state.resetSymbolSearch);
  const requestSeq = useRef(0);

  useEffect(() => {
    const query = value.trim();
    if (disabled || query.length < 2) {
      requestSeq.current += 1;
      resetSymbolSearch(fieldKey);
      return undefined;
    }
    const seq = requestSeq.current + 1;
    requestSeq.current = seq;
    const timer = window.setTimeout(() => {
      strategiesApi.searchSymbols(query, 8)
        .then((result) => {
          if (requestSeq.current !== seq) return;
          setSymbolSearch(fieldKey, {
            items: result.items ?? [],
            total: result.total ?? result.items?.length ?? 0,
            open: true,
            error: "",
          });
        })
        .catch((err) => {
          if (requestSeq.current !== seq) return;
          setSymbolSearch(fieldKey, {
            items: [],
            total: 0,
            error: err instanceof Error ? err.message : "搜索失败，请重试",
            open: true,
          });
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
    };
  }, [disabled, fieldKey, resetSymbolSearch, setSymbolSearch, value]);

  return (
    <div style={SEARCH_FIELD_STYLE}>
      <TextField label={label} value={value} placeholder={placeholder} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
      {open && (items.length || error) ? (
        <div style={SEARCH_POPOVER_STYLE} role="listbox" aria-label={`${label}搜索结果`}>
          {error ? <div style={SEARCH_ERROR_STYLE}>{error}</div> : null}
          {items.map((item) => (
            <button
              key={item.symbol}
              type="button"
              role="option"
              style={SEARCH_OPTION_STYLE}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange(item.symbol);
                onSelect?.(item);
                setSymbolSearch(fieldKey, { open: false });
              }}
            >
              <strong>{item.symbol}</strong>
              <span>{item.name || "--"}</span>
              <small>{item.industry || item.instrument_type || ""}</small>
            </button>
          ))}
          {!error && total > items.length ? (
            <div style={SEARCH_MESSAGE_STYLE}>还有 {total - items.length} 条结果，请细化搜索</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
