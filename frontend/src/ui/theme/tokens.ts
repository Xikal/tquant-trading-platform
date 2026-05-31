/**
 * 设计 Token · 唯一真相源（Web）
 *
 * 任何颜色 / 字号 / 圆角 / 间距只能来自此文件；CSS 侧对应
 * src/styles/foundation/tokens.css（旧变量名在该文件中以别名形式过渡）。
 * 方案见 docs/frontend-ui-redesign-development-plan-2026-05-31.md
 */

export const color = {
  // 中性
  bgBase: "#F4F6FA",
  bgElevated: "#FFFFFF",
  bgSubtle: "#EEF1F6",
  border: "#E2E8F0",
  borderStrong: "#CBD5E1",
  text1: "#0F1B2D",
  text2: "#5A6A7E",
  text3: "#94A3B8",
  // 品牌（深蓝 ink + 交互蓝；金色降级为点睛）
  brandInk: "#0B1F3A",
  brand: "#2563EB",
  brandHover: "#1D4ED8",
  brandSoft: "rgba(37, 99, 235, 0.10)",
  accentGold: "#C8922F",
  // 行情（仅用于数据：红涨绿跌）
  mktUp: "#C62828",
  mktDown: "#1F8B4C",
  mktFlat: "#5A6A7E",
  // 反馈
  success: "#08875D",
  warning: "#B7791F",
  error: "#B42318",
  info: "#2563EB",
} as const;

export const radius = { sm: 6, md: 10, lg: 14 } as const;

export const font = {
  family: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
  micro: 12,
  sm: 13,
  base: 14,
  md: 16,
  lg: 20,
  xl: 24,
} as const;

export const space = {
  sp1: 4,
  sp2: 8,
  sp3: 12,
  sp4: 16,
  sp5: 24,
  sp6: 32,
  sp7: 48,
} as const;

export const tokens = { color, radius, font, space } as const;
