import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, relative } from "node:path";

const root = new URL("../", import.meta.url).pathname;
const srcRoot = join(root, "src");
const maxLines = 1200;
const errors = [];
const skipped = new Set(["src/generated/api-types.ts"]);

function walk(dir, result = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) walk(path, result);
    else if ([".ts", ".tsx"].includes(extname(path))) result.push(path);
  }
  return result;
}

for (const file of walk(srcRoot)) {
  const rel = relative(root, file);
  if (skipped.has(rel)) continue;
  const lines = readFileSync(file, "utf8").split("\n").length;
  if (lines > maxLines) errors.push(`${rel}: ${lines} lines exceeds refactor guard budget ${maxLines}`);
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log("Refactor guard passed");
