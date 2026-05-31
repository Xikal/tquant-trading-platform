import { memo } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LiveCell } from "../../ui/realtime/LiveCell";
import {
  clearLiveQuoteSignals,
  createLiveQuoteRenderProbe,
  updateLiveQuoteSignal,
} from "./liveQuoteSignals";

describe("live quote signals", () => {
  it("updates only the changed symbol and field render probe", () => {
    clearLiveQuoteSignals();
    const renderCounts = { parent: 0, firstCell: 0, secondCell: 0 };
    const ProbeCell = memo(function ProbeCell({
      field,
      symbol,
    }: {
      field: "firstCell" | "secondCell";
      symbol: string;
    }) {
      renderCounts[field] += 1;
      return <LiveCell symbol={symbol} field="price" fallback="--" />;
    });
    const ProbeRow = memo(function ProbeRow() {
      renderCounts.parent += 1;
      return (
        <div>
          <ProbeCell symbol="600000" field="firstCell" />
          <ProbeCell symbol="600001" field="secondCell" />
        </div>
      );
    });
    const probe = createLiveQuoteRenderProbe();
    probe.watch("600000", "price");
    probe.watch("600001", "price");

    renderToString(<ProbeRow />);
    updateLiveQuoteSignal("600000", { price: 10.12, changePct: 1.23, signalState: "buy_now" });
    updateLiveQuoteSignal("600001", { price: 7.01, changePct: -0.44, signalState: "watch" });
    probe.reset();
    renderCounts.parent = 0;
    renderCounts.firstCell = 0;
    renderCounts.secondCell = 0;

    updateLiveQuoteSignal("600000", { price: 10.28 });

    expect(probe.count("600000", "price")).toBe(1);
    expect(probe.count("600001", "price")).toBe(0);
    expect(probe.count("600000", "changePct")).toBe(0);
    expect(renderCounts).toEqual({ parent: 0, firstCell: 0, secondCell: 0 });
  });

  it("renders a hot-path LiveCell from the signal value", () => {
    clearLiveQuoteSignals();
    updateLiveQuoteSignal("600000", { price: 10.12, changePct: 1.23, signalState: "buy_now" });

    const html = renderToString(<LiveCell symbol="600000" field="price" fallback="--" />);

    expect(html).toContain("10.120");
  });
});
