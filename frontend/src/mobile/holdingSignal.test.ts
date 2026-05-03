import { describe, expect, it } from "vitest"
import { buildHoldingSignalSignature, isHoldingTSignalActive } from "./holdingSignal"

describe("holding T signal alerts", () => {
  it("keeps a positive T signal active while the price is near the entry zone", () => {
    expect(
      isHoldingTSignalActive({
        action: "positive_t",
        lastPrice: 10.03,
        entryPrice: 10,
        exitPrice: 10.2
      })
    ).toBe(true)
  })

  it("turns off the highlight once price leaves the active zone", () => {
    expect(
      isHoldingTSignalActive({
        action: "positive_t",
        lastPrice: 10.12,
        entryPrice: 10,
        exitPrice: 10.2
      })
    ).toBe(false)
  })

  it("builds a stable signature only for active T signals", () => {
    const signature = buildHoldingSignalSignature([
      {
        symbol: "300750",
        action: "positive_t",
        lastPrice: 10.01,
        entryPrice: 10,
        exitPrice: 10.2
      },
      {
        symbol: "002594",
        action: "hold",
        lastPrice: 20,
        entryPrice: null,
        exitPrice: null
      }
    ])

    expect(signature).toBe("300750:positive_t")
  })
})
