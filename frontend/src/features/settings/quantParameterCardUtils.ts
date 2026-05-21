export type QuantFieldSpec = {
  path: string;
  label: string;
  min: number;
  max: number;
  step?: string;
  suffix?: string;
};

export function getNested(source: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((value, key) => (isRecord(value) ? value[key] : undefined), source);
}

export function setNested(source: Record<string, unknown>, path: string, value: number | boolean) {
  const parts = path.split(".");
  let cursor: Record<string, unknown> = source;
  for (const key of parts.slice(0, -1)) {
    if (!isRecord(cursor[key])) cursor[key] = {};
    cursor = cursor[key] as Record<string, unknown>;
  }
  cursor[parts[parts.length - 1]] = value;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function structuredCloneSafe<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
