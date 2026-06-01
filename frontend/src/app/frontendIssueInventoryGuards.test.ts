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
});
