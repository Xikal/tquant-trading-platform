import { existsSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../", import.meta.url).pathname;
const assetsDir = join(root, "dist", "assets");
const maxChunkBytes = 360 * 1024;
const maxTotalBytes = 1_250 * 1024;

if (!existsSync(assetsDir)) {
  console.log("Bundle budget skipped: dist/assets not found");
  process.exit(0);
}

const chunks = readdirSync(assetsDir)
  .filter((name) => name.endsWith(".js"))
  .map((name) => ({ name, bytes: statSync(join(assetsDir, name)).size }));

const errors = [];
const total = chunks.reduce((sum, chunk) => sum + chunk.bytes, 0);
for (const chunk of chunks) {
  if (chunk.bytes > maxChunkBytes) errors.push(`${chunk.name}: ${chunk.bytes} bytes exceeds chunk budget ${maxChunkBytes}`);
}
if (total > maxTotalBytes) errors.push(`total js: ${total} bytes exceeds budget ${maxTotalBytes}`);

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`Bundle budget passed (${chunks.length} chunks, ${total} bytes)`);
