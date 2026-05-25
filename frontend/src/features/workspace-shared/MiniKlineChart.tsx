import type { CSSProperties } from "react";
import { lazy, Suspense } from "react";
import type { AnalysisResponse } from "../../types";

const LazyKlineChart = lazy(() => import("../../ui/charts/LazyKlineChart"));

const MINI_KLINE_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "stretch",
  gap: 7,
  height: 210,
  padding: "14px 18px",
  borderRadius: 8,
  background: "#0b1422",
};

const MINI_KLINE_EMPTY_STYLE: CSSProperties = {
  display: "grid",
  placeItems: "center",
  flex: 1,
  minWidth: 0,
  color: "#aeb8c7",
  fontSize: 12,
};

const MINI_KLINE_CHART_STYLE: CSSProperties = {
  flex: 1,
  minWidth: 0,
  minHeight: 0,
};

export function MiniKline({ bars }: { bars: AnalysisResponse["bars"] }) {
  const visible = bars.filter((bar) => Number.isFinite(bar.open) && Number.isFinite(bar.close));
  if (!visible.length) {
    return <div style={MINI_KLINE_STYLE}><div style={MINI_KLINE_EMPTY_STYLE}>等待分析后显示K线</div></div>;
  }
  const labels = visible.map((bar) => bar.timestamp.slice(5, 16).replace("T", " "));
  const candleData = visible.map((bar) => [
    Number(bar.open),
    Number(bar.close),
    Number(bar.low),
    Number(bar.high),
  ]);
  const closePrices = visible.map((bar) => Number(bar.close));
  const volumeData = visible.map((bar) => ({
    value: Number(bar.volume || 0),
    itemStyle: { color: Number(bar.close) >= Number(bar.open) ? "#d92d2d" : "#17965a" },
  }));
  const option = {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      confine: true,
      formatter: (params: Array<{ data?: number[]; seriesName: string; dataIndex?: number }>) => {
        const candle = params.find((item) => item.seriesName === "K线")?.data;
        if (!candle) return "";
        const index = params.find((item) => item.seriesName === "K线")?.dataIndex ?? 0;
        const label = labels[index] ?? "";
        return [
          label,
          `开 ${formatKlinePrice(candle[0])}`,
          `收 ${formatKlinePrice(candle[1])}`,
          `低 ${formatKlinePrice(candle[2])}`,
          `高 ${formatKlinePrice(candle[3])}`,
        ].join("<br/>");
      },
    },
    legend: {
      top: 2,
      right: 8,
      textStyle: { color: "#aeb8c7", fontSize: 10 },
      itemWidth: 10,
      itemHeight: 6,
    },
    grid: [
      { left: 42, right: 16, top: 28, height: "58%" },
      { left: 42, right: 16, top: "76%", height: "14%" },
    ],
    xAxis: [
      {
        type: "category",
        data: labels,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#26354a" } },
        axisLabel: { color: "#8f9caf", fontSize: 10, hideOverlap: true },
        axisTick: { show: false },
      },
      {
        type: "category",
        gridIndex: 1,
        data: labels,
        boundaryGap: true,
        axisLine: { show: false },
        axisLabel: { show: false },
        axisTick: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        splitNumber: 4,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#8f9caf", fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#778395", fontSize: 9, formatter: formatKlineVolume },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: candleData,
        itemStyle: {
          color: "#d92d2d",
          color0: "#17965a",
          borderColor: "#d92d2d",
          borderColor0: "#17965a",
        },
      },
      makeMaSeries("5日线", closePrices, 5, "#f0b44c"),
      makeMaSeries("10日线", closePrices, 10, "#4f9df7"),
      makeMaSeries("20日线", closePrices, 20, "#9b7bff"),
      {
        name: "成交量",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData,
        barWidth: "58%",
      },
    ],
  };
  return (
    <div style={MINI_KLINE_STYLE} aria-label="分钟K线">
      <Suspense fallback={<div style={MINI_KLINE_EMPTY_STYLE}>K线加载中...</div>}>
        <LazyKlineChart option={option} style={MINI_KLINE_CHART_STYLE} />
      </Suspense>
    </div>
  );
}

function makeMaSeries(name: string, closePrices: number[], windowSize: number, color: string) {
  return {
    name,
    type: "line",
    data: closePrices.map((_, index) => {
      if (index < windowSize - 1) {
        return "-";
      }
      const slice = closePrices.slice(index - windowSize + 1, index + 1);
      const average = slice.reduce((sum, value) => sum + value, 0) / windowSize;
      return Number(average.toFixed(3));
    }),
    smooth: false,
    showSymbol: false,
    lineStyle: { width: 1, color },
    emphasis: { disabled: true },
  };
}

function formatKlinePrice(value?: number): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value >= 100 ? value.toFixed(2) : value.toFixed(3);
}

function formatKlineVolume(value?: number): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(0)}亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(0)}万`;
  return value.toFixed(0);
}
