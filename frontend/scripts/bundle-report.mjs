import { readdir, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";

const distDir = new URL("../dist/assets", import.meta.url);
const outputPath = new URL("../dist/bundle-report.json", import.meta.url);

async function main() {
  const files = await readdir(distDir);
  const assets = [];
  for (const file of files) {
    const filePath = join(distDir.pathname, file);
    const info = await stat(filePath);
    assets.push({ file, bytes: info.size, kb: Number((info.size / 1024).toFixed(2)) });
  }
  assets.sort((left, right) => right.bytes - left.bytes);
  const totalBytes = assets.reduce((sum, item) => sum + item.bytes, 0);
  const report = {
    generated_at: new Date().toISOString(),
    total_kb: Number((totalBytes / 1024).toFixed(2)),
    assets,
  };
  await writeFile(outputPath, JSON.stringify(report, null, 2));
  console.log(`Bundle report written: ${outputPath.pathname}`);
  for (const item of assets.slice(0, 8)) {
    console.log(`${item.kb.toFixed(2)} KB  ${item.file}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
