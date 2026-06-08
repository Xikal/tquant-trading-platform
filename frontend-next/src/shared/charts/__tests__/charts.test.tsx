import { createSignal } from "solid-js";
import { render } from "solid-js/web";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EquitySparklineChart } from "../EquitySparklineChart";
import { KlineChart } from "../KlineChart";

const chartDownsampleMock = vi.hoisted(() => ({
  downsampleChartPoints: vi.fn((points: Array<{ time: string; open: number; high: number; low: number; close: number }>) => Promise.resolve(points)),
}));

const lightweight = vi.hoisted(() => {
  const series = { setData: vi.fn() };
  const chart = { addSeries: vi.fn(() => series), remove: vi.fn() };
  return { chart, series, createChart: vi.fn(() => chart) };
});

vi.mock("lightweight-charts", () => ({
  CandlestickSeries: "CandlestickSeries",
  createChart: lightweight.createChart,
}));

vi.mock("../chartDownsample", () => ({
  downsampleChartPoints: chartDownsampleMock.downsampleChartPoints,
}));

describe("frontend-next chart lifecycle", () => {
  beforeEach(() => {
    lightweight.chart.addSeries.mockClear();
    lightweight.chart.remove.mockClear();
    lightweight.series.setData.mockClear();
    lightweight.createChart.mockClear();
    chartDownsampleMock.downsampleChartPoints.mockReset();
    chartDownsampleMock.downsampleChartPoints.mockImplementation((points: Array<{ time: string; open: number; high: number; low: number; close: number }>) => Promise.resolve(points));
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("clears Lightweight Charts data when the next point set is empty and removes the chart on cleanup", async () => {
    const [points, setPoints] = createSignal([{ time: "2026-06-05", open: 9.8, high: 10.2, low: 9.7, close: 10 }]);
    const dispose = render(() => <KlineChart points={points()} />, document.body);

    expect(lightweight.createChart).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    expect(lightweight.chart.addSeries).toHaveBeenCalledWith("CandlestickSeries", expect.objectContaining({ upColor: expect.any(String), downColor: expect.any(String) }));
    expect(lightweight.series.setData).toHaveBeenLastCalledWith([{ time: "2026-06-05", open: 9.8, high: 10.2, low: 9.7, close: 10 }]);

    setPoints([]);
    await Promise.resolve();
    expect(lightweight.series.setData).toHaveBeenLastCalledWith([]);

    dispose();
    expect(lightweight.chart.remove).toHaveBeenCalledTimes(1);
  });

  it("converts intraday minute timestamps to unix seconds for Lightweight Charts", async () => {
    const points = [{ time: "2026-06-08 14:50", open: 11.03, high: 11.03, low: 11.02, close: 11.03 }];
    const dispose = render(() => <KlineChart points={points} />, document.body);

    await Promise.resolve();

    expect(lightweight.series.setData).toHaveBeenLastCalledWith([
      { time: Date.UTC(2026, 5, 8, 14, 50, 0) / 1000, open: 11.03, high: 11.03, low: 11.02, close: 11.03 },
    ]);
    dispose();
  });

  it("uses the chart downsample adapter before writing Lightweight Charts data", async () => {
    const points = Array.from({ length: 300 }, (_, index) => ({
      time: `2026-06-${String(index + 1).padStart(2, "0")}`,
      open: index,
      high: index + 1,
      low: index - 1,
      close: index + 0.5,
    }));
    const sampled = [points[0], points.at(-1)!];
    chartDownsampleMock.downsampleChartPoints.mockResolvedValue(sampled);

    const dispose = render(() => <KlineChart points={points} maxPoints={2} />, document.body);
    await Promise.resolve();

    expect(chartDownsampleMock.downsampleChartPoints).toHaveBeenCalledWith(points, 2);
    expect(lightweight.series.setData).toHaveBeenLastCalledWith(sampled);
    dispose();
  });

  it("ignores stale async downsample results after points change", async () => {
    const first = [{ time: "2026-06-05", open: 9.8, high: 10.2, low: 9.7, close: 10 }];
    const second = [{ time: "2026-06-06", open: 10.8, high: 11.2, low: 10.7, close: 11 }];
    const resolvers: Array<(value: Array<{ time: string; open: number; high: number; low: number; close: number }>) => void> = [];
    chartDownsampleMock.downsampleChartPoints.mockImplementation(
      (points: Array<{ time: string; open: number; high: number; low: number; close: number }>) =>
        new Promise((resolve) => {
          resolvers.push(() => resolve(points));
        }),
    );
    const [points, setPoints] = createSignal(first);
    const dispose = render(() => <KlineChart points={points()} />, document.body);

    setPoints(second);
    resolvers[1]?.(second);
    await Promise.resolve();
    resolvers[0]?.(first);
    await Promise.resolve();

    expect(lightweight.series.setData).toHaveBeenCalledTimes(1);
    expect(lightweight.series.setData).toHaveBeenLastCalledWith(second);
    dispose();
  });

  it("renders a lightweight equity sparkline without ECharts runtime", () => {
    const dispose = render(() => <EquitySparklineChart values={[1, 1.05, 0.98, 1.12]} title="样本权益" />, document.body);

    expect(document.querySelector("svg[aria-label='样本权益']")).not.toBeNull();
    expect(document.querySelector(".equity-sparkline__line")?.getAttribute("d")).toContain("M");
    expect(document.querySelectorAll(".equity-sparkline__hit")).toHaveLength(4);

    dispose();
  });

  it("shows an explicit empty state for missing equity values", () => {
    const dispose = render(() => <EquitySparklineChart values={[]} title="空权益" />, document.body);

    expect(document.body.textContent).toContain("后端暂未返回权益曲线");

    dispose();
  });
});
