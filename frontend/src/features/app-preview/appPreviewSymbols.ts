import { api } from "../../api/client"

const instrumentIdentityCache = new Map<string, { symbol: string; name: string }>()

export function normalizeSymbol(value: string) {
  return value.trim().toUpperCase()
}

export function stripMarketSuffix(value: string) {
  return normalizeSymbol(value).split(".")[0]
}

export function addExchangeSuffix(value: string) {
  const normalized = normalizeSymbol(value)
  if (!normalized || normalized.includes(".")) {
    return normalized
  }

  const digits = normalized.replace(/[^0-9]/g, "")
  if (!digits) {
    return normalized
  }

  if (/^[569]/.test(digits)) {
    return `${digits}.SH`
  }
  if (/^[0123]/.test(digits)) {
    return `${digits}.SZ`
  }
  if (/^[48]/.test(digits)) {
    return `${digits}.BJ`
  }
  return normalized
}

export function symbolCacheKeys(rawSymbol: string) {
  const normalized = normalizeSymbol(rawSymbol)
  const suffixed = addExchangeSuffix(normalized)
  return [...new Set([normalized, suffixed, stripMarketSuffix(normalized), stripMarketSuffix(suffixed)].filter(Boolean))]
}

export function symbolsMatch(left: string, right: string) {
  const rightKeys = new Set(symbolCacheKeys(right))
  return symbolCacheKeys(left).some((key) => rightKeys.has(key))
}

export function rememberInstrumentIdentity(symbol: string, name: string) {
  const identity = {
    symbol: addExchangeSuffix(symbol),
    name: name.trim() || addExchangeSuffix(symbol)
  }

  for (const key of symbolCacheKeys(symbol)) {
    instrumentIdentityCache.set(key, identity)
  }
  return identity
}

export async function resolveInstrumentIdentity(
  rawSymbol: string,
  knownItems: Array<{ symbol: string; name: string }> = []
) {
  const keyword = normalizeSymbol(rawSymbol)
  if (!keyword) {
    throw new Error("代码必填")
  }

  for (const item of knownItems) {
    rememberInstrumentIdentity(item.symbol, item.name)
  }

  for (const key of symbolCacheKeys(keyword)) {
    const cached = instrumentIdentityCache.get(key)
    if (cached) {
      return cached
    }
  }

  const payload = await api.listInstruments(stripMarketSuffix(addExchangeSuffix(keyword)))
  const items = payload.items ?? []
  const exact =
    items.find((item) => symbolCacheKeys(item.symbol).some((key) => symbolCacheKeys(keyword).includes(key))) ??
    items[0]

  if (!exact) {
    throw new Error("未找到股票代码")
  }

  return rememberInstrumentIdentity(exact.symbol, exact.name)
}
