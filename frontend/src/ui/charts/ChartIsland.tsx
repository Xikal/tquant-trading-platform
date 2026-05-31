import type { CSSProperties } from "react";
import { useEffect, useRef } from "react";
import type { EChartsCoreOption, EChartsType } from "echarts/core";
import * as echarts from "echarts/core";

interface ChartIslandProps {
  className?: string;
  option: EChartsCoreOption;
  style?: CSSProperties;
}

interface ChartIslandInstance {
  dispose: () => void;
  resize: () => void;
  setOption: (option: EChartsCoreOption, notMerge?: boolean, lazyUpdate?: boolean) => void;
}

export function ChartIsland({ className = "", option, style }: ChartIslandProps) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const resizeTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!elementRef.current) {
      return undefined;
    }
    chartRef.current = echarts.init(elementRef.current, undefined, { renderer: "canvas" });
    const handleResize = () => {
      if (resizeTimerRef.current != null) {
        window.clearTimeout(resizeTimerRef.current);
      }
      resizeTimerRef.current = window.setTimeout(() => {
        resizeTimerRef.current = null;
        resizeChartIsland(chartRef.current);
      }, 80);
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      if (resizeTimerRef.current != null) {
        window.clearTimeout(resizeTimerRef.current);
        resizeTimerRef.current = null;
      }
      disposeChartIsland(chartRef.current);
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    applyChartIslandOption(chartRef.current, option);
  }, [option]);

  return <div ref={elementRef} className={className || undefined} style={style} />;
}

export function applyChartIslandOption(chart: ChartIslandInstance | null, option: EChartsCoreOption): void {
  chart?.setOption(option, true, true);
}

export function resizeChartIsland(chart: Pick<ChartIslandInstance, "resize"> | null): void {
  chart?.resize();
}

export function disposeChartIsland(chart: Pick<ChartIslandInstance, "dispose"> | null): void {
  chart?.dispose();
}
