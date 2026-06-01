import { App as AntdApp, ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import type { ReactNode } from "react";
import { antdTheme } from "../ui/theme/antdTheme";

export function WebUiProviders({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider locale={zhCN} theme={{ ...antdTheme, algorithm: theme.defaultAlgorithm }}>
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}
