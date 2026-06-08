import type { DownsamplePayload, DownsamplePoint, FilterPayload, SortPayload } from "./protocol";

export function filterItems<T extends Record<string, unknown>>(payload: FilterPayload<T>): T[] {
  const keyword = payload.keyword?.trim().toLowerCase();
  if (!keyword) return payload.items;
  const fields = payload.fields?.length ? payload.fields : Object.keys(payload.items[0] ?? {});
  return payload.items.filter((item) =>
    fields.some((field) => String(item[field] ?? "").toLowerCase().includes(keyword)),
  );
}

export function downsample<T extends DownsamplePoint>(payload: DownsamplePayload<T>): T[] {
  const { points, maxPoints } = payload;
  if (points.length <= maxPoints || maxPoints <= 0) return points;
  if (maxPoints === 1) return [points[points.length - 1]];
  const step = (points.length - 1) / (maxPoints - 1);
  return Array.from({ length: maxPoints }, (_, index) => points[Math.round(index * step)]);
}

export function sortItems<T extends object>(payload: SortPayload<T>): T[] {
  const direction = payload.direction === "asc" ? 1 : -1;
  const numeric = payload.numeric !== false;
  return payload.items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const compared = compareValues(fieldValue(left.item, payload.key), fieldValue(right.item, payload.key), numeric, direction);
      return compared === 0 ? left.index - right.index : compared;
    })
    .map(({ item }) => item);
}

export function deriveSummary(items: Array<Record<string, unknown>>): Record<string, number> {
  return {
    total: items.length,
    with_score: items.filter((item) => Number.isFinite(Number(item.production_score ?? item.score))).length,
  };
}

function compareValues(left: unknown, right: unknown, numeric: boolean, direction: 1 | -1): number {
  if (numeric) {
    const leftNumber = Number(left);
    const rightNumber = Number(right);
    const leftFinite = Number.isFinite(leftNumber);
    const rightFinite = Number.isFinite(rightNumber);
    if (leftFinite && rightFinite) return (leftNumber - rightNumber) * direction;
    if (leftFinite !== rightFinite) return leftFinite ? -1 : 1;
  }
  return String(left ?? "").localeCompare(String(right ?? ""), "zh-Hans-CN", { numeric: true }) * direction;
}

function fieldValue(item: object, key: string): unknown {
  return Object.prototype.hasOwnProperty.call(item, key) ? (item as Record<string, unknown>)[key] : undefined;
}
