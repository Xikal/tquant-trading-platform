import { describe, expect, it } from "vitest";
import { mergePaperOrderDraft, paperOrderDraftFromSearch, paperOrderDraftKey } from "./paperOrderDraft";

describe("paper order draft helpers", () => {
  it("accepts only analysis-sourced search drafts", () => {
    expect(paperOrderDraftFromSearch({ source: "analysis", symbol: "600000", name: "浦发银行", quantity: "300", price: "8.72" })).toMatchObject({
      symbol: "600000",
      name: "浦发银行",
      quantity: "300",
      price: "8.72",
      side: "buy",
      order_type: "limit",
    });
    expect(paperOrderDraftFromSearch({ source: "manual", symbol: "600000" })).toBeNull();
  });

  it("normalizes invalid draft fields back to the paper shadow default", () => {
    expect(mergePaperOrderDraft({ symbol: "sh600000", side: "sell", quantity: "0", price: "bad" })).toMatchObject({
      symbol: "600000",
      side: "sell",
      quantity: "100",
      price: "",
    });
  });

  it("produces a stable key for modal handoff dedupe", () => {
    expect(paperOrderDraftKey({ symbol: "600000", side: "buy", quantity: "100", price: "8.72" })).toBe("600000|buy|100|8.72||");
    expect(paperOrderDraftKey(null)).toBe("");
  });
});
