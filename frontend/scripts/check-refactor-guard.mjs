import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname;
const allowed = new Set(["ui/grid/VirtualGrid.tsx"]);
const allowedSignalDefinitionDirs = ["state/realtime/"];
const statePatterns = [
  { label: "useState", regex: /\buseState\b/ },
  { label: "useReducer", regex: /\buseReducer\b/ },
];
const tsxPatterns = [
  { label: "AntD icons barrel import", regex: /from\s+["']@ant-design\/icons["']/ },
  { label: "raw AntD Table import", regex: /import\s+\{[^}]*\bTable\b[^}]*\}\s+from\s+["']antd["']/ },
  { label: "echarts-for-react import", regex: /from\s+["']echarts-for-react["']/ },
  { label: "raw AntD Table JSX", regex: /<Table\b/ },
  { label: "ReactECharts JSX", regex: /<ReactECharts\b/ },
  { label: "dataSource slice", regex: /dataSource=\{[^}]*\.slice\(\s*0\s*,/ },
  { label: "MonitorPage priorityCards non-business slice", regex: /priorityCards\.slice\(\s*0\s*,(?!\s*3[),])/ },
  { label: "MonitorPage opportunities slice", regex: /opportunities\.slice\(\s*0\s*,/ },
  { label: "native input", regex: /<input\b/ },
  { label: "native select", regex: /<select\b/ },
  { label: "native textarea", regex: /<textarea\b/ },
  { label: "native form", regex: /<form\b/ },
  { label: "native table", regex: /<(table|thead|tbody|tr|td|th)\b/ },
  { label: "role table", regex: /role=["']table["']/ },
];

function walk(dir) {
  return readdirSync(dir)
    .flatMap((name) => {
      const path = join(dir, name);
      const rel = relative(ROOT, path);
      if (
        name === "node_modules" ||
        name === "dist"
      ) {
        return [];
      }
      return statSync(path).isDirectory() ? walk(path) : [path];
    });
}

const violations = [];
for (const file of walk(ROOT)) {
  if (!/\.(ts|tsx)$/.test(file)) continue;
  const rel = relative(ROOT, file);
  if (allowed.has(rel)) continue;
  const text = readFileSync(file, "utf8");
  const lines = text.split(/\r?\n/);
  const patterns = /\.tsx$/.test(file) ? [...statePatterns, ...tsxPatterns] : statePatterns;
  if (definesSignal(text) && !allowedSignalDefinitionDirs.some((dir) => rel.startsWith(dir))) {
    violations.push(`${rel}:1 signal definition outside hot realtime state path`);
  }
  for (const violation of findFastStoreIntervalViolations(rel, text)) {
    violations.push(violation);
  }
  lines.forEach((line, index) => {
    for (const pattern of patterns) {
      if (pattern.regex.test(line)) {
        violations.push(`${rel}:${index + 1} ${pattern.label}: ${line.trim()}`);
      }
    }
  });
}

if (violations.length) {
  console.error("Frontend refactor guard failed. Use Zustand and Ant Design Form/Table primitives for Web code instead:");
  console.error(violations.join("\n"));
  process.exit(1);
}

console.log("Frontend refactor guard passed.");

function definesSignal(text) {
  return /from\s+["']@preact\/signals-react["']/.test(text) && /\bsignal\s*</.test(text);
}

function findFastStoreIntervalViolations(rel, text) {
  const violations = [];
  const intervalRegex = /setInterval\s*\(([\s\S]{0,900}?),\s*(\d{1,4})\s*\)/g;
  for (const match of text.matchAll(intervalRegex)) {
    const intervalMs = Number(match[2]);
    if (!Number.isFinite(intervalMs) || intervalMs > 1000) {
      continue;
    }
    const callback = match[1];
    if (writesGlobalStore(callback)) {
      const line = text.slice(0, match.index ?? 0).split(/\r?\n/).length;
      violations.push(`${rel}:${line} <=1000ms setInterval writes Zustand/global store`);
    }
  }
  return violations;
}

function writesGlobalStore(text) {
  return (
    /\.setState\s*\(/.test(text) ||
    /\bset[A-Z][A-Za-z0-9_]*\s*\(/.test(text) && /use[A-Za-z0-9_]*Store/.test(text)
  );
}
