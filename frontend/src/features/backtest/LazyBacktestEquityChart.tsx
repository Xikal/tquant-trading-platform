import { useEffect, useMemo, useRef } from "react";
import { LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkPointComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { EquityPoint } from "../../api/backtests";
import { BACKTEST_ECHARTS_STYLE } from "./backtestStyles";

echarts.use([
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  MarkPointComponent,
  TooltipComponent,
]);

export default function LazyBacktestEquityChart({ points }: { points: EquityPoint[] }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const option = useMemo(() => buildOption(points), [points]);

  useEffect(() => {
    if (!elementRef.current) {
      return undefined;
    }
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

  return <div ref={elementRef} style={BACKTEST_ECHARTS_STYLE} />;
}

function buildOption(points: EquityPoint[]): echarts.EChartsCoreOption {
  const finite = points.filter((point) => Number.isFinite(point.nav));
  const dates = finite.map((point) => point.date);
  const nav = finite.map((point) => round(point.nav));
  const benchmark = finite.map((point) => round(point.benchmark_nav ?? point.nav));
  const drawdown = finite.map((point) => round(point.drawdown_pct ?? 0));
  return {
    animation: false,
    backgroundColor: "transparent",
    color: ["#67e8f9", "#d6a55c", "#ef4444"],
    grid: [
      { left: 46, right: 22, top: 34, height: "56%" },
      { left: 46, right: 22, bottom: 36, height: "18%" },
    ],
    legend: {
      top: 4,
      right: 18,
      textStyle: { color: "#94a3b8", fontSize: 11 },
      data: ["策略净值", "基准净值", "回撤"],
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      valueFormatter: (value: unknown) => formatTooltipValue(value),
    },
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], filterMode: "none" },
      {
        type: "slider",
        xAxisIndex: [0, 1],
        bottom: 8,
        height: 16,
        borderColor: "rgba(148, 163, 184, 0.18)",
        fillerColor: "rgba(103, 232, 249, 0.12)",
        handleStyle: { color: "#67e8f9" },
        textStyle: { color: "#94a3b8" },
      },
    ],
    xAxis: [
      {
        type: "category",
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.28)" } },
        axisLabel: { color: "#94a3b8", fontSize: 10 },
      },
      {
        type: "category",
        data: dates,
        gridIndex: 1,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.22)" } },
        axisLabel: { show: false },
      },
    ],
    yAxis: [
      {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.12)" } },
        axisLabel: { color: "#94a3b8", fontSize: 10 },
      },
      {
        type: "value",
        gridIndex: 1,
        splitLine: { lineStyle: { color: "rgba(239, 68, 68, 0.10)" } },
        axisLabel: { color: "#94a3b8", fontSize: 10, formatter: "{value}%" },
      },
    ],
    series: [
      {
        name: "策略净值",
        type: "line",
        data: nav,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2.6 },
        areaStyle: { color: "rgba(103, 232, 249, 0.10)" },
        markPoint: {
          symbolSize: 42,
          label: { color: "#0f172a", fontSize: 10 },
          data: [
            { type: "max", name: "高点" },
            { type: "min", name: "低点" },
          ],
        },
      },
      {
        name: "基准净值",
        type: "line",
        data: benchmark,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, type: "dashed" },
      },
      {
        name: "回撤",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: drawdown,
        showSymbol: false,
        lineStyle: { width: 1.8 },
        areaStyle: { color: "rgba(239, 68, 68, 0.10)" },
      },
    ],
  };
}

function round(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return Number(value.toFixed(4));
}

function formatTooltipValue(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "--";
  }
  return Math.abs(value) < 0.5 ? value.toFixed(4) : value.toFixed(2);
}
