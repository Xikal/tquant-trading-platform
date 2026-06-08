import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { relative, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const srcRoot = resolve("src");
const distAssets = resolve("dist/assets");
const jsonReportPath = resolve("../docs/reports/frontend-next-css-budget-2026-06-07.json");
const markdownReportPath = resolve("../docs/reports/frontend-next-css-optimization-2026-06-07.md");
const SOURCE_CSS_BYTES_TARGET = 180_000;
const IMPORTANT_COUNT_TARGET = 25;
const DIST_CSS_GZIP_WARN = 60_000;

const sourceCss = collectFiles(srcRoot, (file) => file.endsWith(".css"));
const distCss = existsSync(distAssets) ? collectFiles(distAssets, (file) => file.endsWith(".css")) : [];
const sourceStats = summarizeFiles(sourceCss);
const distStats = summarizeFiles(distCss);
const importantByFile = sourceStats.files
  .filter((file) => file.important_count > 0)
  .sort((a, b) => b.important_count - a.important_count);
const largestSource = [...sourceStats.files].sort((a, b) => b.bytes - a.bytes).slice(0, 15);
const largestDist = [...distStats.files].sort((a, b) => b.bytes - a.bytes).slice(0, 10);

const report = {
  generated_at: new Date().toISOString(),
  summary: {
    source_css_files: sourceStats.files.length,
    source_css_bytes: sourceStats.bytes,
    source_css_gzip_bytes: sourceStats.gzip_bytes,
    source_css_lines: sourceStats.lines,
    dist_css_files: distStats.files.length,
    dist_css_bytes: distStats.bytes,
    dist_css_gzip_bytes: distStats.gzip_bytes,
    important_count: sourceStats.important_count,
    dist_available: distCss.length > 0,
  },
  important_by_file: importantByFile,
  largest_source_css: largestSource,
  largest_dist_css: largestDist,
  budgets: {
    source_css_bytes_target: SOURCE_CSS_BYTES_TARGET,
    source_css_important_target: IMPORTANT_COUNT_TARGET,
    dist_css_gzip_warn: DIST_CSS_GZIP_WARN,
  },
  status: {
    source_css_bytes: sourceStats.bytes <= SOURCE_CSS_BYTES_TARGET ? "ok" : "needs-explanation",
    important_count: sourceStats.important_count <= IMPORTANT_COUNT_TARGET ? "ok" : "needs-explanation",
    dist_css_gzip: distStats.gzip_bytes <= DIST_CSS_GZIP_WARN || distStats.files.length === 0 ? "ok" : "warn",
  },
  pass: {
    dist_css_gzip: distStats.gzip_bytes <= DIST_CSS_GZIP_WARN || distStats.files.length === 0,
  },
  notes: [
    "Budget report is read-only and does not delete selectors.",
    "Dist CSS numbers require npm run build before this command.",
    "CSS optimization must be verified by screenshot health and visual consistency after any style change.",
  ],
};

mkdirSync(resolve("../docs/reports"), { recursive: true });
writeFileSync(jsonReportPath, `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(markdownReportPath, renderMarkdown(report));
console.log(JSON.stringify({ ok: Object.values(report.pass).every(Boolean), reportPath: jsonReportPath, markdownReportPath, summary: report.summary, status: report.status }, null, 2));

function collectFiles(root, predicate) {
  if (!existsSync(root)) return [];
  const files = [];
  const stack = [root];
  while (stack.length) {
    const current = stack.pop();
    const entries = readDir(current);
    for (const entry of entries) {
      const path = resolve(current, entry.name);
      if (entry.isDirectory()) stack.push(path);
      else if (entry.isFile() && predicate(path)) files.push(path);
    }
  }
  return files.sort();
}

function readDir(path) {
  return readdirSync(path, { withFileTypes: true });
}

function summarizeFiles(files) {
  const items = files.map((file) => {
    const text = readFileSync(file, "utf8");
    return {
      file: relative(process.cwd(), file),
      bytes: Buffer.byteLength(text),
      gzip_bytes: gzipSync(text).length,
      lines: text.split("\n").length,
      important_count: (text.match(/!important/g) ?? []).length,
    };
  });
  return {
    files: items,
    bytes: sum(items, "bytes"),
    gzip_bytes: sum(items, "gzip_bytes"),
    lines: sum(items, "lines"),
    important_count: sum(items, "important_count"),
  };
}

function sum(items, key) {
  return items.reduce((total, item) => total + item[key], 0);
}

function renderMarkdown(payload) {
  const importantRows = payload.important_by_file
    .slice(0, 12)
    .map((file) => `| ${file.file} | ${file.important_count} | ${file.bytes} |`)
    .join("\n");
  const distRows = payload.largest_dist_css
    .map((file) => `| ${file.file} | ${file.bytes} | ${file.gzip_bytes} |`)
    .join("\n");
  const sourceRows = payload.largest_source_css
    .map((file) => `| ${file.file} | ${file.bytes} | ${file.lines} | ${file.important_count} |`)
    .join("\n");
  return `# Frontend Next CSS Optimization - 2026-06-07

状态：预算报告已生成；未执行破坏性删除。
生成时间：${payload.generated_at}

## Budget Summary

| 项 | 值 | 状态 |
|---|---:|---|
| source CSS files | ${payload.summary.source_css_files} | - |
| source CSS bytes | ${payload.summary.source_css_bytes} | ${payload.status.source_css_bytes} |
| source CSS gzip bytes | ${payload.summary.source_css_gzip_bytes} | - |
| source CSS lines | ${payload.summary.source_css_lines} | - |
| dist CSS files | ${payload.summary.dist_css_files} | ${payload.summary.dist_available ? "built" : "dist missing"} |
| dist CSS bytes | ${payload.summary.dist_css_bytes} | - |
| dist CSS gzip bytes | ${payload.summary.dist_css_gzip_bytes} | ${payload.status.dist_css_gzip} |
| !important count | ${payload.summary.important_count} | ${payload.status.important_count} |

## Largest Source CSS

| File | bytes | lines | !important |
|---|---:|---:|---:|
${sourceRows || "| - | - | - | - |"}

## Largest Dist CSS

| File | bytes | gzip bytes |
|---|---:|---:|
${distRows || "| dist 未生成，请先运行 npm run build | - | - |"}

## !important Hotspots

| File | !important | bytes |
|---|---:|---:|
${importantRows || "| - | 0 | - |"}

## Lossless Optimization Rule

- 本报告只做体积和债务统计，不删除 CSS。
- 禁止 PurgeCSS 批量删除；未引用选择器只能先进入候选报告。
- 任何 CSS 修改后必须运行截图/视觉一致性检查。
`;
}
