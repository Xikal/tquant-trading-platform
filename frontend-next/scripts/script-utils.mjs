import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";

export async function startServer(port, options = {}) {
  const baseURL = `http://127.0.0.1:${port}`;
  const child = spawn("npm", ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
    cwd: options.cwd,
    env: { ...process.env, ...(options.env ?? {}) },
    stdio: "ignore",
    detached: false,
  });
  await waitForServer(baseURL);
  return { baseURL, child };
}

export async function waitForServer(url) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // wait
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

export function stopServer(server) {
  server?.child?.kill("SIGTERM");
}

export function authStatusFromEnv() {
  return {
    access_token: tokenStatus(process.env.FRONTEND_AUTH_TOKEN || process.env.TQUANT_AUTH_TOKEN),
    admin_token: tokenStatus(process.env.FRONTEND_ADMIN_TOKEN || process.env.ADMIN_API_TOKEN),
  };
}

export function buildAuthHeaders() {
  const headers = {};
  const accessToken = process.env.FRONTEND_AUTH_TOKEN || process.env.TQUANT_AUTH_TOKEN || "";
  const adminToken = process.env.FRONTEND_ADMIN_TOKEN || process.env.ADMIN_API_TOKEN || "";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (adminToken) headers["X-Admin-Token"] = adminToken;
  return headers;
}

let cachedAccessToken = null;
let cachedAccessTokenBase = "";
const authCachePath = process.env.FRONTEND_NEXT_AUTH_CACHE || join(tmpdir(), "frontend-next-shadow-auth-token.json");

export async function ensureAccessToken(apiBase = process.env.API_BASE || "http://127.0.0.1:8000") {
  const existing = cachedAccessToken || process.env.FRONTEND_AUTH_TOKEN || process.env.TQUANT_AUTH_TOKEN || "";
  if (existing && cachedAccessTokenBase === apiBase) return existing;
  if (existing && (await accessTokenValid(apiBase, existing))) {
    cachedAccessToken = existing;
    cachedAccessTokenBase = apiBase;
    process.env.FRONTEND_AUTH_TOKEN = existing;
    return existing;
  }
  const cached = readCachedAccessToken(apiBase);
  if (cached && (await accessTokenValid(apiBase, cached))) {
    cachedAccessToken = cached;
    cachedAccessTokenBase = apiBase;
    process.env.FRONTEND_AUTH_TOKEN = cached;
    return cached;
  }
  if (process.env.FRONTEND_NEXT_AUTO_AUTH === "0") return existing;
  const registered = await registerSmokeUser(apiBase);
  cachedAccessToken = registered.accessToken;
  cachedAccessTokenBase = apiBase;
  process.env.FRONTEND_AUTH_TOKEN = registered.accessToken;
  writeCachedAccessToken(apiBase, registered.accessToken);
  return registered.accessToken;
}

export async function buildResolvedAuthHeaders(apiBase = process.env.API_BASE || "http://127.0.0.1:8000") {
  await ensureAccessToken(apiBase);
  return buildAuthHeaders();
}

export async function installAuthState(page, options = {}) {
  const accessToken = await ensureAccessToken(options.apiBase);
  const adminToken = process.env.FRONTEND_ADMIN_TOKEN || process.env.ADMIN_API_TOKEN || "";
  await page.addInitScript(
    ({ accessToken: injectedAccessToken, adminToken: injectedAdminToken }) => {
      if (injectedAccessToken) {
        window.localStorage.setItem("tquant:auth:access_token", injectedAccessToken);
        window.sessionStorage.setItem("tquant:auth:access_token", injectedAccessToken);
        window.localStorage.setItem("tquant:auth:persistence_mode", "session");
      }
      if (injectedAdminToken) {
        window.localStorage.setItem("tquant:admin_api_token", injectedAdminToken);
        window.sessionStorage.setItem("tquant:admin_api_token", injectedAdminToken);
      }
    },
    { accessToken, adminToken },
  );
  return authStatusFromEnv();
}

export async function detectAuthGate(page) {
  const finalUrl = page.url();
  const bodyText = await page.locator("body").innerText({ timeout: 1_000 }).catch(() => "");
  if (finalUrl.includes("/login") || /账号登录|登录进入工作台|USER ID|请输入手机号或账号/.test(bodyText)) {
    return "auth-required-login-screen";
  }
  return null;
}

async function accessTokenValid(apiBase, token) {
  try {
    const response = await fetch(`${apiBase}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function registerSmokeUser(apiBase) {
  const suffix = `${Date.now()}_${Math.floor(Math.random() * 10_000)}`;
  const response = await fetch(`${apiBase}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: `frontend_next_shadow_${suffix}`,
      password: `FrontNextShadow-${suffix}`,
      display_name: "frontend-next shadow",
      device_name: "frontend-next-shadow-validation",
    }),
  });
  const payload = await response.json().catch(() => null);
  if (response.status === 429) {
    const reused = await loginLatestLocalSmokeUser(apiBase);
    if (reused?.accessToken) return reused;
  }
  if (!response.ok || !payload?.access_token) {
    throw new Error(`Unable to register frontend-next shadow auth user: HTTP ${response.status}`);
  }
  return { accessToken: payload.access_token };
}

async function loginLatestLocalSmokeUser(apiBase) {
  if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/?$/.test(apiBase)) return null;
  let usernames;
  try {
    const dbPath = resolve("../backend/data/t_quant.db");
    const sql = `
select username from users
where username like 'frontend_next_shadow_%' or username like 'frontend_next_smoke_%'
order by created_at desc
limit 20;
`;
    usernames = execFileSync("sqlite3", [dbPath, sql], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] })
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  } catch {
    return null;
  }
  for (const username of usernames) {
    const password = smokePasswordForUsername(username);
    if (!password) continue;
    try {
      const response = await fetch(`${apiBase}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, device_name: "frontend-next-shadow-validation" }),
      });
      const payload = await response.json().catch(() => null);
      if (response.ok && payload?.access_token) return { accessToken: payload.access_token };
    } catch {
      // Try the next local smoke user.
    }
  }
  return null;
}

function smokePasswordForUsername(username) {
  if (username.startsWith("frontend_next_shadow_")) {
    return `FrontNextShadow-${username.slice("frontend_next_shadow_".length)}`;
  }
  if (username.startsWith("frontend_next_smoke_")) {
    return `FrontNextSmoke-${username.slice("frontend_next_smoke_".length)}`;
  }
  return "";
}

function readCachedAccessToken(apiBase) {
  try {
    const payload = JSON.parse(readFileSync(authCachePath, "utf8"));
    if (payload?.apiBase !== apiBase || typeof payload?.accessToken !== "string") return "";
    return payload.accessToken;
  } catch {
    return "";
  }
}

function writeCachedAccessToken(apiBase, accessToken) {
  try {
    mkdirSync(dirname(authCachePath), { recursive: true });
    writeFileSync(authCachePath, JSON.stringify({ apiBase, accessToken, updatedAt: new Date().toISOString() }, null, 2));
  } catch {
    // Auth cache is a local validation convenience only.
  }
}

function tokenStatus(value) {
  return value ? "provided" : "missing";
}

export async function hashPayload(payload) {
  const crypto = await import("node:crypto");
  return crypto.createHash("sha256").update(stableStringify(payload)).digest("hex");
}

export function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function shapeOf(value, depth = 0) {
  if (depth > 3) return typeof value;
  if (Array.isArray(value)) return value.length ? [shapeOf(value[0], depth + 1)] : [];
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, shapeOf(value[key], depth + 1)]));
  }
  return typeof value;
}
