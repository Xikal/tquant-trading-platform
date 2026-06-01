import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const rootDir = resolve(__dirname, "..", "..");

function projectPath(path: string) {
  return resolve(rootDir, path);
}

function readProjectFile(path: string) {
  return readFileSync(projectPath(path), "utf8");
}

describe("frontend issue inventory guards", () => {
  it("keeps the unmounted factor-mining UI retired from the frontend bundle", () => {
    expect(existsSync(projectPath("src/features/factor-mining"))).toBe(false);
    expect(existsSync(projectPath("src/api/factorMining.ts"))).toBe(false);
    expect(existsSync(projectPath("src/stores/factorMiningUiStore.ts"))).toBe(false);
    expect(readProjectFile("src/state/serverQueries/queryKeys.ts")).not.toContain("factorMining");
  });

  it("keeps visible metric labels plain-language in paper and strategy tracking surfaces", () => {
    const files = [
      "src/features/paper/PaperTradingPerformance.tsx",
      "src/features/paper/PortfolioExecutionPanel.tsx",
      "src/features/strategy-tracking/DriftMonitorPanel.tsx",
      "src/features/strategy-tracking/PromotionReviewPanel.tsx",
    ];

    for (const file of files) {
      expect(readProjectFile(file)).not.toContain('"PF"');
      expect(readProjectFile(file)).not.toContain(">PF<");
    }
  });

  it("keeps responsive and performance mock signal copy observation-only", () => {
    const scripts = [
      "scripts/smoke-responsive.mjs",
      "scripts/perf-profile.mjs",
    ];

    for (const script of scripts) {
      const source = readProjectFile(script);
      expect(source).not.toContain('buy_signal_text: "接近买点"');
      expect(source).not.toContain('signal_text: "接近买点"');
      expect(source).not.toContain('label: "首次推荐"');
      expect(source).not.toContain('buy_signal_hint: "等待确认"');
    }
  });
});
