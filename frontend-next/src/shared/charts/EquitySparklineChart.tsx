import { createEffect, createMemo, createSignal, For, Show } from "solid-js";
import { recordTelemetry } from "../telemetry/clientTelemetry";

export interface EquitySparklineChartProps {
  title?: string;
  values: number[];
  height?: number;
}

interface SparklinePoint {
  x: number;
  y: number;
  value: number;
  index: number;
}

export function EquitySparklineChart(props: EquitySparklineChartProps) {
  const [hovered, setHovered] = createSignal<SparklinePoint | null>(null);
  const height = () => props.height ?? 286;
  const width = 640;
  const padding = { top: 20, right: 18, bottom: 28, left: 38 };
  const finiteValues = createMemo(() => props.values.filter((value) => Number.isFinite(value)));
  const points = createMemo(() => buildPoints(finiteValues(), width, height(), padding));
  const linePath = createMemo(() => points().map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" "));
  const areaPath = createMemo(() => {
    const rows = points();
    if (!rows.length) return "";
    const baseline = height() - padding.bottom;
    return `${linePath()} L${rows[rows.length - 1].x.toFixed(2)},${baseline} L${rows[0].x.toFixed(2)},${baseline} Z`;
  });
  const ticks = createMemo(() => yTicks(finiteValues(), height(), padding));

  createEffect(() => {
    recordTelemetry({ kind: "chart", name: "equity-sparkline", status: finiteValues().length ? "rendered" : "empty", meta: { points: finiteValues().length } });
  });

  return (
    <div class="chart-frame chart-frame--compact equity-sparkline" style={{ height: `${height()}px` }} aria-label={props.title ?? "权益曲线"}>
      <Show when={points().length > 0} fallback={<div class="equity-sparkline__empty">后端暂未返回权益曲线。</div>}>
        <svg viewBox={`0 0 ${width} ${height()}`} role="img" aria-label={props.title ?? "权益曲线"}>
          <For each={ticks()}>
            {(tick) => (
              <g>
                <line x1={padding.left} x2={width - padding.right} y1={tick.y} y2={tick.y} class="equity-sparkline__grid" />
                <text x={padding.left - 8} y={tick.y + 3} text-anchor="end" class="equity-sparkline__tick">{tick.label}</text>
              </g>
            )}
          </For>
          <path d={areaPath()} class="equity-sparkline__area" />
          <path d={linePath()} class="equity-sparkline__line" />
          <For each={points()}>
            {(point) => (
              <circle
                cx={point.x}
                cy={point.y}
                r="7"
                class="equity-sparkline__hit"
                onMouseEnter={() => setHovered(point)}
                onMouseLeave={() => setHovered(null)}
              />
            )}
          </For>
          <Show when={hovered()}>
            {(point) => (
              <g>
                <line x1={point().x} x2={point().x} y1={padding.top} y2={height() - padding.bottom} class="equity-sparkline__cursor" />
                <circle cx={point().x} cy={point().y} r="4" class="equity-sparkline__dot" />
                <text x={Math.min(width - 84, point().x + 8)} y={Math.max(18, point().y - 10)} class="equity-sparkline__tooltip">
                  #{point().index + 1} {point().value.toFixed(4)}
                </text>
              </g>
            )}
          </Show>
        </svg>
      </Show>
    </div>
  );
}

function buildPoints(values: number[], width: number, height: number, padding: { top: number; right: number; bottom: number; left: number }): SparklinePoint[] {
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const plotWidth = Math.max(1, width - padding.left - padding.right);
  const plotHeight = Math.max(1, height - padding.top - padding.bottom);
  return values.map((value, index) => ({
    x: padding.left + (values.length === 1 ? plotWidth / 2 : (plotWidth * index) / (values.length - 1)),
    y: padding.top + ((max - value) / span) * plotHeight,
    value,
    index,
  }));
}

function yTicks(values: number[], height: number, padding: { top: number; bottom: number }) {
  if (!values.length) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const ticks = max === min ? [max] : [max, (max + min) / 2, min];
  const plotHeight = Math.max(1, height - padding.top - padding.bottom);
  return ticks.map((value) => ({
    y: padding.top + ((max - value) / (max - min || 1)) * plotHeight,
    label: value.toFixed(2),
  }));
}
