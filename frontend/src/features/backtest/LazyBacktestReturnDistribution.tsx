import { useMemo } from "react";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { EquityPoint } from "../../api/backtests";
import { ChartIsland } from "../../ui/charts/ChartIsland";
import {
  BACKTEST_ECHARTS_ALT_STYLE,
  BACKTEST_ECHARTS_STYLE,
  combineBacktestStyles,
} from "./backtestStyles";
import { backtestChartColor, withAlpha } from "./backtestChartTheme";

echarts.use([BarChart, CanvasRenderer, GridComponent, LegendComponent, LineChart, TooltipComponent]);

export default function LazyBacktestReturnDistribution({ points }: { points: EquityPoint[] }) {
  const option = useMemo(() => buildOption(points), [points]);
  return <ChartIsland option={option} style={combineBacktestStyles(BACKTEST_ECHARTS_STYLE, BACKTEST_ECHARTS_ALT_STYLE)} />;
}

function buildOption(points: EquityPoint[]): echarts.EChartsCoreOption {
  const returns = dailyReturns(points);
  const bins = buildBins(returns, 12);
  const mean = average(returns);
  const std = standardDeviation(returns, mean);
  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  return {
    animation: false,
    color: [backtestChartColor.benchmark, backtestChartColor.strategy],
    grid: { left: 44, right: 18, top: 32, bottom: 32 },
    legend: { top: 2, right: 12, textStyle: { color: backtestChartColor.textSecondary, fontSize: 12 } },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: bins.map((bin) => bin.label), axisLabel: { color: backtestChartColor.textSecondary, fontSize: 12, rotate: 24 } },
    yAxis: { type: "value", axisLabel: { color: backtestChartColor.textSecondary, fontSize: 12 }, splitLine: { lineStyle: { color: withAlpha(backtestChartColor.textMuted, 0.14) } } },
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
