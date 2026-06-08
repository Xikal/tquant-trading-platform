import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { basename, relative, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const distRoot = resolve("dist");
const assetsRoot = resolve(distRoot, "assets");
const indexPath = resolve(distRoot, "index.html");
const jsonReportPath = resolve("../docs/reports/frontend-next-chunk-profile-2026-06-08.json");
const markdownReportPath = resolve("../docs/reports/frontend-next-chunk-profile-2026-06-08.md");
const INITIAL_JS_RAW_TARGET = 350_000;

if (!existsSync(indexPath) || !existsSync(assetsRoot)) {
  console.error("chunk profile requires a built dist. Run npm run build first.");
  process.exit(1);
}

const html = readFileSync(indexPath, "utf8");
const initialAssetHrefs = extractInitialAssetHrefs(html);
const initialAssets = initialAssetHrefs.map((href) => assetInfo(href)).filter(Boolean);
const allAssets = readdirSync(assetsRoot)
  .map((name) => assetInfo(`/next/assets/${name}`))
  .filter(Boolean)
  .sort((a, b) => b.bytes - a.bytes);
const initialJs = initialAssets.filter((asset) => asset.type === "js");
const initialCss = initialAssets.filter((asset) => asset.type === "css");
const echartsAssets = allAssets.filter((asset) => /echarts/i.test(asset.name));
const initialEchartsAssets = initialAssets.filter((asset) => /echarts/i.test(asset.name));
const report = {
  generated_at: new Date().toISOString(),
  dist_index: relative(process.cwd(), indexPath),
  targets: {
    initial_js_raw_bytes_max: INITIAL_JS_RAW_TARGET,
    initial_echarts_assets_max: 0,
  },
  summary: {
    initial_js_assets: initialJs.length,
    initial_js_raw_bytes: sum(initialJs, "bytes"),
    initial_js_gzip_bytes: sum(initialJs, "gzip_bytes"),
    initial_css_assets: initialCss.length,
    initial_css_raw_bytes: sum(initialCss, "bytes"),
    initial_css_gzip_bytes: sum(initialCss, "gzip_bytes"),
    initial_echarts_assets: initialEchartsAssets.length,
    total_js_assets: allAssets.filter((asset) => asset.type === "js").length,
    total_js_raw_bytes: sum(allAssets.filter((asset) => asset.type === "js"), "bytes"),
    echarts_assets: echartsAssets.length,
    echarts_raw_bytes: sum(echartsAssets, "bytes"),
    echarts_gzip_bytes: sum(echartsAssets, "gzip_bytes"),
  },
  initial_assets: initialAssets,
  echarts_assets: echartsAssets,
  largest_assets: allAssets.slice(0, 20),
};

report.status = {
  initial_js_raw: report.summary.initial_js_raw_bytes <= INITIAL_JS_RAW_TARGET ? "ok" : "fail",
  initial_echarts_assets: report.summary.initial_echarts_assets === 0 ? "ok" : "fail",
};
report.ok = Object.values(report.status).every((status) => status === "ok");

mkdirSync(resolve("../docs/reports"), { recursive: true });
writeFileSync(jsonReportPath, `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(markdownReportPath, renderMarkdown(report));

console.log(
  JSON.stringify(
    {
      ok: report.ok,
      reportPath: jsonReportPath,
      markdownReportPath,
      summary: report.summary,
      status: report.status,
    },
    null,
    2,
  ),
);

if (!report.ok) process.exit(1);

function extractInitialAssetHrefs(markup) {
  const assets = new Set();
  for (const match of markup.matchAll(/<script[^>]+src="([^"]+)"[^>]*>/g)) assets.add(match[1]);
  for (const match of markup.matchAll(/<link[^>]+href="([^"]+)"[^>]*>/g)) {
    const tag = match[0];
    if (/rel="(?:modulepreload|stylesheet)"/.test(tag)) assets.add(match[1]);
  }
  return [...assets].filter((href) => href.includes("/assets/"));
}

function assetInfo(href) {
  const name = basename(href);
  const file = resolve(assetsRoot, name);
  if (!existsSync(file)) return null;
  const bytes = statSync(file).size;
  const content = readFileSync(file);
  return {
    name,
    href,
    type: name.endsWith(".js") ? "js" : name.endsWith(".css") ? "css" : "other",
    bytes,
    gzip_bytes: gzipSync(content).length,
  };
}

function sum(items, key) {
  return items.reduce((total, item) => total + item[key], 0);
}

function renderMarkdown(payload) {
  return `# Frontend Next Chunk Profile - 2026-06-08

状态：${payload.ok ? "PASS" : "FAIL"}
生成时间：${payload.generated_at}

## Summary

| 项 | 值 | 状态 |
|---|---:|---|
| initial JS raw bytes | ${payload.summary.initial_js_raw_bytes} | ${payload.status.initial_js_raw} |
| initial JS gzip bytes | ${payload.summary.initial_js_gzip_bytes} | - |
| initial CSS raw bytes | ${payload.summary.initial_css_raw_bytes} | - |
| initial CSS gzip bytes | ${payload.summary.initial_css_gzip_bytes} | - |
| initial ECharts assets | ${payload.summary.initial_echarts_assets} | ${payload.status.initial_echarts_assets} |
| ECharts lazy assets | ${payload.summary.echarts_assets} | - |
| ECharts raw bytes | ${payload.summary.echarts_raw_bytes} | lazy |

## Initial Assets

| Asset | type | raw bytes | gzip bytes |
|---|---|---:|---:|
${payload.initial_assets.map((asset) => `| ${asset.name} | ${asset.type} | ${asset.bytes} | ${asset.gzip_bytes} |`).join("\n") || "| - | - | - | - |"}

## ECharts Assets

| Asset | raw bytes | gzip bytes |
|---|---:|---:|
${payload.echarts_assets.map((asset) => `| ${asset.name} | ${asset.bytes} | ${asset.gzip_bytes} |`).join("\n") || "| - | - | - |"}

## 结论

- 首屏 JS raw 目标：<= ${payload.targets.initial_js_raw_bytes_max} bytes。
- 首屏 ECharts chunk 目标：0。
- ECharts chunk 可以存在，但必须保持 lazy，不得出现在 HTML script/modulepreload 初始资产中。
`;
}
