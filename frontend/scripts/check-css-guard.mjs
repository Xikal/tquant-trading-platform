import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const srcRoot = fileURLToPath(new URL("../src", import.meta.url));
const baselinePath = fileURLToPath(new URL("./css-guard-baseline.json", import.meta.url));

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

const allFiles = walk(srcRoot);

// 规则 1：禁止 .part-N.css（沿用旧规则）——使用语义文件 / tokens / CSS Module / antd 主题变量。
const partCss = allFiles
  .filter((file) => /\.part-\d+\.css$/.test(file))
  .map((file) => relative(srcRoot, file));

// 规则 2：棘轮指标（只许降不许升），随重构 Phase 推进逐步降基线。
// tokens.ts 是设计 Token 唯一源，允许出现 hex；测试与生成代码不计入。
const TOKEN_SOURCE = /ui[/\\]theme[/\\]tokens\.ts$/;
const codeFiles = allFiles.filter(
  (file) =>
    /\.(ts|tsx)$/.test(file) &&
    !/\.test\.(ts|tsx)$/.test(file) &&
    !/[/\\]generated[/\\]/.test(file),
);

const metrics = { inlineStyleObjects: 0, cssPropertiesFiles: 0, smallFonts: 0, hardcodedHex: 0 };
const hexFiles = new Set();
const smallFontFiles = new Set();

for (const file of codeFiles) {
  const text = readFileSync(file, "utf8");
  metrics.inlineStyleObjects += (text.match(/style=\{\{/g) || []).length;
  if (/\bCSSProperties\b/.test(text)) {
    metrics.cssPropertiesFiles += 1;
  }
  const small = (text.match(/fontSize:\s*(9|10|11)\b/g) || []).length;
  if (small) {
    metrics.smallFonts += small;
    smallFontFiles.add(relative(srcRoot, file));
  }
  if (!TOKEN_SOURCE.test(file)) {
    const hex = (text.match(/#[0-9a-fA-F]{3,8}\b/g) || []).length;
    if (hex) {
      metrics.hardcodedHex += hex;
      hexFiles.add(relative(srcRoot, file));
    }
  }
}

if (process.argv.includes("--update-baseline")) {
  writeFileSync(baselinePath, `${JSON.stringify(metrics, null, 2)}\n`);
  console.log("CSS guard baseline updated:", metrics);
  process.exit(0);
}

const errors = [];

if (partCss.length) {
  errors.push(`禁止 .part-N.css：\n  ${partCss.join("\n  ")}`);
}

if (existsSync(baselinePath)) {
  const baseline = JSON.parse(readFileSync(baselinePath, "utf8"));
  for (const key of Object.keys(metrics)) {
    const limit = baseline[key] ?? 0;
    if (metrics[key] > limit) {
      errors.push(
        `${key} 回升：基线 ${limit} → 当前 ${metrics[key]}（只许降不许升；先迁移到 tokens / 原语，再用 --update-baseline 降基线）`,
      );
    }
  }
} else {
  console.warn(
    "未找到 css-guard-baseline.json；运行 `node scripts/check-css-guard.mjs --update-baseline` 生成基线。",
  );
}

if (errors.length) {
  console.error(`CSS guard failed:\n${errors.join("\n")}`);
  process.exit(1);
}

console.log("CSS guard passed:", metrics);
