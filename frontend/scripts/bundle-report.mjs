import { gzipSync } from "node:zlib";
import { readFile, readdir, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";

const distDir = new URL("../dist/assets", import.meta.url);
const outputPath = new URL("../dist/bundle-report.json", import.meta.url);

async function main() {
  const files = await readdir(distDir);
  const assets = [];
  for (const file of files) {
    const filePath = join(distDir.pathname, file);
    const info = await stat(filePath);
    const content = await readFile(filePath);
    const gzipBytes = gzipSync(content).byteLength;
    assets.push({
      file,
      bytes: info.size,
      kb: Number((info.size / 1024).toFixed(2)),
      gzip_bytes: gzipBytes,
      gzip_kb: Number((gzipBytes / 1024).toFixed(2)),
      kind: classifyAsset(file),
    });
  }
  assets.sort((left, right) => right.bytes - left.bytes);
  const totalBytes = assets.reduce((sum, item) => sum + item.bytes, 0);
  const report = {
    generated_at: new Date().toISOString(),
    total_kb: Number((totalBytes / 1024).toFixed(2)),
    total_gzip_kb: Number((assets.reduce((sum, item) => sum + item.gzip_bytes, 0) / 1024).toFixed(2)),
    first_screen_js_gzip_kb: Number((assets
      .filter((item) => item.kind === "first-screen-js")
      .reduce((sum, item) => sum + item.gzip_bytes, 0) / 1024).toFixed(2)),
    assets,
  };
  await writeFile(outputPath, JSON.stringify(report, null, 2));
  console.log(`Bundle report written: ${outputPath.pathname}`);
  for (const item of assets.slice(0, 8)) {
    console.log(`${item.kb.toFixed(2)} KB (${item.gzip_kb.toFixed(2)} gzip)  ${item.file}`);
  }
}

function classifyAsset(file) {
  if (!file.endsWith(".js")) return "style-or-static";
  if (file.startsWith("echarts-") || file.startsWith("antd-")) {
    return "heavy-vendor";
  }
  if (file.startsWith("react-vendor-") || file.startsWith("tanstack-") || file.startsWith("vendor-")) {
    return "vendor";
  }
  if (file.startsWith("TradingWorkspace-") || file.startsWith("index-") || file.startsWith("client-") || file.startsWith("httpClient-")) {
    return "first-screen-js";
  }
  return "lazy-feature";
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
