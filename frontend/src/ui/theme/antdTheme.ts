import type { ThemeConfig } from "antd";

export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: "#0B1F3A",
    colorInfo: "#2563EB",
    colorSuccess: "#08875D",
    colorWarning: "#B7791F",
    colorError: "#B42318",
    colorText: "#102033",
    colorTextSecondary: "#64748B",
    colorBgLayout: "#F4F6FA",
    colorBgContainer: "#FFFFFF",
    colorBorder: "#E2E8F0",
    borderRadius: 12,
    fontFamily: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
  },
  components: {
    Button: {
      controlHeight: 36,
      borderRadius: 8,
    },
    Card: {
      borderRadiusLG: 12,
    },
    Table: {
      fontSize: 13,
      cellPaddingBlock: 8,
      cellPaddingInline: 10,
    },
  },
};
