import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { relative, resolve } from "node:path";

const srcRoot = resolve("src");
const jsonReportPath = resolve("../docs/reports/frontend-next-css-unused-report-2026-06-07.json");
const markdownReportPath = resolve("../docs/reports/frontend-next-css-unused-report-2026-06-07.md");
const cssFiles = collectFiles(srcRoot, (file) => file.endsWith(".css"));
const codeFiles = collectFiles(srcRoot, (file) => /\.(ts|tsx|html)$/.test(file) && !file.includes("/generated/"));
const codeText = codeFiles.map((file) => readFileSync(file, "utf8")).join("\n");
const allSelectors = [];

for (const file of cssFiles) {
  const text = readFileSync(file, "utf8");
  const selectors = extractClassSelectors(text);
  for (const selector of selectors) {
    allSelectors.push({
      selector,
      file: relative(process.cwd(), file),
      referenced: isSelectorReferenced(selector, codeText),
      risk: selectorRisk(selector, file),
    });
  }
}

const unique = dedupeSelectors(allSelectors);
const candidates = unique.filter((item) => !item.referenced && item.risk !== "known-dynamic-or-legacy").sort((a, b) => a.selector.localeCompare(b.selector));
const knownDynamic = unique.filter((item) => item.risk === "known-dynamic-or-legacy").sort((a, b) => a.selector.localeCompare(b.selector));
const report = {
  generated_at: new Date().toISOString(),
  summary: {
    css_files: cssFiles.length,
    code_files: codeFiles.length,
    unique_class_selectors: unique.length,
    referenced_selectors: unique.filter((item) => item.referenced).length,
    candidate_unused_selectors: candidates.length,
    known_dynamic_or_legacy_selectors: knownDynamic.length,
  },
  candidate_unused_selectors: candidates.slice(0, 500),
  known_dynamic_or_legacy_selectors: knownDynamic.slice(0, 300),
  notes: [
    "This report is intentionally conservative; do not delete candidates without browser screenshots and runtime DOM checks.",
    "Dynamic classes, legacy adapter classes and third-party compatibility aliases are marked as known-dynamic-or-legacy.",
    "PurgeCSS or automatic deletion is prohibited by the current remediation plan.",
  ],
};

mkdirSync(resolve("../docs/reports"), { recursive: true });
writeFileSync(jsonReportPath, `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(markdownReportPath, renderMarkdown(report));
console.log(JSON.stringify({ ok: true, reportPath: jsonReportPath, markdownReportPath, summary: report.summary }, null, 2));

function collectFiles(root, predicate) {
  if (!existsSync(root)) return [];
  const files = [];
  const stack = [root];
  while (stack.length) {
    const current = stack.pop();
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const path = resolve(current, entry.name);
      if (entry.isDirectory()) stack.push(path);
      else if (entry.isFile() && predicate(path)) files.push(path);
    }
  }
  return files.sort();
}

function extractClassSelectors(text) {
  const selectors = new Set();
  const sanitized = text.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const match of sanitized.matchAll(/\.(-?[_a-zA-Z]+[_a-zA-Z0-9-]*)/g)) {
    const selector = match[1];
    if (selector.length < 2) continue;
    if (/^\d/.test(selector)) continue;
    selectors.add(selector);
  }
  return [...selectors];
}

function isSelectorReferenced(selector, text) {
  const escaped = escapeRegex(selector);
  return new RegExp(`["'\`\\s.]${escaped}(?:["'\`\\s.]|$|--)`).test(text) || text.includes(selector);
}

function selectorRisk(selector, file) {
  if (
    selector.startsWith("ant-") ||
    selector.startsWith("tq-") ||
    selector.startsWith("legacy-") ||
    selector.startsWith("mecha-") ||
    selector.startsWith("is-") ||
    selector.startsWith("has-") ||
    file.includes("legacy-workspace")
  ) {
    return "known-dynamic-or-legacy";
  }
  if (selector.includes("--")) return "modifier";
  return "candidate";
}

function dedupeSelectors(items) {
  const bySelector = new Map();
  for (const item of items) {
    const existing = bySelector.get(item.selector);
    if (!existing) {
      bySelector.set(item.selector, { ...item, files: [item.file] });
      continue;
    }
    existing.referenced ||= item.referenced;
    existing.files.push(item.file);
    if (existing.risk !== "known-dynamic-or-legacy") existing.risk = item.risk;
  }
  return [...bySelector.values()].map((item) => ({ ...item, files: [...new Set(item.files)].slice(0, 8) }));
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function renderMarkdown(payload) {
  const candidateRows = payload.candidate_unused_selectors
    .slice(0, 80)
    .map((item) => `| .${item.selector} | ${item.files.join("<br>")} | ${item.risk} |`)
    .join("\n");
  return `# Frontend Next CSS Unused Selector Report - 2026-06-07

状态：只读候选报告，未删除任何样式。
生成时间：${payload.generated_at}

## Summary

| 项 | 值 |
|---|---:|
| CSS files | ${payload.summary.css_files} |
| code files scanned | ${payload.summary.code_files} |
| unique class selectors | ${payload.summary.unique_class_selectors} |
| referenced selectors | ${payload.summary.referenced_selectors} |
| candidate unused selectors | ${payload.summary.candidate_unused_selectors} |
| known dynamic/legacy selectors | ${payload.summary.known_dynamic_or_legacy_selectors} |

## Candidate Selectors

| Selector | Files | Risk |
|---|---|---|
${candidateRows || "| - | - | - |"}

## Rules

- 候选项不能自动删除；必须先做 DOM/class 运行时扫描和截图健康检查。
- .tq-*、.ant-*、legacy adapter、modifier、动态状态类默认保守保留。
- 禁止 PurgeCSS 批量删除。
`;
}
