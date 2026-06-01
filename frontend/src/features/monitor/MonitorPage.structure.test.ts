import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const monitorDir = resolve(__dirname);

function readMonitorFile(fileName: string) {
  return readFileSync(resolve(monitorDir, fileName), "utf8");
}

describe("MonitorPage structure", () => {
  it("keeps the page shell below the page-size threshold by extracting leaf panels", () => {
    const pageSource = readMonitorFile("MonitorPage.tsx");

    expect(pageSource.split("\n").length).toBeLessThanOrEqual(600);
    expect(pageSource).not.toContain("function MonitorReviewPanel");
    expect(pageSource).not.toContain("function HourlyAllMarketPulse");
    expect(existsSync(resolve(monitorDir, "MonitorPage.panels.tsx"))).toBe(true);
  });
});
