import { App as AntdApp, ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import type { ReactNode } from "react";
import { antdTheme } from "../ui/theme/antdTheme";
import { useThemeStore } from "../stores/themeStore";

export function WebUiProviders({ children }: { children: ReactNode }) {
  const mode = useThemeStore((state) => state.mode);
  const algorithm = mode === "dark" ? theme.darkAlgorithm : theme.defaultAlgorithm;
  return (
    <ConfigProvider locale={zhCN} theme={{ ...antdTheme, algorithm }}>
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}
