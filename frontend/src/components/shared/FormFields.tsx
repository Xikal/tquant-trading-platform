import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { useEffect, useRef, useState } from "react";
import { strategiesApi, type SymbolSearchItem } from "../../api/strategies";

interface FieldFrameProps {
  label: string;
  hint?: string;
  error?: string;
  className?: string;
  children: ReactNode;
}

function FieldFrame({ label, hint, error, className = "", children }: FieldFrameProps) {
  return (
    <label className={`tq-field ${className}`.trim()}>
      <span className="tq-field__label">{label}</span>
      {children}
      {error ? <span className="tq-field__error">{error}</span> : null}
      {!error && hint ? <span className="tq-field__hint">{hint}</span> : null}
    </label>
  );
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
  fieldClassName?: string;
};

export function TextField({ label, hint, error, fieldClassName = "", className = "", ...props }: TextFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <input className={`tq-input ${className}`.trim()} {...props} />
    </FieldFrame>
  );
}

export function DateField(props: TextFieldProps) {
  return <TextField {...props} type="date" />;
}

type NumberFieldProps = TextFieldProps & {
  suffix?: string;
};

export function NumberField({ label, hint, error, suffix, fieldClassName = "", className = "", ...props }: NumberFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <span className="tq-input-wrap">
        <input className={`tq-input ${className}`.trim()} {...props} type="number" />
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

export function SelectField({ label, hint, error, options, fieldClassName = "", className = "", ...props }: SelectFieldProps) {
  return (
    <FieldFrame label={label} hint={hint} error={error} className={fieldClassName}>
      <select className={`tq-input ${className}`.trim()} {...props}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
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
  return (
    <label className="tq-field tq-slider-field">
      <span className="tq-field__label">
        {label}
        <strong>{value}{suffix ?? ""}</strong>
      </span>
      <input
        className="tq-slider"
        {...props}
        type="range"
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
      />
    </label>
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
  const [items, setItems] = useState<SymbolSearchItem[]>([]);
  const [total, setTotal] = useState(0);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const requestSeq = useRef(0);

  useEffect(() => {
    const query = value.trim();
    if (disabled || query.length < 2) {
      requestSeq.current += 1;
      setItems([]);
      setTotal(0);
      setOpen(false);
      setError("");
      return undefined;
    }
    const seq = requestSeq.current + 1;
    requestSeq.current = seq;
    const timer = window.setTimeout(() => {
      strategiesApi.searchSymbols(query, 8)
        .then((result) => {
          if (requestSeq.current !== seq) return;
          setItems(result.items ?? []);
          setTotal(result.total ?? result.items?.length ?? 0);
          setOpen(true);
          setError("");
        })
        .catch((err) => {
          if (requestSeq.current !== seq) return;
          setItems([]);
          setTotal(0);
          setError(err instanceof Error ? err.message : "搜索失败，请重试");
          setOpen(true);
        });
    }, 180);
    return () => {
      window.clearTimeout(timer);
    };
  }, [disabled, value]);

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
                setOpen(false);
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
