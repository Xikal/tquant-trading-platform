import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function readLocal(fileName: string) {
  return readFileSync(new URL(fileName, import.meta.url), "utf8");
}

describe("backtest copy guard", () => {
  it("keeps internal OOS and IS copy behind plain-language labels", () => {
    const validation = readLocal("./ValidationPanel.tsx");
    const optimization = readLocal("./OptimizationPanel.tsx");
    const capacity = readLocal("./MLCapacityPanel.tsx");
    const dashboard = readLocal("./BacktestDashboard.panels.tsx");
    const etfT0 = readLocal("./EtfT0BacktestPanel.tsx");
    const compare = readLocal("./ComparePanel.tsx");

    expect(validation).not.toContain(">IS ");
    expect(validation).not.toContain(">OOS ");
    expect(optimization).not.toContain("OOS 降级");
    expect(optimization).not.toContain("IS/OOS 对比");
    expect(capacity).not.toContain("RL Shadow");
    for (const source of [dashboard, etfT0, compare, optimization, capacity]) {
      expect(source).not.toContain("MaxDD");
      expect(source).not.toContain("PF");
      expect(source).not.toContain("Paper 样本");
    }
  });
});
