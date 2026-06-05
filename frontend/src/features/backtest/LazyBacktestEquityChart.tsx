import { useEffect, useMemo } from "react";
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
import { useServerState } from "../../state/serverState";
import { ChartIsland } from "../../ui/charts/ChartIsland";
import { downsampleDenseChartPoints, downsampleDenseChartPointsAsync } from "../../ui/charts/chartDownsample";
import { BACKTEST_ECHARTS_STYLE } from "./backtestStyles";
import { backtestChartColor, withAlpha } from "./backtestChartTheme";

echarts.use([
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  MarkPointComponent,
  TooltipComponent,
]);

const EQUITY_CHART_MAX_POINTS = 1200;
const EQUITY_CHART_WORKER_KEY = ["backtest", "equity-chart", "worker-downsample"] as const;

export default function LazyBacktestEquityChart({ points }: { points: EquityPoint[] }) {
  const fallbackPoints = useMemo(() => downsampleDenseChartPoints(points, EQUITY_CHART_MAX_POINTS), [points]);
  const [workerPoints, setWorkerPoints] = useServerState<EquityPoint[] | null>(EQUITY_CHART_WORKER_KEY, null);
  const pointsSignature = useMemo(() => equityPointsSignature(points), [points]);

  useEffect(() => {
    let cancelled = false;
    setWorkerPoints(null);
    if (points.length <= EQUITY_CHART_MAX_POINTS) {
      return undefined;
    }
    void downsampleDenseChartPointsAsync(points, EQUITY_CHART_MAX_POINTS)
      .then((result) => {
        if (!cancelled) {
          setWorkerPoints(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setWorkerPoints(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [points, pointsSignature, setWorkerPoints]);

  const chartPoints = workerPoints ?? fallbackPoints;
  const option = useMemo(() => buildOption(chartPoints), [chartPoints]);
  return <ChartIsland option={option} style={BACKTEST_ECHARTS_STYLE} />;
}

function equityPointsSignature(points: EquityPoint[]): string {
  const first = points[0];
  const last = points[points.length - 1];
  return `${points.length}:${first?.date ?? ""}:${first?.nav ?? ""}:${last?.date ?? ""}:${last?.nav ?? ""}`;
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
    color: [backtestChartColor.strategy, backtestChartColor.benchmark, backtestChartColor.drawdown],
    grid: [
      { left: 46, right: 22, top: 34, height: "56%" },
      { left: 46, right: 22, bottom: 36, height: "18%" },
    ],
    legend: {
      top: 4,
      right: 18,
      textStyle: { color: backtestChartColor.textMuted, fontSize: 12 },
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
        borderColor: withAlpha(backtestChartColor.textMuted, 0.18),
        fillerColor: withAlpha(backtestChartColor.strategy, 0.12),
        handleStyle: { color: backtestChartColor.strategy },
        textStyle: { color: backtestChartColor.textMuted },
      },
    ],
    xAxis: [
      {
        type: "category",
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: withAlpha(backtestChartColor.textMuted, 0.28) } },
        axisLabel: { color: backtestChartColor.textMuted, fontSize: 12 },
      },
      {
        type: "category",
        data: dates,
        gridIndex: 1,
        boundaryGap: false,
        axisLine: { lineStyle: { color: withAlpha(backtestChartColor.textMuted, 0.22) } },
        axisLabel: { show: false },
      },
    ],
    yAxis: [
      {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { color: withAlpha(backtestChartColor.textMuted, 0.12) } },
        axisLabel: { color: backtestChartColor.textMuted, fontSize: 12 },
      },
      {
        type: "value",
        gridIndex: 1,
        splitLine: { lineStyle: { color: withAlpha(backtestChartColor.drawdown, 0.1) } },
        axisLabel: { color: backtestChartColor.textMuted, fontSize: 12, formatter: "{value}%" },
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
        areaStyle: { color: withAlpha(backtestChartColor.strategy, 0.1) },
        markPoint: {
          symbolSize: 42,
          label: { color: backtestChartColor.textPrimary, fontSize: 12 },
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
        areaStyle: { color: withAlpha(backtestChartColor.drawdown, 0.1) },
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
