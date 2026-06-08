import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const root = new URL("../", import.meta.url).pathname;
const repoRoot = join(root, "..");
const srcRoot = join(root, "src");
const errors = [];

function walk(dir, result = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) walk(path, result);
    else if ([".ts", ".tsx", ".css"].includes(extname(path))) result.push(path);
  }
  return result;
}

for (const file of walk(srcRoot)) {
  const rel = relative(root, file);
  const text = readFileSync(file, "utf8");
  if (text.includes("strategy_policy.py")) {
    errors.push(`${rel}: frontend-next must not depend on strategy_policy.py`);
  }
  if (/\.\.\/\.\.\/frontend\//.test(text) || /from\s+["'][^"']*frontend\/src/.test(text)) {
    errors.push(`${rel}: old frontend must remain read-only reference, not runtime dependency`);
  }
  if (rel.includes("shared/workers/") && /(priority_board|production_score)\s*=|set[A-Z][\w]*(priority_board|production_score)/.test(text)) {
    errors.push(`${rel}: worker may derive display data only and must not mutate production ranking fields`);
  }
  if (rel.includes("features/") && /Kline|kline/i.test(text) && /echarts/.test(text)) {
    errors.push(`${rel}: K line surfaces must use shared Lightweight Charts adapter, not ECharts directly`);
  }
}

try {
  statSync(join(repoRoot, "strategy_policy.py"));
} catch {
  // Absence is fine here; the guard only prevents frontend-next references or edits.
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log("Boundary guard passed");
