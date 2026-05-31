import type { CSSProperties } from "react";
import { BarChart, CandlestickChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { ChartIsland } from "./ChartIsland";

echarts.use([BarChart, CandlestickChart, GridComponent, LegendComponent, LineChart, CanvasRenderer, TooltipComponent]);

export default function LazyKlineChart({ option, className = "", style }: { option: unknown; className?: string; style?: CSSProperties }) {
  return <ChartIsland option={option as echarts.EChartsCoreOption} className={className} style={style} />;
}
