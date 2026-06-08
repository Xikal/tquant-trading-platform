import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../", import.meta.url).pathname;
const srcRoot = join(root, "src");
const errors = [];

function walk(dir, result = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) walk(path, result);
    else if (path.endsWith(".css")) result.push(path);
  }
  return result;
}

for (const file of walk(srcRoot)) {
  const rel = relative(root, file);
  const text = readFileSync(file, "utf8");
  const lines = text.split("\n").length;
  if (lines > 1500) errors.push(`${rel}: ${lines} lines exceeds css guard budget 1500`);
  if (text.includes(".legacy-workspace-shell:has(")) errors.push(`${rel}: shell variants must be route classes, not :has() parent hacks`);
}

for (const rel of ["src/shared/styles/legacy-next-overrides.css", "src/shared/styles/workspace-compat.css", "src/shared/styles/web-layout.css"]) {
  try {
    statSync(join(root, rel));
    errors.push(`${rel}: unused legacy override file should stay deleted or be imported deliberately`);
  } catch {
    // Expected: deleted because index.tsx imports tokens, legacy-workspace, and legacy-solid-adapter only.
  }
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`CSS guard passed (${walk(srcRoot).length} css files)`);
