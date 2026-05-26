import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig(({ mode }) => {
  const isNativeMode = mode === "native";
  const isTestMode = mode === "test";

  return {
    plugins: [react()],
    resolve: {
      alias: isTestMode
        ? {
            "antd-mobile/es/global": resolve(__dirname, "src/test/emptyModule.ts"),
            "antd-mobile": resolve(__dirname, "src/test/antdMobileMock.tsx"),
          }
        : undefined,
    },
    base: isNativeMode ? "./" : "/",
    build: {
      chunkSizeWarningLimit: 700,
      outDir: isNativeMode ? "dist-native" : "dist",
      rolldownOptions: isNativeMode
        ? {
            input: {
              index: resolve(__dirname, "index.native.html")
            },
            output: {
              manualChunks: splitVendorChunks
            }
          }
        : {
            output: {
              manualChunks: splitVendorChunks
            }
          },
      rollupOptions: isNativeMode
        ? {
            input: {
              index: resolve(__dirname, "index.native.html")
            },
            output: {
              manualChunks: splitVendorChunks
            }
          }
        : {
            output: {
              manualChunks: splitVendorChunks
            }
          }
    },
    server: {
      port: 5173,
      host: "0.0.0.0",
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true
        }
      }
    }
  };
});

function splitVendorChunks(id: string): string | undefined {
  if (!id.includes("node_modules")) {
    return undefined;
  }
  const normalized = id.replace(/\\/g, "/");
  if (id.includes("zrender")) {
    return "zrender";
  }
  if (normalized.includes("/echarts-for-react")) {
    return "echarts-react";
  }
  if (normalized.includes("/echarts/core") || normalized.includes("/echarts/lib/core")) {
    return "echarts-core";
  }
  if (normalized.includes("/echarts/charts") || normalized.includes("/echarts/lib/chart")) {
    return "echarts-charts";
  }
  if (normalized.includes("/echarts/components") || normalized.includes("/echarts/lib/component")) {
    return "echarts-components";
  }
  if (normalized.includes("/echarts/renderers") || normalized.includes("/echarts/lib/renderer")) {
    return "echarts-renderers";
  }
  if (normalized.includes("/echarts/lib/coord")) {
    return "echarts-coord";
  }
  if (normalized.includes("/echarts/")) {
    return "echarts-core";
  }
  if (normalized.includes("/@capacitor")) {
    return "native";
  }
  if (normalized.includes("/@ant-design/icons")) {
    return "antd-icons";
  }
  if (matchesAntdComponent(normalized, ["button", "float-button"])) {
    return "antd-button";
  }
  if (matchesAntdComponent(normalized, ["checkbox", "switch", "slider", "radio"])) {
    return "antd-controls";
  }
  if (
    matchesAntdComponent(normalized, ["modal", "drawer", "popconfirm", "popover", "tooltip"]) ||
    matchesAntdComponent(normalized, ["result", "empty", "skeleton", "spin", "alert", "message", "notification", "progress"])
  ) {
    return "antd-feedback";
  }
  if (
    matchesAntdComponent(normalized, ["tabs", "dropdown", "menu", "breadcrumb", "pagination", "steps"]) ||
    matchesAntdComponent(normalized, ["badge", "segmented"])
  ) {
    return "antd-navigation";
  }
  if (
    matchesAntdComponent(normalized, ["form", "input", "input-number", "select", "date-picker", "time-picker", "tree-select"])
  ) {
    return "antd-form";
  }
  if (matchesAntdComponent(normalized, ["table", "list", "descriptions", "statistic", "tag", "timeline"])) {
    return "antd-display";
  }
  if (matchesAntdComponent(normalized, ["row", "col", "grid", "layout", "card", "divider", "flex", "space"])) {
    return "antd-layout";
  }
  if (normalized.includes("/@ant-design") || normalized.includes("/@rc-component") || normalized.includes("/rc-")) {
    return "antd-foundation";
  }
  if (
    normalized.includes("/antd/es/config-provider") ||
    normalized.includes("/antd/lib/config-provider") ||
    normalized.includes("/antd/es/space") ||
    normalized.includes("/antd/lib/space") ||
    normalized.includes("/antd/es/typography") ||
    normalized.includes("/antd/lib/typography") ||
    normalized.includes("/antd/es/theme") ||
    normalized.includes("/antd/lib/theme") ||
    normalized.includes("/antd/es/_util") ||
    normalized.includes("/antd/lib/_util") ||
    normalized.includes("/antd/es/style") ||
    normalized.includes("/antd/lib/style")
  ) {
    return "antd-core";
  }
  if (normalized.includes("/antd/")) {
    return "antd";
  }
  if (normalized.includes("/antd-mobile")) {
    return "antd-mobile";
  }
  if (normalized.includes("/@tanstack")) {
    return "tanstack";
  }
  if (normalized.includes("/react")) {
    return "react-vendor";
  }
  return "vendor";
}

function matchesAntdComponent(id: string, componentNames: string[]): boolean {
  return componentNames.some((component) => (
    id.includes(`/antd/es/${component}`) ||
    id.includes(`/antd/lib/${component}`)
  ));
}
