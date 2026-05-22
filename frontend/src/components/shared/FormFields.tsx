import type { ChangeEvent, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
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
      className={`tq-field ${className}`.trim()}
      label={label}
      validateStatus={error ? "error" : undefined}
      help={error || undefined}
      extra={!error && hint ? hint : undefined}
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

export function TextField({ label, hint, error, fieldClassName = "", className = "", size: _nativeSize, ...props }: TextFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <Input className={`tq-input ${className}`.trim()} {...props} />
    </FieldFrame>
  );
}

export function DateField(props: TextFieldProps) {
  return <TextField {...props} type="date" />;
}

type NumberFieldProps = TextFieldProps & {
  suffix?: string;
};

export function NumberField({ label, hint, error, suffix, fieldClassName = "", className = "", size: _nativeSize, ...props }: NumberFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <span className="tq-input-wrap">
        <Input className={`tq-input ${className}`.trim()} {...props} type="number" />
        {suffix ? <span className="tq-input-suffix">{suffix}</span> : null}
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

export function SelectField({ label, hint, error, options, fieldClassName = "", className = "", value, disabled, onChange, ...props }: SelectFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <Select
        className={`tq-input ${className}`.trim()}
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
      className="tq-field tq-slider-field"
      label={(
        <span>
        {label}
        <strong>{value}{suffix ?? ""}</strong>
      </span>
      )}
    >
      <Slider
        className="tq-slider"
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
    <div className="tq-search-field">
      <TextField label={label} value={value} placeholder={placeholder} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
      {open && (items.length || error) ? (
        <div className="tq-search-popover" role="listbox" aria-label={`${label}搜索结果`}>
          {error ? <div className="tq-search-error">{error}</div> : null}
          {items.map((item) => (
            <button
              key={item.symbol}
              type="button"
              role="option"
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
            <div className="tq-search-more">还有 {total - items.length} 条结果，请细化搜索</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
