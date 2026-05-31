import { describe, expect, it } from "vitest";
import type { StockCardView } from "../workspace-shared/workspaceTypes";
import { countChangedMonitorCardRenders, createStableCardListMapper } from "./stableMonitorCards";

interface TestMonitorItem {
  id: string;
  score: number;
}

describe("stable monitor cards", () => {
  it("keeps unchanged item references stable so memoized card leaves only render changed cards", () => {
    const toCard = (item: TestMonitorItem): StockCardView => ({
      name: item.id,
      symbol: item.id,
      priceText: "1.000",
      changeText: "0.00%",
      scoreText: String(item.score),
      riskText: "低",
      actionText: `score-${item.score}`,
      details: `score ${item.score}`,
      tone: "neutral",
    });
    const stableMap = createStableCardListMapper<TestMonitorItem>({
      keyOf: (item) => item.id,
      signatureOf: (item) => `${item.id}:${item.score}`,
      mapItem: toCard,
    });

    const first = stableMap([
      { id: "600000", score: 10 },
      { id: "600001", score: 20 },
      { id: "600002", score: 30 },
    ]);
    const nextItems = [
      { id: "600000", score: 10 },
      { id: "600001", score: 21 },
      { id: "600002", score: 30 },
    ];
    const unstableNext = nextItems.map(toCard);
    const stableNext = stableMap(nextItems);

    expect(countChangedMonitorCardRenders(first, unstableNext)).toBe(3);
    expect(countChangedMonitorCardRenders(first, stableNext)).toBe(1);
    expect(stableNext[0]).toBe(first[0]);
    expect(stableNext[1]).not.toBe(first[1]);
    expect(stableNext[2]).toBe(first[2]);
  });
});
