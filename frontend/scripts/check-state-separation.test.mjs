import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const script = new URL("./check-state-separation.mjs", import.meta.url);

describe("check-state-separation", () => {
  it("fails when a Zustand store keeps server response data", () => {
    const root = mkdtempSync(join(tmpdir(), "state-separation-"));
    try {
      writeFileSync(
        join(root, "badStore.ts"),
        `import { create } from "zustand";
         import type { LowBuyPriorityBoardResult } from "../types";
         interface BadStore {
           priorityBoard: LowBuyPriorityBoardResult | null;
           setPriorityBoard: (value: LowBuyPriorityBoardResult | null) => void;
         }
         export const useBadStore = create<BadStore>((set) => ({
           priorityBoard: null,
           setPriorityBoard: (priorityBoard) => set({ priorityBoard }),
         }));`,
      );

      expect(() => execFileSync("node", [script.pathname, "--stores-root", root], { encoding: "utf8" }))
        .toThrow(/server state/i);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it("passes for UI-only store fields", () => {
    const root = mkdtempSync(join(tmpdir(), "state-separation-"));
    try {
      writeFileSync(
        join(root, "goodStore.ts"),
        `import { create } from "zustand";
         interface GoodStore {
           activeTab: string;
           selectedItemId: string | null;
           expandedKeys: string[];
           setActiveTab: (value: string) => void;
         }
         export const useGoodStore = create<GoodStore>((set) => ({
           activeTab: "monitor",
           selectedItemId: null,
           expandedKeys: [],
           setActiveTab: (activeTab) => set({ activeTab }),
         }));`,
      );

      expect(execFileSync("node", [script.pathname, "--stores-root", root], { encoding: "utf8" }))
        .toContain("State separation guard passed.");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});
