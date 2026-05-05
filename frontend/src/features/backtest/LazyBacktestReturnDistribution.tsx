import { useEffect, useMemo, useRef } from "react";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { EquityPoint } from "../../api/backtests";

echarts.use([BarChart, CanvasRenderer, GridComponent, LegendComponent, LineChart, TooltipComponent]);

export default function LazyBacktestReturnDistribution({ points }: { points: EquityPoint[] }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const option = useMemo(() => buildOption(points), [points]);

  useEffect(() => {
    if (!elementRef.current) return undefined;
    chartRef.current = echarts.init(elementRef.current, undefined, { renderer: "canvas" });
    const handleResize = () => chartRef.current?.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true, true);
  }, [option]);

  return <div ref={elementRef} className="backtest-echarts distribution" />;
}

function buildOption(points: EquityPoint[]): echarts.EChartsCoreOption {
  const returns = dailyReturns(points);
  const bins = buildBins(returns, 12);
  const mean = average(returns);
  const std = standardDeviation(returns, mean);
  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  return {
    animation: false,
    color: ["#d6a55c", "#67e8f9"],
    grid: { left: 44, right: 18, top: 32, bottom: 32 },
    legend: { top: 2, right: 12, textStyle: { color: "#64748b", fontSize: 10 } },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: bins.map((bin) => bin.label), axisLabel: { color: "#64748b", fontSize: 10, rotate: 24 } },
    yAxis: { type: "value", axisLabel: { color: "#64748b", fontSize: 10 }, splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.14)" } } },
    series: [
      { type: "bar", name: "收益分布", data: bins.map((bin) => bin.count), barMaxWidth: 28 },
      {
        type: "line",
        name: "正态拟合",
        smooth: true,
        showSymbol: false,
        data: bins.map((bin) => Math.max(0, normalPdf(bin.mid, mean, std) * returns.length * bin.width * maxCount / Math.max(...bins.map((item) => normalPdf(item.mid, mean, std) * returns.length * item.width), 1))),
      },
    ],
  };
}

function dailyReturns(points: EquityPoint[]): number[] {
  const ordered = points.filter((point) => Number.isFinite(point.nav)).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const values: number[] = [];
  for (let index = 1; index < ordered.length; index += 1) {
    const previous = Number(ordered[index - 1].nav);
    const current = Number(ordered[index].nav);
    if (previous > 0 && Number.isFinite(current)) values.push(((current / previous) - 1) * 100);
  }
  return values;
}

function buildBins(values: number[], count: number) {
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = Math.max((max - min) / count, 0.01);
  return Array.from({ length: count }, (_, index) => {
    const start = min + index * width;
    const end = index === count - 1 ? max + 0.0001 : start + width;
    const binValues = values.filter((value) => value >= start && value < end);
    return {
      count: binValues.length,
      mid: start + width / 2,
      width,
      label: `${start.toFixed(1)}~${end.toFixed(1)}%`,
    };
  });
}

function average(values: number[]): number {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function standardDeviation(values: number[], mean: number): number {
  if (values.length < 2) return 1;
  return Math.max(Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (values.length - 1)), 0.01);
}

function normalPdf(x: number, mean: number, std: number): number {
  return Math.exp(-0.5 * ((x - mean) / std) ** 2) / (std * Math.sqrt(2 * Math.PI));
}
