export const RUNTIME_API_BASE_URL_STORAGE_KEY = "tquant.desktop.apiBaseUrl";

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export interface ResolveApiUrlOptions {
  buildBase?: string;
  storage?: StorageLike;
}

export function normalizeApiBaseUrl(value: unknown): string {
  if (typeof value !== "string") return "";
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  if (!/^https?:\/\/[\w.-]+(?::\d+)?(?:\/.*)?$/i.test(trimmed)) return "";
  return trimmed;
}

export function getRuntimeApiBaseUrl(storage: StorageLike | undefined = browserStorage()): string {
  if (!storage) return "";
  return normalizeApiBaseUrl(storage.getItem(RUNTIME_API_BASE_URL_STORAGE_KEY));
}

export function setRuntimeApiBaseUrl(value: string, storage: StorageLike | undefined = browserStorage()): string {
  const normalized = normalizeApiBaseUrl(value);
  if (!storage) return normalized;
  if (normalized) storage.setItem(RUNTIME_API_BASE_URL_STORAGE_KEY, normalized);
  else storage.removeItem(RUNTIME_API_BASE_URL_STORAGE_KEY);
  return normalized;
}

export function clearRuntimeApiBaseUrl(storage: StorageLike | undefined = browserStorage()): void {
  storage?.removeItem(RUNTIME_API_BASE_URL_STORAGE_KEY);
}

export function getBuildApiBaseUrl(buildBase = import.meta.env.VITE_API_BASE_URL ?? ""): string {
  return normalizeApiBaseUrl(buildBase);
}

export function getEffectiveApiBaseUrl(options: ResolveApiUrlOptions = {}): string {
  return getRuntimeApiBaseUrl(options.storage) || getBuildApiBaseUrl(options.buildBase);
}

export function resolveApiUrl(path: string, options: ResolveApiUrlOptions = {}): string {
  if (/^https?:\/\//i.test(path)) return path;
  const base = getEffectiveApiBaseUrl(options);
  if (!base) return ensureLeadingSlash(path);
  return `${base}${ensureLeadingSlash(path)}`;
}

function ensureLeadingSlash(path: string): string {
  return path.startsWith("/") ? path : `/${path}`;
}

function browserStorage(): StorageLike | undefined {
  if (typeof window === "undefined") return undefined;
  return window.localStorage;
}
