import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";

const reportPath = new URL("../dist/bundle-report.json", import.meta.url);
const allowlistPath = new URL("../.bundle-allowlist.json", import.meta.url);

const FIRST_SCREEN_GZIP_LIMIT_KB = 350;
const SINGLE_CHUNK_GZIP_LIMIT_KB = 110;
const TOTAL_GZIP_LIMIT_KB = 820;

async function main() {
  const report = await readBundleReport();
  if (!report) {
    return;
  }
  const allowlist = await readAllowlist();
  const violations = checkBundleBudget(report, allowlist);

  if (violations.length) {
    console.error("Bundle budget check failed:");
    console.error(violations.join("\n"));
    process.exit(1);
  }

  console.log("Bundle budget check passed:", {
    first_screen_js_gzip_kb: report.first_screen_js_gzip_kb,
    total_gzip_kb: report.total_gzip_kb,
  });
}

export function checkBundleBudget(report, allowlist = { chunks: {} }) {
  const violations = [];

  if (report.first_screen_js_gzip_kb > FIRST_SCREEN_GZIP_LIMIT_KB) {
    violations.push(`first_screen_js_gzip_kb ${report.first_screen_js_gzip_kb}KB exceeds ${FIRST_SCREEN_GZIP_LIMIT_KB}KB`);
  }
  if (report.total_gzip_kb > TOTAL_GZIP_LIMIT_KB) {
    violations.push(`total_gzip_kb ${report.total_gzip_kb}KB exceeds ${TOTAL_GZIP_LIMIT_KB}KB`);
  }

  for (const asset of report.assets ?? []) {
    if (!asset.file?.endsWith(".js") || asset.gzip_kb <= SINGLE_CHUNK_GZIP_LIMIT_KB) {
      continue;
    }
    const allowed = allowlist.chunks?.[asset.file] ?? allowlist.chunks?.[chunkPrefix(asset.file)];
    if (!allowed?.reason) {
      violations.push(`${asset.file} gzip ${asset.gzip_kb}KB exceeds ${SINGLE_CHUNK_GZIP_LIMIT_KB}KB without allowlist reason`);
    }
  }

  return violations;
}

async function readBundleReport() {
  if (!existsSync(reportPath)) {
    console.log("Bundle budget check skipped: dist/bundle-report.json is not built yet.");
    return null;
  }
  return JSON.parse(await readFile(reportPath, "utf8"));
}

async function readAllowlist() {
  if (!existsSync(allowlistPath)) {
    return { chunks: {} };
  }
  return JSON.parse(await readFile(allowlistPath, "utf8"));
}

function chunkPrefix(file) {
  return file.replace(/-[^-]+\.js$/, "");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
