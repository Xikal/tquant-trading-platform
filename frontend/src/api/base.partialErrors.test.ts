import { describe, expect, it } from "vitest";
import { bffPartialErrorsText, getBffPartialErrors } from "./base";

describe("BFF partial error helpers", () => {
  it("normalizes object and string partial errors without dropping main payload", () => {
    const payload = {
      items: [{ symbol: "600000" }],
      partial_errors: [
        { source: "paired_hedge", detail: "暂不可用" },
        "market_pulse timeout",
      ],
    };

    expect(getBffPartialErrors(payload)).toEqual([
      { source: "paired_hedge", detail: "暂不可用" },
      { detail: "market_pulse timeout" },
    ]);
    expect(bffPartialErrorsText(payload)).toBe("paired_hedge：暂不可用；market_pulse timeout");
    expect(payload.items).toHaveLength(1);
  });
});
