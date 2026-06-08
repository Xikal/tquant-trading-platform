import { createEffect, onCleanup } from "solid-js";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { recordTelemetry } from "../telemetry/clientTelemetry";

echarts.use([BarChart, LineChart, GridComponent, CanvasRenderer]);

export function EchartsIsland(props: { title?: string; values: number[]; height?: number; type?: "bar" | "line"; variant?: "light" | "dark" }) {
  let container: HTMLDivElement | undefined;
  let chart: echarts.ECharts | null = null;
  createEffect(() => {
    if (!container) return;
    if (!chart) {
      chart = echarts.init(container);
      recordTelemetry({ kind: "chart", name: "echarts", status: "init" });
    }
    chart.setOption({
      backgroundColor: "transparent",
      grid: { left: 28, right: 12, top: 18, bottom: 22 },
      xAxis: { type: "category", data: props.values.map((_, index) => String(index + 1)), axisLabel: { color: axisColor(props.variant) } },
      yAxis: { type: "value", axisLabel: { color: axisColor(props.variant) }, splitLine: { lineStyle: { color: gridColor(props.variant) } } },
      series: [{
        type: props.type ?? "bar",
        data: props.values,
        smooth: props.type === "line",
        showSymbol: false,
        itemStyle: { color: "#2563eb" },
        lineStyle: { color: "#2563eb", width: 2 },
        areaStyle: props.type === "line" ? { color: "rgba(37, 99, 235, 0.12)" } : undefined,
      }],
    });
    recordTelemetry({ kind: "chart", name: "echarts", status: "set-option", meta: { points: props.values.length } });
  });
  onCleanup(() => {
    chart?.dispose();
    recordTelemetry({ kind: "chart", name: "echarts", status: "disposed" });
  });
  return <div class="chart-frame chart-frame--compact" style={{ height: `${props.height ?? 180}px` }} ref={container} aria-label={props.title} />;
}

function axisColor(variant?: "light" | "dark") {
  return variant === "dark" ? "#94a3b8" : "#64748b";
}

function gridColor(variant?: "light" | "dark") {
  return variant === "dark" ? "rgba(148, 163, 184, 0.16)" : "#e2e8f0";
}
