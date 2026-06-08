import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { PNG } from "pngjs";

const pages = [
  ["monitor-action-web.png", "/monitor", "/next/monitor"],
  ["monitor-market-web.png", "/monitor/market", "/next/monitor/market"],
  ["paper-web.png", "/paper", "/next/paper"],
  ["strategy-tracking-web.png", "/strategy-tracking", "/next/strategy-tracking"],
  ["analysis-web.png", "/analysis", "/next/analysis"],
  ["playbook-web.png", "/playbook", "/next/playbook"],
  ["backtest-web.png", "/backtest", "/next/backtest"],
  ["data-console-web.png", "/data", "/next/data"],
  ["settings-web.png", "/settings", "/next/settings"],
];

const screenshotDir = resolve("../docs/reports/frontend-next-screenshots-2026-06-05");
const outputDir = resolve("../docs/reports/frontend-next-visual-review-2026-06-05");
const checklistPath = resolve("../docs/reports/frontend-next-visual-signoff-2026-06-05.md");

mkdirSync(outputDir, { recursive: true });
const rows = [];

for (const [image, legacyRoute, nextRoute] of pages) {
  const legacyPath = resolve(screenshotDir, `legacy-${image}`);
  const nextPath = resolve(screenshotDir, image);
  if (!existsSync(legacyPath) || !existsSync(nextPath)) {
    rows.push({ legacyRoute, nextRoute, status: "missing-screenshot", reviewPath: "" });
    continue;
  }
  const reviewPath = resolve(outputDir, `review-${image}`);
  const similarity = composeReview(legacyPath, nextPath, reviewPath);
  rows.push({ legacyRoute, nextRoute, status: "ready-for-human-signoff", similarity, reviewPath });
}

const markdown = [
  "# Frontend Next Visual Signoff",
  "",
  "日期：2026-06-05",
  "范围：旧 `frontend/` 与新 `frontend-next/` 1440x900 认证态截图人工签收清单。",
  "",
  "说明：本文件不代表已经人工签收；它固定了逐页签收证据。签收前需打开对应 review PNG，确认信息层级、密度、颜色、表格/卡片、空态/错误态、关键按钮和滚动区域是否接受。",
  "",
  "| 旧路由 | 新路由 | 状态 | sample_similarity | Review PNG | 人工结论 |",
  "|---|---|---|---:|---|---|",
  ...rows.map((row) =>
    `| ${row.legacyRoute} | ${row.nextRoute} | ${row.status} | ${row.similarity ?? ""} | ${row.reviewPath ? `[${basename(row.reviewPath)}](${row.reviewPath})` : ""} | 待签收 |`,
  ),
  "",
  "人工签收 Gate：全部页面结论从 `待签收` 改为 `通过` 后，才可把视觉项视为 cutover 前完成。",
  "",
];

writeFileSync(checklistPath, markdown.join("\n"));
console.log(JSON.stringify({ checklistPath, outputDir, rows }, null, 2));

function composeReview(legacyPath, nextPath, outputPath) {
  const legacy = PNG.sync.read(readFileSync(legacyPath));
  const next = PNG.sync.read(readFileSync(nextPath));
  const gutter = 24;
  const width = legacy.width + next.width + gutter;
  const height = Math.max(legacy.height, next.height);
  const out = new PNG({ width, height, colorType: 6 });
  fill(out, 248, 250, 252, 255);
  blit(legacy, out, 0, 0);
  blit(next, out, legacy.width + gutter, 0);
  writeFileSync(outputPath, PNG.sync.write(out));
  return comparePng(legacy, next);
}

function fill(png, r, g, b, a) {
  for (let y = 0; y < png.height; y += 1) {
    for (let x = 0; x < png.width; x += 1) {
      const idx = (png.width * y + x) << 2;
      png.data[idx] = r;
      png.data[idx + 1] = g;
      png.data[idx + 2] = b;
      png.data[idx + 3] = a;
    }
  }
}

function blit(src, dest, dx, dy) {
  for (let y = 0; y < src.height; y += 1) {
    for (let x = 0; x < src.width; x += 1) {
      const srcIdx = (src.width * y + x) << 2;
      const destIdx = (dest.width * (dy + y) + dx + x) << 2;
      dest.data[destIdx] = src.data[srcIdx];
      dest.data[destIdx + 1] = src.data[srcIdx + 1];
      dest.data[destIdx + 2] = src.data[srcIdx + 2];
      dest.data[destIdx + 3] = src.data[srcIdx + 3];
    }
  }
}

function comparePng(a, b) {
  const sampleWidth = Math.min(a.width, b.width);
  const sampleHeight = Math.min(a.height, b.height);
  const step = 12;
  let samples = 0;
  let totalDelta = 0;
  for (let y = 0; y < sampleHeight; y += step) {
    for (let x = 0; x < sampleWidth; x += step) {
      const aIdx = (a.width * y + x) << 2;
      const bIdx = (b.width * y + x) << 2;
      totalDelta +=
        Math.abs(a.data[aIdx] - b.data[bIdx]) +
        Math.abs(a.data[aIdx + 1] - b.data[bIdx + 1]) +
        Math.abs(a.data[aIdx + 2] - b.data[bIdx + 2]);
      samples += 1;
    }
  }
  return Number((1 - totalDelta / (samples * 255 * 3)).toFixed(4));
}
