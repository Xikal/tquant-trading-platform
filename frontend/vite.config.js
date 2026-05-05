import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var isNativeMode = mode === "native";
    return {
        plugins: [react()],
        base: isNativeMode ? "./" : "/",
        build: {
            chunkSizeWarningLimit: 600,
            outDir: isNativeMode ? "dist-native" : "dist",
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
    if (id.includes("zrender")) {
        return "zrender";
    }
    if (id.includes("/echarts") || id.includes("\\echarts")) {
        return "echarts";
    }
    if (id.includes("/@capacitor") || id.includes("\\@capacitor")) {
        return "native";
    }
    if (id.includes("/react") || id.includes("\\react")) {
        return "react-vendor";
    }
    return "vendor";
}
