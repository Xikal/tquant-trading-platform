export type PriceTone = "positive" | "negative" | "neutral";

export function getPriceTone(value: number | null | undefined): PriceTone {
  if (typeof value !== "number" || !Number.isFinite(value) || value === 0) {
    return "neutral";
  }
  return value > 0 ? "positive" : "negative";
}

export function getPriceToneClass(value: number | null | undefined) {
  const tone = getPriceTone(value);
  if (tone === "positive") {
    return "price-up";
  }
  if (tone === "negative") {
    return "price-down";
  }
  return "price-flat";
}
