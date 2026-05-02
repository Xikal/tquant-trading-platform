import { describe, expect, it } from "vitest";

import { formatAmount, formatPct, formatPrice, plainTradingText, shortTime, toneFromChange } from "./workspaceFormatters";

describe("workspaceFormatters", () => {
  it("formats finance values with stable precision", () => {
    expect(formatPrice(4.081)).toBe("4.081");
    expect(formatPrice(184.3)).toBe("184.30");
    expect(formatPct(1.234)).toBe("+1.23%");
    expect(formatPct(-0.42)).toBe("-0.42%");
    expect(formatAmount(123_456_789)).toBe("1.2亿");
  });

  it("maps trading jargon to plain language", () => {
    expect(plainTradingText("弱扩散防守，轮动过快")).toContain("指数可能被少数大票托住");
    expect(plainTradingText("弱扩散防守，轮动过快")).toContain("热点切换太快");
  });

  it("uses A-share tone semantics", () => {
    expect(toneFromChange(1)).toBe("up");
    expect(toneFromChange(-1)).toBe("down");
    expect(toneFromChange(0)).toBe("neutral");
  });

  it("renders Beijing time for backend timestamps", () => {
    expect(shortTime("2026-04-29 09:41:23")).toBe("09:41:23");
  });
});
