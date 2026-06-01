import { useMemo } from "react";
import { LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { BacktestCompareResponse } from "../../api/backtests";
import { ChartIsland } from "../../ui/charts/ChartIsland";
import {
  BACKTEST_ECHARTS_COMPACT_STYLE,
  BACKTEST_ECHARTS_STYLE,
  combineBacktestStyles,
} from "./backtestStyles";
import { backtestChartColor, backtestComparePalette, withAlpha } from "./backtestChartTheme";

echarts.use([CanvasRenderer, DataZoomComponent, GridComponent, LegendComponent, LineChart, TooltipComponent]);

export default function LazyBacktestCompareChart({ result }: { result: BacktestCompareResponse | null }) {
  const option = useMemo(() => buildOption(result), [result]);
  return <ChartIsland option={option} style={combineBacktestStyles(BACKTEST_ECHARTS_STYLE, BACKTEST_ECHARTS_COMPACT_STYLE)} />;
}

function buildOption(result: BacktestCompareResponse | null): echarts.EChartsCoreOption {
  const series = (result?.items ?? []).filter((item) => (item.equity ?? []).length >= 2).slice(0, 6);
  const dates = Array.from(new Set(series.flatMap((item) => (item.equity ?? []).map((point) => point.date)))).sort();
  return {
    animation: false,
    backgroundColor: "transparent",
    color: [...backtestComparePalette],
    grid: { left: 44, right: 18, top: 34, bottom: 42 },
    legend: { top: 4, right: 12, textStyle: { color: backtestChartColor.textMuted, fontSize: 12 } },
    tooltip: { trigger: "axis" },
    dataZoom: [
      { type: "inside", filterMode: "none" },
      { type: "slider", height: 14, bottom: 8, textStyle: { color: backtestChartColor.textMuted } },
    ],
    xAxis: { type: "category", data: dates, boundaryGap: false, axisLabel: { color: backtestChartColor.textMuted, fontSize: 12 } },
    yAxis: { type: "value", scale: true, axisLabel: { color: backtestChartColor.textMuted, fontSize: 12 }, splitLine: { lineStyle: { color: withAlpha(backtestChartColor.textMuted, 0.12) } } },
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
