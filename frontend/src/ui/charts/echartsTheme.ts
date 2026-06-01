import * as echarts from "echarts/core";
import { color, font } from "../theme/tokens";

export const TQUANT_ECHARTS_THEME = "tquant";

export const tquantEchartsTheme = {
  color: [color.brand, color.mktUp, color.mktDown, color.warning, color.info],
  backgroundColor: "transparent",
  textStyle: {
    color: color.text2,
    fontFamily: font.family,
    fontSize: font.sm,
  },
  title: {
    textStyle: { color: color.text1, fontWeight: 600 },
    subtextStyle: { color: color.text2 },
  },
  line: {
    symbol: "circle",
    symbolSize: 6,
  },
  categoryAxis: {
    axisLine: { lineStyle: { color: color.border } },
    axisTick: { lineStyle: { color: color.border } },
    axisLabel: { color: color.text3 },
    splitLine: { lineStyle: { color: color.border } },
  },
  valueAxis: {
    axisLine: { lineStyle: { color: color.border } },
    axisTick: { lineStyle: { color: color.border } },
    axisLabel: { color: color.text3 },
    splitLine: { lineStyle: { color: color.border } },
  },
  tooltip: {
    backgroundColor: color.bgElevated,
    borderColor: color.border,
    textStyle: { color: color.text1, fontFamily: font.family },
    extraCssText: "box-shadow: var(--shadow-2); border-radius: var(--radius-md);",
  },
  legend: {
    textStyle: { color: color.text2 },
  },
};

let registered = false;

export function ensureTquantEchartsThemeRegistered() {
  if (registered) return;
  echarts.registerTheme(TQUANT_ECHARTS_THEME, tquantEchartsTheme);
  registered = true;
}
