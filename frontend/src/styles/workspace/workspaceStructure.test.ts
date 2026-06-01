import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const workspaceStyleDir = resolve(__dirname);

function readStyle(fileName: string) {
  return readFileSync(resolve(workspaceStyleDir, fileName), "utf8");
}

describe("workspace styles structure", () => {
  it("keeps the workspace entry stylesheet below the growth threshold", () => {
    const source = readStyle("workspace.css");

    expect(source).toContain("@import \"./workspace-primitives.css\"");
    expect(source.split("\n").length).toBeLessThanOrEqual(1700);
  });
});
