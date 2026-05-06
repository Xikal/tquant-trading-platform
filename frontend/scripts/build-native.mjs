import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { build } from "vite";

const frontendRoot = resolve(import.meta.dirname, "..");
const repoRoot = resolve(frontendRoot, "..");
const versionFile = resolve(repoRoot, "VERSION.json");

const version = JSON.parse(readFileSync(versionFile, "utf8"));

process.env.VITE_NATIVE_VERSION_CODE = String(version.build_number ?? 1);
process.env.VITE_NATIVE_VERSION_NAME = String(version.version ?? "1.0.0");

await build({ mode: "native" });
