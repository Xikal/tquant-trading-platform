import { defineConfig } from "vite";
import solid from "vite-plugin-solid";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/next/" : "/",
  plugins: [solid()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: process.env.FRONTEND_NEXT_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rolldownOptions: {
      output: {
        manualChunks: splitVendorChunks,
      },
    },
    rollupOptions: {
      output: {
        manualChunks: splitVendorChunks,
      },
    },
  },
  worker: {
    format: "es",
  },
}));

function splitVendorChunks(id: string): string | undefined {
  if (!id.includes("node_modules")) return undefined;
  const normalized = id.replace(/\\/g, "/");
  if (normalized.includes("/echarts/core") || normalized.includes("/echarts/lib/core")) return "echarts-core";
  if (normalized.includes("/echarts/charts") || normalized.includes("/echarts/lib/chart")) return "echarts-charts";
  if (normalized.includes("/echarts/components") || normalized.includes("/echarts/lib/component")) return "echarts-components";
  if (normalized.includes("/echarts/renderers") || normalized.includes("/echarts/lib/renderer")) return "echarts-renderers";
  if (normalized.includes("/zrender/")) return "zrender";
  if (normalized.includes("/echarts/")) return "echarts-core";
  if (normalized.includes("/@tanstack/")) return "tanstack";
  if (normalized.includes("/solid-js/")) return "solid-vendor";
  return "vendor";
}
