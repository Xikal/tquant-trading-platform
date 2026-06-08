import { render } from "solid-js/web";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PaperPositionCard } from "./PaperPage";

describe("paper position live quote card", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("renders live quote quality, timestamp, latest price, and day change", () => {
    const dispose = render(
      () => (
        <PaperPositionCard
          item={{
            symbol: "510300",
            name: "沪深300ETF",
            quantity: 200,
            available_quantity: 200,
            cost_basis: 4,
            latest_price: 4.25,
            day_change_pct: 1.23,
            unrealized_pnl_pct: 6.25,
            quote_data_quality: "fresh",
            quote_data_quality_text: "实时行情已叠加",
            quote_timestamp: "2026-06-08 14:56:00",
          }}
          onOpenOrder={vi.fn()}
        />
      ),
      document.body,
    );

    expect(document.body.textContent).toContain("实时行情已叠加");
    expect(document.body.textContent).toContain("2026-06-08 14:56:00");
    expect(document.body.textContent).toContain("4.250");
    expect(document.body.textContent).toContain("+1.23%");
    expect(document.body.textContent).toContain("+6.25%");
    dispose();
  });
});
