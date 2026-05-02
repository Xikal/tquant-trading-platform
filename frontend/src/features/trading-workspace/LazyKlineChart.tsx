import { useEffect, useRef } from "react";
import { BarChart, CandlestickChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([BarChart, CandlestickChart, GridComponent, LegendComponent, LineChart, CanvasRenderer, TooltipComponent]);

export default function LazyKlineChart({ option, className = "" }: { option: unknown; className?: string }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);

  useEffect(() => {
    if (!elementRef.current) {
      return undefined;
    }
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
    chartRef.current?.setOption(option as echarts.EChartsCoreOption, true, true);
  }, [option]);

  return <div ref={elementRef} className={className} />;
}
