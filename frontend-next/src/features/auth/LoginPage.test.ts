import { describe, expect, it } from "vitest";
import { safeRedirectPath } from "./LoginPage";

describe("safeRedirectPath", () => {
  it("allows internal /next routes", () => {
    expect(safeRedirectPath("/next/analysis?symbol=000001")).toBe("/next/analysis?symbol=000001");
    expect(safeRedirectPath("/analysis?symbol=000001")).toBe("/analysis?symbol=000001");
    expect(safeRedirectPath("/monitor/market")).toBe("/monitor/market");
  });

  it("falls back for external or non-next redirects", () => {
    expect(safeRedirectPath("https://example.com/next/analysis")).toBe("/next/monitor");
    expect(safeRedirectPath("//example.com/next/analysis")).toBe("/next/monitor");
    expect(safeRedirectPath("/login")).toBe("/next/monitor");
    expect(safeRedirectPath(null)).toBe("/next/monitor");
  });
});
