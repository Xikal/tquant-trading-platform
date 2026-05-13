const OFFLINE_CACHE_NAME = "tquant-api-v2";
const OFFLINE_CACHE_PREFIX = "/__offline_cache__/";
const OFFLINE_CACHE_TTL_MS = 30 * 60 * 1000;
const OFFLINE_CACHEABLE_PATHS = ["/agent/reports/daily", "/market/breadth", "/strategies/meta"];
const OFFLINE_CACHE_SENSITIVE_KEYS = new Set([
  "token",
  "apikey",
  "api_key",
  "password",
  "passwd",
  "secret",
  "database_url",
  "authorization",
  "cookie",
  "key",
]);

type OfflinePayload<T> = {
  expiresAt: number;
  payload: T;
};

export function canPersistOffline(path: string): boolean {
  return OFFLINE_CACHEABLE_PATHS.some((prefix) => path.startsWith(prefix));
}

export async function writeOfflineCache(
  path: string,
  payload: unknown,
  authScopeToken: string,
): Promise<void> {
  if (!canPersistOffline(path)) {
    return;
  }
  const cache = await openOfflineCache();
  if (!cache) {
    return;
  }
  const body: OfflinePayload<unknown> = {
    expiresAt: Date.now() + OFFLINE_CACHE_TTL_MS,
    payload: sanitizeOfflinePayload(payload),
  };
  try {
    await cache.put(
      offlineCacheRequest(path, authScopeToken),
      new Response(JSON.stringify(body), {
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      }),
    );
  } catch {
    // Cache Storage is best-effort only.
  }
}

export async function readOfflineCache<T>(path: string, authScopeToken: string): Promise<T | null> {
  if (!canPersistOffline(path)) {
    return null;
  }
  const cache = await openOfflineCache();
  if (!cache) {
    return null;
  }
  const request = offlineCacheRequest(path, authScopeToken);
  const response = await cache.match(request);
  if (!response) {
    return null;
  }
  try {
    const parsed = (await response.json()) as OfflinePayload<T>;
    if (!parsed.expiresAt || parsed.expiresAt <= Date.now()) {
      try {
        await cache.delete(request);
      } catch {
        // Ignore best-effort cleanup failures.
      }
      return null;
    }
    return parsed.payload ?? null;
  } catch {
    try {
      await cache.delete(request);
    } catch {
      // Ignore best-effort cleanup failures.
    }
    return null;
  }
}

export async function clearOfflineCache(): Promise<void> {
  const cache = await openOfflineCache();
  if (!cache) {
    return;
  }
  try {
    const keys = await cache.keys();
    await Promise.all(
      keys
        .filter((request) => request.url.includes(OFFLINE_CACHE_PREFIX))
        .map((request) => cache.delete(request)),
    );
  } catch {
    // Ignore best-effort cleanup failures.
  }
}

export function offlineAuthScope(token: string): string {
  let hash = 5381;
  for (let index = 0; index < token.length; index += 1) {
    hash = (hash * 33) ^ token.charCodeAt(index);
  }
  return `${hash >>> 0}`;
}

async function openOfflineCache(): Promise<Cache | null> {
  if (typeof window === "undefined" || !("caches" in window)) {
    return null;
  }
  try {
    return await window.caches.open(OFFLINE_CACHE_NAME);
  } catch {
    return null;
  }
}

function offlineCacheRequest(path: string, authScopeToken: string): Request {
  const normalizedPath = encodeURIComponent(path);
  const key = `${OFFLINE_CACHE_PREFIX}${offlineAuthScope(authScopeToken)}:${normalizedPath}`;
  return new Request(new URL(key, window.location.origin).toString(), { method: "GET" });
}

function sanitizeOfflinePayload(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeOfflinePayload(item));
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  const next: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (isSensitiveOfflineCacheKey(key)) {
      continue;
    }
    next[key] = sanitizeOfflinePayload(item);
  }
  return next;
}

function isSensitiveOfflineCacheKey(key: string): boolean {
  const normalized = key.trim().toLowerCase();
  const compact = normalized.replace(/[^a-z0-9]/g, "");
  if (OFFLINE_CACHE_SENSITIVE_KEYS.has(normalized) || OFFLINE_CACHE_SENSITIVE_KEYS.has(compact)) {
    return true;
  }
  return (
    compact.includes("token") ||
    compact.includes("apikey") ||
    compact.includes("password") ||
    compact.includes("passwd") ||
    compact.includes("secret") ||
    compact.includes("databaseurl") ||
    compact.includes("authorization") ||
    compact.includes("cookie")
  );
}
