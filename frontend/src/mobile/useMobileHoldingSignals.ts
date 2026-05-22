import { useEffect, useMemo, useRef } from "react"
import { useMobileUiStore } from "../stores/mobileUiStore"
import type { MobileHoldingRowData } from "./MobileDesignCards"
import { buildHoldingSignalSignature, isHoldingTSignalActive } from "./holdingSignal"
import type { MobileTab } from "./mobileTypes"

function holdingSignalInput(row: MobileHoldingRowData) {
  return {
    symbol: row.record.symbol,
    action: row.signal?.action ?? "hold",
    lastPrice: row.quote?.last_price,
    entryPrice: row.signal?.entry_price
  }
}

export function useMobileHoldingSignals(activeTab: MobileTab, holdingRows: MobileHoldingRowData[]) {
  const signalToastVisible = useMobileUiStore((state) => state.signalToastVisible)
  const setSignalToastVisible = useMobileUiStore((state) => state.setSignalToastVisible)
  const lastSignalToastSignature = useRef("")

  const activeHoldingSignalSymbols = useMemo(() => {
    return new Set(
      holdingRows
        .filter((row) => isHoldingTSignalActive(holdingSignalInput(row)))
        .map((row) => row.record.symbol)
    )
  }, [holdingRows])

  const holdingSignalSignature = useMemo(
    () => buildHoldingSignalSignature(holdingRows.map(holdingSignalInput)),
    [holdingRows]
  )

  useEffect(() => {
    if (activeTab !== "holdings") {
      return
    }
    if (!holdingSignalSignature) {
      lastSignalToastSignature.current = ""
      setSignalToastVisible(false)
      return
    }
    if (lastSignalToastSignature.current === holdingSignalSignature) {
      return
    }
    lastSignalToastSignature.current = holdingSignalSignature
    setSignalToastVisible(true)
    const timeout = window.setTimeout(() => setSignalToastVisible(false), 3000)
    return () => window.clearTimeout(timeout)
  }, [activeTab, holdingSignalSignature, setSignalToastVisible])

  return {
    activeHoldingSignalSymbols,
    signalToastVisible,
    hideSignalToast: () => setSignalToastVisible(false)
  }
}
