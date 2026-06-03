import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var isNativeMode = mode === "native";
    return {
        plugins: [react()],
        base: isNativeMode ? "./" : "/",
        build: {
            chunkSizeWarningLimit: 700,
            emptyOutDir: true,
            outDir: "dist",
            rolldownOptions: {
                output: {
                    manualChunks: splitVendorChunks
                }
            },
            rollupOptions: {
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
    if (normalized.includes("/@ant-design/icons")) {
        return "antd-icons";
    }
    if (matchesAntdComponent(normalized, [
        "anchor",
        "auto-complete",
        "calendar",
        "carousel",
        "cascader",
        "collapse",
        "color-picker",
        "date-picker",
        "drawer",
        "float-button",
        "image",
        "mentions",
        "modal",
        "qr-code",
        "statistic",
        "steps",
        "time-picker",
        "tour",
        "transfer",
        "tree",
        "tree-select",
        "upload",
        "watermark",
    ])) {
        return "antd-detail";
    }
    if (matchesRcPackage(normalized, [
        "async-validator",
        "calendar",
        "cascader",
        "collapse",
        "color-picker",
        "dialog",
        "picker",
        "tree",
        "tree-select",
        "upload",
    ])) {
        return "antd-detail";
    }
    if (matchesAntdComponent(normalized, ["button"])) {
        return "antd-shell";
    }
    if (matchesAntdComponent(normalized, ["checkbox"])) {
        return "antd-check-controls";
    }
    if (matchesAntdComponent(normalized, ["switch"])) {
        return "antd-switch-controls";
    }
    if (matchesAntdComponent(normalized, ["radio"])) {
        return "antd-radio-controls";
    }
    if (matchesAntdComponent(normalized, ["slider"])) {
        return "antd-value-controls";
    }
    if (matchesAntdComponent(normalized, ["popconfirm", "popover", "tooltip"]) ||
        matchesAntdComponent(normalized, ["result", "empty", "skeleton", "spin", "alert", "message", "notification", "progress"])) {
        return "antd-feedback";
    }
    if (matchesAntdComponent(normalized, ["tabs", "dropdown", "menu", "breadcrumb", "pagination"]) ||
        matchesAntdComponent(normalized, ["badge", "segmented"])) {
        return "antd-navigation";
    }
    if (matchesAntdComponent(normalized, ["form", "input", "input-number", "select"])) {
        return "antd-form";
    }
    if (matchesAntdComponent(normalized, ["table", "list", "descriptions", "tag", "timeline"])) {
        return "antd-display";
    }
    if (matchesAntdComponent(normalized, ["row", "col", "grid", "layout", "card", "divider", "flex", "space"]) ||
        matchesAntdComponent(normalized, ["typography", "config-provider", "theme"])) {
        return "antd-shell";
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
    if (normalized.includes("/@ant-design") || normalized.includes("/@rc-component") || normalized.includes("/rc-")) {
        return "antd-core";
    }
    if (normalized.includes("/antd/")) {
        return "antd-core";
    }
    if (normalized.includes("/@tanstack")) {
        return "tanstack";
    }
    if (normalized.includes("/react")) {
        return "react-vendor";
    }
    return "vendor";
}
function matchesAntdComponent(id, componentNames) {
    return componentNames.some(function (component) { return (id.includes("/antd/es/".concat(component)) ||
        id.includes("/antd/lib/".concat(component))); });
}
function matchesRcPackage(id, packageNames) {
    return packageNames.some(function (packageName) { return (id.includes("/@rc-component/".concat(packageName, "/")) ||
        id.includes("/rc-".concat(packageName, "/"))); });
}
