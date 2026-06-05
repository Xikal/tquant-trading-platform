import { describe, expect, it, vi } from "vitest";
import { applyChartIslandOption, disposeChartIsland, resizeChartIsland } from "./ChartIsland";
import { downsampleDenseChartPoints, downsampleDenseChartPointsAsync } from "./chartDownsample";

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

  it("keeps ordinary charts unchanged and downsamples dense chart islands", () => {
    const ordinary = Array.from({ length: 60 }, (_, index) => ({ nav: index }));
    const dense = Array.from({ length: 240 }, (_, index) => ({ nav: Math.sin(index / 8), date: String(index) }));

    expect(downsampleDenseChartPoints(ordinary, 120)).toBe(ordinary);
    const downsampled = downsampleDenseChartPoints(dense, 80);
    expect(downsampled).toHaveLength(80);
    expect(downsampled[0]).toBe(dense[0]);
    expect(downsampled[downsampled.length - 1]).toBe(dense[dense.length - 1]);
  });

  it("supports async worker-backed dense chart downsample with sync fallback", async () => {
    const dense = Array.from({ length: 160 }, (_, index) => ({ nav: 1 + index / 100, date: String(index) }));

    const downsampled = await downsampleDenseChartPointsAsync(dense, 80);

    expect(downsampled).toHaveLength(80);
    expect(downsampled[0]).toBe(dense[0]);
    expect(downsampled[downsampled.length - 1]).toBe(dense[dense.length - 1]);
  });
});
