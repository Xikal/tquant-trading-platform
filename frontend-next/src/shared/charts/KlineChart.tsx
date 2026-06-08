import { createEffect, onCleanup } from "solid-js";
import { CandlestickSeries, createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import { recordTelemetry } from "../telemetry/clientTelemetry";
import { redactSensitiveText } from "../security/redaction";
import { downsampleChartPoints } from "./chartDownsample";

export interface KlineCandlePoint {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export function KlineChart(props: { points: KlineCandlePoint[]; height?: number; maxPoints?: number; variant?: "light" | "dark" }) {
  let container: HTMLDivElement | undefined;
  let chart: IChartApi | null = null;
  let series: ISeriesApi<"Candlestick"> | null = null;
  let updateSequence = 0;
  let disposed = false;

  createEffect(() => {
    if (!container || chart) return;
    chart = createChart(container, {
      height: props.height ?? 220,
      layout: { background: { color: props.variant === "dark" ? "#0b1f3a" : "#ffffff" }, textColor: props.variant === "dark" ? "#9fb0c5" : "#5a6a7e" },
      grid: { vertLines: { color: props.variant === "dark" ? "#152a49" : "#eef1f6" }, horzLines: { color: props.variant === "dark" ? "#152a49" : "#eef1f6" } },
      rightPriceScale: { borderColor: props.variant === "dark" ? "#25324a" : "#e2e8f0" },
      timeScale: { borderColor: props.variant === "dark" ? "#25324a" : "#e2e8f0" },
    });
    series = chart.addSeries(CandlestickSeries, {
      upColor: props.variant === "dark" ? "#22c55e" : "#16a34a",
      downColor: props.variant === "dark" ? "#ef4444" : "#dc2626",
      borderUpColor: props.variant === "dark" ? "#22c55e" : "#16a34a",
      borderDownColor: props.variant === "dark" ? "#ef4444" : "#dc2626",
      wickUpColor: props.variant === "dark" ? "#86efac" : "#16a34a",
      wickDownColor: props.variant === "dark" ? "#fca5a5" : "#dc2626",
    });
    recordTelemetry({ kind: "chart", name: "kline", status: "init", meta: { points: props.points.length } });
  });

  createEffect(() => {
    if (!series) return;
    const sequence = ++updateSequence;
    const sourcePoints = props.points;
    downsampleChartPoints(sourcePoints, props.maxPoints ?? 240)
      .then((points) => {
        if (disposed || sequence !== updateSequence || !series) return;
        series.setData(points.map((point) => ({
          time: chartTime(point.time),
          open: point.open,
          high: point.high,
          low: point.low,
          close: point.close,
        })));
        recordTelemetry({ kind: "chart", name: "kline", status: "set-data", meta: { points: points.length, source_points: sourcePoints.length } });
      })
      .catch((error) => {
        if (disposed || sequence !== updateSequence || !series) return;
        series.setData([]);
        recordTelemetry({ kind: "chart", name: "kline", status: "error", meta: { error: redactSensitiveText(error) } });
      });
  });

  onCleanup(() => {
    disposed = true;
    updateSequence += 1;
    chart?.remove();
    recordTelemetry({ kind: "chart", name: "kline", status: "disposed" });
  });

  return <div class={`chart-frame${props.variant === "dark" ? " chart-frame--dark" : ""}`} ref={container} />;
}

function chartTime(time: string | number): Time {
  return (typeof time === "number" ? (Math.floor(time) as Time) : time) as Time;
}
