import { readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("../src", import.meta.url).pathname;

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const violations = walk(root)
  .filter((file) => /\.part-\d+\.css$/.test(file))
  .map((file) => relative(root, file));

if (violations.length) {
  console.error("CSS guard failed. Do not use .part-N.css files; use semantic files, tokens, CSS modules, or AntD theme tokens instead:");
  console.error(violations.join("\n"));
  process.exit(1);
}

console.log("CSS guard passed.");
