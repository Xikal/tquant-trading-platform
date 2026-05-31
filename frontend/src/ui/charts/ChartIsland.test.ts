import { describe, expect, it, vi } from "vitest";
import { applyChartIslandOption, disposeChartIsland, resizeChartIsland } from "./ChartIsland";

describe("ChartIsland contract", () => {
  it("updates options imperatively without rebuilding the chart instance", () => {
    const chart = {
      dispose: vi.fn(),
      resize: vi.fn(),
      setOption: vi.fn(),
    };

    applyChartIslandOption(chart, { series: [{ data: [1] }] });
    applyChartIslandOption(chart, { series: [{ data: [2] }] });
    resizeChartIsland(chart);

    expect(chart.setOption).toHaveBeenCalledTimes(2);
    expect(chart.setOption).toHaveBeenNthCalledWith(1, { series: [{ data: [1] }] }, true, true);
    expect(chart.setOption).toHaveBeenNthCalledWith(2, { series: [{ data: [2] }] }, true, true);
    expect(chart.resize).toHaveBeenCalledTimes(1);
    expect(chart.dispose).not.toHaveBeenCalled();
  });

  it("disposes the imperative chart island on unmount", () => {
    const chart = {
      dispose: vi.fn(),
      resize: vi.fn(),
      setOption: vi.fn(),
    };

    disposeChartIsland(chart);

    expect(chart.dispose).toHaveBeenCalledTimes(1);
  });
});
