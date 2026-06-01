export type PriceTone = "up" | "down" | "flat";

interface PriceTextProps {
  className?: string;
  digits?: number;
  fallback?: string;
  prefix?: string;
  showSign?: boolean;
  suffix?: string;
  tone?: PriceTone;
  value?: number | null;
}

export function resolvePriceTone(value?: number | null, fallback: PriceTone = "flat"): PriceTone {
  if (typeof value !== "number" || !Number.isFinite(value) || value === 0) return fallback;
  return value > 0 ? "up" : "down";
}

export function priceToneColor(tone: PriceTone): string {
  if (tone === "up") return "var(--mkt-up)";
  if (tone === "down") return "var(--mkt-down)";
  return "var(--mkt-flat)";
}

export function PriceText({
  className,
  digits = 2,
  fallback = "--",
  prefix = "",
  showSign = false,
  suffix = "",
  tone,
  value,
}: PriceTextProps) {
  const numeric = typeof value === "number" && Number.isFinite(value);
  const resolvedTone = tone ?? resolvePriceTone(value);
  const text = numeric ? `${prefix}${showSign && value > 0 ? "+" : ""}${value.toFixed(digits)}${suffix}` : fallback;
  return <span className={`tq-price tq-price--${resolvedTone} ${className ?? ""}`.trim()}>{text}</span>;
}
