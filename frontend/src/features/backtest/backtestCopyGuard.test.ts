import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function readLocal(fileName: string) {
  return readFileSync(new URL(fileName, import.meta.url), "utf8");
}

describe("backtest copy guard", () => {
  it("keeps internal OOS and IS copy behind plain-language labels", () => {
    const validation = readLocal("./ValidationPanel.tsx");
    const optimization = readLocal("./OptimizationPanel.tsx");

    expect(validation).not.toContain(">IS ");
    expect(validation).not.toContain(">OOS ");
    expect(optimization).not.toContain("OOS 降级");
    expect(optimization).not.toContain("IS/OOS 对比");
  });
});
