import { copyFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const rootDir = resolve(import.meta.dirname, "..");
const source = resolve(rootDir, "dist-native", "index.native.html");
const target = resolve(rootDir, "dist-native", "index.html");

if (!existsSync(source)) {
  throw new Error(`Native entry not found: ${source}`);
}

copyFileSync(source, target);
