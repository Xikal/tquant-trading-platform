import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname;
const allowed = new Set(["test/antdMobileMock.tsx"]);
const statePatterns = [
  { label: "useState", regex: /\buseState\b/ },
  { label: "useReducer", regex: /\buseReducer\b/ },
];
const tsxPatterns = [
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
        name === "dist" ||
        name === "dist-native" ||
        rel === "mobile"
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
  if (allowed.has(rel) || rel === "main-native.tsx") continue;
  const text = readFileSync(file, "utf8");
  const lines = text.split(/\r?\n/);
  const patterns = /\.tsx$/.test(file) ? [...statePatterns, ...tsxPatterns] : statePatterns;
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
