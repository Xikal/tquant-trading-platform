import { defineConfig } from "vite";
import solid from "vite-plugin-solid";

export default defineConfig(({ command }) => ({
  base: command === "build" ? (process.env.VITE_DESKTOP_APP === "1" ? "./" : "/next/") : "/",
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
  if (normalized.includes("/@tanstack/solid-router/")) return "tanstack-router";
  if (normalized.includes("/@tanstack/solid-query/")) return "tanstack-query";
  if (normalized.includes("/@tanstack/solid-table/")) return "tanstack-table";
  if (normalized.includes("/@tanstack/solid-virtual/")) return "tanstack-virtual";
  if (normalized.includes("/@tanstack/")) return "tanstack-misc";
  if (normalized.includes("/solid-js/")) return "solid-vendor";
  return "vendor";
}
