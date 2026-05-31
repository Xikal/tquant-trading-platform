import type { ThemeConfig } from "antd";
import { color, font, radius } from "./tokens";

export const antdTheme: ThemeConfig = {
  // 输出 --ant-* CSS 变量，使手写 CSS 与 antd 组件同源；本项目仅一个 antd 版本，关闭 hash 减小样式体积。
  cssVar: { prefix: "ant" },
  hashed: false,
  token: {
    colorPrimary: color.brand,
    colorInfo: color.info,
    colorSuccess: color.success,
    colorWarning: color.warning,
    colorError: color.error,
    colorText: color.text1,
    colorTextSecondary: color.text2,
    colorBgLayout: color.bgBase,
    colorBgContainer: color.bgElevated,
    colorBorder: color.border,
    borderRadius: radius.sm,
    fontFamily: font.family,
  },
  components: {
    Button: {
      controlHeight: 36,
      borderRadius: radius.sm,
      defaultShadow: "none",
      dangerShadow: "none",
      primaryShadow: "none",
    },
    Card: {
      borderRadiusLG: radius.md,
    },
    Form: {
      itemMarginBottom: 14,
    },
    Input: {
      borderRadius: radius.sm,
    },
    InputNumber: {
      borderRadius: radius.sm,
    },
    Select: {
      borderRadius: radius.sm,
    },
    Table: {
      fontSize: 13,
      cellPaddingBlock: 8,
      cellPaddingInline: 10,
    },
  },
};
