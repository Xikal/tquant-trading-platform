import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("PaperOrderEntryModal copy", () => {
  it("uses production-signal import copy instead of recommendation wording", () => {
    const source = readFileSync(new URL("./PaperOrderEntryModal.tsx", import.meta.url), "utf8");

    expect(source).toContain("从生产买入信号导入");
    expect(source).toContain("生产买入信号加载失败");
    expect(source).not.toContain("今日推荐");
  });
});
