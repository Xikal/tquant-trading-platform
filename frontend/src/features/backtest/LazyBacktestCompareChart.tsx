import { useEffect, useMemo, useRef } from "react";
import { LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { BacktestCompareResponse } from "../../api/backtests";
import {
  BACKTEST_ECHARTS_COMPACT_STYLE,
  BACKTEST_ECHARTS_STYLE,
  combineBacktestStyles,
} from "./backtestStyles";

echarts.use([CanvasRenderer, DataZoomComponent, GridComponent, LegendComponent, LineChart, TooltipComponent]);

export default function LazyBacktestCompareChart({ result }: { result: BacktestCompareResponse | null }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const option = useMemo(() => buildOption(result), [result]);

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

  return <div ref={elementRef} style={combineBacktestStyles(BACKTEST_ECHARTS_STYLE, BACKTEST_ECHARTS_COMPACT_STYLE)} />;
}

function buildOption(result: BacktestCompareResponse | null): echarts.EChartsCoreOption {
  const series = (result?.items ?? []).filter((item) => (item.equity ?? []).length >= 2).slice(0, 6);
  const dates = Array.from(new Set(series.flatMap((item) => (item.equity ?? []).map((point) => point.date)))).sort();
  return {
    animation: false,
    backgroundColor: "transparent",
    color: ["#67e8f9", "#d6a55c", "#ef4444", "#22c55e", "#f97316", "#a78bfa"],
    grid: { left: 44, right: 18, top: 34, bottom: 42 },
    legend: { top: 4, right: 12, textStyle: { color: "#94a3b8", fontSize: 10 } },
    tooltip: { trigger: "axis" },
    dataZoom: [
      { type: "inside", filterMode: "none" },
      { type: "slider", height: 14, bottom: 8, textStyle: { color: "#94a3b8" } },
    ],
    xAxis: { type: "category", data: dates, boundaryGap: false, axisLabel: { color: "#94a3b8", fontSize: 10 } },
    yAxis: { type: "value", scale: true, axisLabel: { color: "#94a3b8", fontSize: 10 }, splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.12)" } } },
    series: series.map((item) => {
      const pointMap = new Map((item.equity ?? []).map((point) => [point.date, point.nav]));
      return {
        type: "line",
        name: `#${item.run_id}`,
        data: dates.map((date) => round(pointMap.get(date))),
        showSymbol: false,
        smooth: true,
      };
    }),
  };
}

function round(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Number(parsed.toFixed(4)) : null;
}
