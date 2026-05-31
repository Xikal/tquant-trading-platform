import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("web entry performance", () => {
  it("keeps service worker registration out of the first-screen static import graph", () => {
    const source = readFileSync(resolve(__dirname, "main.tsx"), "utf8");

    expect(source).not.toContain('from "./registerServiceWorker"');
    expect(source).toContain('import("./registerServiceWorker")');
  });
});
