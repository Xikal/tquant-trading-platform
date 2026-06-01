import { useMemo } from "react";
import { HeatmapChart } from "echarts/charts";
import { CalendarComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { BacktestMonthlyReturn } from "../../api/backtests";
import { ChartIsland } from "../../ui/charts/ChartIsland";
import {
  BACKTEST_ECHARTS_ALT_STYLE,
  BACKTEST_ECHARTS_STYLE,
  combineBacktestStyles,
} from "./backtestStyles";
import { backtestChartColor } from "./backtestChartTheme";

echarts.use([CalendarComponent, CanvasRenderer, HeatmapChart, TooltipComponent, VisualMapComponent]);

export default function LazyBacktestMonthlyHeatmap({ items }: { items: BacktestMonthlyReturn[] }) {
  const option = useMemo(() => buildOption(items), [items]);
  return <ChartIsland option={option} style={combineBacktestStyles(BACKTEST_ECHARTS_STYLE, BACKTEST_ECHARTS_ALT_STYLE)} />;
}

function buildOption(items: BacktestMonthlyReturn[]): echarts.EChartsCoreOption {
  const finite = items.filter((item) => Number.isFinite(Number(item.return_pct)));
  const years = Array.from(new Set(finite.map((item) => item.month.slice(0, 4)))).sort();
  const minYear = years[0] ?? String(new Date().getFullYear());
  const maxYear = years[years.length - 1] ?? minYear;
  const values = finite.map((item) => Number(item.return_pct ?? 0));
  const maxAbs = Math.max(1, ...values.map((value) => Math.abs(value)));
  return {
    animation: false,
    tooltip: {
      formatter: (params: unknown) => {
        const data = (params as { data?: [string, number, number | null, number | null] }).data;
        if (!data) return "";
        return `${data[0]}<br/>策略收益：${data[1].toFixed(2)}%<br/>基准：${Number(data[2] ?? 0).toFixed(2)}%<br/>交易：${Number(data[3] ?? 0)}`;
      },
    },
    visualMap: {
      min: -maxAbs,
      max: maxAbs,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: [backtestChartColor.success, backtestChartColor.surface, backtestChartColor.drawdown] },
      textStyle: { color: backtestChartColor.textSecondary },
    },
    calendar: {
      top: 18,
      left: 34,
      right: 28,
      cellSize: ["auto", 18],
      range: [`${minYear}-01-01`, `${maxYear}-12-31`],
      itemStyle: { borderColor: backtestChartColor.border },
      monthLabel: { color: backtestChartColor.textSecondary, fontSize: 12 },
      dayLabel: { show: false },
      yearLabel: { color: backtestChartColor.textPrimary },
    },
    series: {
      type: "heatmap",
      coordinateSystem: "calendar",
      data: finite.map((item) => [`${item.month}-01`, Number(item.return_pct ?? 0), item.benchmark_return_pct ?? null, item.trade_count ?? null]),
    },
  };
}
