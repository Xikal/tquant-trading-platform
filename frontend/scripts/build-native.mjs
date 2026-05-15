import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { build, loadEnv } from "vite";

const frontendRoot = resolve(import.meta.dirname, "..");
const repoRoot = resolve(frontendRoot, "..");
const versionFile = resolve(repoRoot, "VERSION.json");

const version = JSON.parse(readFileSync(versionFile, "utf8"));
const nativeEnv = loadEnv("native", frontendRoot, "");

if (!process.env.VITE_NATIVE_VERSION_CODE) {
  process.env.VITE_NATIVE_VERSION_CODE =
    nativeEnv.VITE_NATIVE_VERSION_CODE || String(version.build_number ?? 1);
}
if (!process.env.VITE_NATIVE_VERSION_NAME) {
  process.env.VITE_NATIVE_VERSION_NAME =
    nativeEnv.VITE_NATIVE_VERSION_NAME || String(version.version ?? "1.0.0");
}

if (!process.env.VITE_API_BASE_URL && nativeEnv.VITE_API_BASE_URL) {
  process.env.VITE_API_BASE_URL = nativeEnv.VITE_API_BASE_URL;
}

await build({ mode: "native" });
