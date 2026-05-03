import type { ActionType } from "../types"

export interface HoldingSignalInput {
  symbol?: string
  action: ActionType
  lastPrice: number | null | undefined
  entryPrice: number | null | undefined
}

const ACTIVE_PRICE_BAND_RATIO = 0.006

export function isHoldingTSignalActive(input: HoldingSignalInput): boolean {
  if (input.action !== "positive_t" && input.action !== "negative_t") {
    return false
  }
  if (!isFinitePositive(input.lastPrice) || !isFinitePositive(input.entryPrice)) {
    return false
  }
  const lower = input.entryPrice * (1 - ACTIVE_PRICE_BAND_RATIO)
  const upper = input.entryPrice * (1 + ACTIVE_PRICE_BAND_RATIO)
  return input.lastPrice >= lower && input.lastPrice <= upper
}

export function buildHoldingSignalSignature(items: HoldingSignalInput[]): string {
  return items
    .filter(isHoldingTSignalActive)
    .map((item) => `${item.symbol}:${item.action}`)
    .join("|")
}

function isFinitePositive(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0
}
