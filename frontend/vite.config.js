import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var isNativeMode = mode === "native";
    var isTestMode = mode === "test";
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
function splitVendorChunks(id) {
    if (!id.includes("node_modules")) {
        return undefined;
    }
    var normalized = id.replace(/\\/g, "/");
    if (id.includes("zrender")) {
        return "zrender";
    }
    if (normalized.includes("/echarts")) {
        return "echarts";
    }
    if (normalized.includes("/@capacitor")) {
        return "native";
    }
    if (normalized.includes("/@ant-design/icons")) {
        return "antd-icons";
    }
    if (normalized.includes("/@ant-design") || normalized.includes("/@rc-component") || normalized.includes("/rc-")) {
        return "antd-foundation";
    }
    if (normalized.includes("/antd/es/table") || normalized.includes("/antd/lib/table")) {
        return "antd-table";
    }
    if (normalized.includes("/antd/es/button") ||
        normalized.includes("/antd/lib/button") ||
        normalized.includes("/antd/es/checkbox") ||
        normalized.includes("/antd/lib/checkbox") ||
        normalized.includes("/antd/es/switch") ||
        normalized.includes("/antd/lib/switch") ||
        normalized.includes("/antd/es/slider") ||
        normalized.includes("/antd/lib/slider")) {
        return "antd-controls";
    }
    if (normalized.includes("/antd/es/modal") ||
        normalized.includes("/antd/lib/modal") ||
        normalized.includes("/antd/es/result") ||
        normalized.includes("/antd/lib/result") ||
        normalized.includes("/antd/es/empty") ||
        normalized.includes("/antd/lib/empty") ||
        normalized.includes("/antd/es/skeleton") ||
        normalized.includes("/antd/lib/skeleton") ||
        normalized.includes("/antd/es/spin") ||
        normalized.includes("/antd/lib/spin")) {
        return "antd-feedback";
    }
    if (normalized.includes("/antd/es/tabs") ||
        normalized.includes("/antd/lib/tabs") ||
        normalized.includes("/antd/es/dropdown") ||
        normalized.includes("/antd/lib/dropdown") ||
        normalized.includes("/antd/es/badge") ||
        normalized.includes("/antd/lib/badge") ||
        normalized.includes("/antd/es/segmented") ||
        normalized.includes("/antd/lib/segmented")) {
        return "antd-navigation";
    }
    if (normalized.includes("/antd/es/form") ||
        normalized.includes("/antd/lib/form") ||
        normalized.includes("/antd/es/input") ||
        normalized.includes("/antd/lib/input") ||
        normalized.includes("/antd/es/input-number") ||
        normalized.includes("/antd/lib/input-number") ||
        normalized.includes("/antd/es/select") ||
        normalized.includes("/antd/lib/select")) {
        return "antd-form";
    }
    if (normalized.includes("/antd/es/config-provider") ||
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
        normalized.includes("/antd/lib/style")) {
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
