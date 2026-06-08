import { describe, expect, it } from "vitest";
import { downsample, filterItems, sortItems } from "../computeSync";

describe("frontend-next compute fallback", () => {
  it("filters display rows without mutating production ordering", () => {
    const rows = [
      { symbol: "000001", name: "平安银行", production_score: 88 },
      { symbol: "600000", name: "浦发银行", production_score: 91 },
    ];
    expect(filterItems({ items: rows, keyword: "浦发", fields: ["name"] })).toEqual([rows[1]]);
    expect(rows.map((row) => row.symbol)).toEqual(["000001", "600000"]);
  });

  it("downsamples chart points with a deterministic sync path", () => {
    const points = Array.from({ length: 10 }, (_, index) => ({ time: index, value: index }));
    expect(downsample({ points, maxPoints: 4 }).map((point) => point.value)).toEqual([0, 3, 6, 9]);
  });

  it("keeps chart endpoints while downsampling uneven point counts", () => {
    const points = Array.from({ length: 11 }, (_, index) => ({ time: index, value: index }));
    const sampled = downsample({ points, maxPoints: 4 });
    expect(sampled).toHaveLength(4);
    expect(sampled.at(0)).toEqual(points[0]);
    expect(sampled.at(-1)).toEqual(points.at(-1));
    expect(downsample({ points, maxPoints: 1 })).toEqual([points.at(-1)]);
  });

  it("sorts display rows stably while keeping rows with missing scores last", () => {
    const rows = [
      { symbol: "000001", score: 82 },
      { symbol: "600000", score: 91 },
      { symbol: "510300" },
      { symbol: "300750", score: 91 },
    ];
    expect(sortItems({ items: rows, key: "score", direction: "desc", numeric: true }).map((row) => row.symbol)).toEqual(["600000", "300750", "000001", "510300"]);
    expect(rows.map((row) => row.symbol)).toEqual(["000001", "600000", "510300", "300750"]);
  });
});
