const SCALE = 1_000_000n;
const RATE_SCALE = 1_000_000n;

export type OrderFeePreviewInput = {
  symbol: string;
  side: "buy" | "sell";
  quantity: string | number;
  price: string | number;
};

export function estimateOrderFeeWarning(input: OrderFeePreviewInput): string {
  const quantity = parseInteger(input.quantity);
  const price = parseDecimalToMicros(input.price);
  if (quantity <= 0n || price <= 0n) return "";
  const amount = price * quantity;
  const etf = isEtfSymbol(input.symbol);
  const commission = etf
    ? applyMillionRate(amount, 50n)
    : maxMicros(applyMillionRate(amount, 85n), 5n * SCALE);
  const stampTax = input.side === "sell" && !etf ? applyMillionRate(amount, 500n) : 0n;
  const transferFee = etf ? 0n : applyMillionRate(amount, 10n);
  const totalFee = commission + stampTax + transferFee;
  if (totalFee * 100n >= amount) return "手续费占比超过 1%，单笔金额偏小，容易吞噬收益。";
  if (totalFee * 200n >= amount) return "手续费占比超过 0.5%，建议合并小额委托。";
  return "";
}

function parseInteger(value: string | number): bigint {
  const text = String(value ?? "").trim();
  if (!/^\d+$/.test(text)) return 0n;
  return BigInt(text);
}

function parseDecimalToMicros(value: string | number): bigint {
  const text = String(value ?? "").trim();
  const match = text.match(/^(\d+)(?:\.(\d{0,6}))?$/);
  if (!match) return 0n;
  const whole = BigInt(match[1]);
  const fraction = BigInt((match[2] ?? "").padEnd(6, "0"));
  return whole * SCALE + fraction;
}

function applyMillionRate(amountMicros: bigint, ratePerMillion: bigint): bigint {
  return divRoundHalfUp(amountMicros * ratePerMillion, RATE_SCALE);
}

function divRoundHalfUp(value: bigint, divisor: bigint): bigint {
  return (value + divisor / 2n) / divisor;
}

function maxMicros(left: bigint, right: bigint): bigint {
  return left > right ? left : right;
}

function isEtfSymbol(symbol: string): boolean {
  const normalized = symbol.trim();
  return /^(15|16|51|56|58)\d{4}$/.test(normalized);
}

