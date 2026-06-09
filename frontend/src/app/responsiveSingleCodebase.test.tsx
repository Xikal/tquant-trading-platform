import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { webRoutes } from "./router/webRouteDefinitions";
import { TqPageLoading } from "../ui/feedback/StateViews";

const rootDir = resolve(__dirname, "..", "..");

function readProjectFile(path: string) {
  return readFileSync(resolve(rootDir, path), "utf8");
}

describe("responsive single codebase", () => {
  it("renders the same Web route shell for mobile-sized viewports", () => {
    const html = renderToStaticMarkup(<TqPageLoading label="工作台加载中" />);
    const keyMobilePaths = ["/monitor", "/monitor/market", "/paper", "/strategy-tracking", "/settings"];

    expect(html).toContain("工作台加载中");
    expect(keyMobilePaths.every((path) => webRoutes.some((route) => route.path === path))).toBe(true);
  });

  it("keeps Capacitor as a shell around the responsive web build", () => {
    const capacitorConfig = readProjectFile("capacitor.config.ts");
    const packageJson = readProjectFile("package.json");

    expect(capacitorConfig).toContain('webDir: "dist"');
    expect(packageJson).not.toContain("dist-native");
    expect(existsSync(resolve(rootDir, "index.native.html"))).toBe(false);
    expect(existsSync(resolve(rootDir, "src/main-native.tsx"))).toBe(false);
  });

  it("removes the antd-mobile and src/mobile fork from source and dependencies", () => {
    const packageJson = readProjectFile("package.json");
    const viteConfig = readProjectFile("vite.config.ts");

    expect(packageJson).not.toContain("antd-mobile");
    expect(viteConfig).not.toContain("antd-mobile");
    expect(existsSync(resolve(rootDir, "src/mobile"))).toBe(false);
    expect(existsSync(resolve(rootDir, "src/app/NativeApp.tsx"))).toBe(false);
    expect(existsSync(resolve(rootDir, "src/app/router/nativeRoutes.tsx"))).toBe(false);
  });
});
