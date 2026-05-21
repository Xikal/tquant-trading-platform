import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import type { ReactNode } from "react";
import { antdTheme } from "../ui/theme/antdTheme";

export function WebUiProviders({ children }: { children: ReactNode }) {
  return (
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}
