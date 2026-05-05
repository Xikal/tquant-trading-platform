import { useEffect, useMemo, useRef } from "react";
import { HeatmapChart } from "echarts/charts";
import { CalendarComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { BacktestMonthlyReturn } from "../../api/backtests";

echarts.use([CalendarComponent, CanvasRenderer, HeatmapChart, TooltipComponent, VisualMapComponent]);

export default function LazyBacktestMonthlyHeatmap({ items }: { items: BacktestMonthlyReturn[] }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const option = useMemo(() => buildOption(items), [items]);

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

  return <div ref={elementRef} className="backtest-echarts heatmap" />;
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
      inRange: { color: ["#22c55e", "#f8fafc", "#dc2626"] },
      textStyle: { color: "#64748b" },
    },
    calendar: {
      top: 18,
      left: 34,
      right: 28,
      cellSize: ["auto", 18],
      range: [`${minYear}-01-01`, `${maxYear}-12-31`],
      itemStyle: { borderColor: "#e2e8f0" },
      monthLabel: { color: "#475569", fontSize: 10 },
      dayLabel: { show: false },
      yearLabel: { color: "#0f172a" },
    },
    series: {
      type: "heatmap",
      coordinateSystem: "calendar",
      data: finite.map((item) => [`${item.month}-01`, Number(item.return_pct ?? 0), item.benchmark_return_pct ?? null, item.trade_count ?? null]),
    },
  };
}
