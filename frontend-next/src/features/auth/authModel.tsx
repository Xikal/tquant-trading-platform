import { createContext, createResource, createSignal, onMount, useContext, type JSX } from "solid-js";
import {
  applyAuthTokenResponse,
  authApi,
  canAttemptAuthRefresh,
  clearAuthRefreshSession,
  currentRefreshTokenRemembered,
  getAuthAccessToken,
  getCachedAuthUser,
  getAuthRefreshToken,
  setCachedAuthUser,
  setAuthAccessToken,
} from "../../shared/api/auth";
import { ApiError, errorMessage } from "../../shared/api/errors";
import type { AuthMfaSetupResponse, AuthTokenResponse, AuthUser } from "../../shared/api/types";


export type AuthStatus = "restoring" | "anonymous" | "authenticated";

export interface AuthModel {
  status: () => AuthStatus;
  user: () => AuthUser | null;
  error: () => string;
  isAdmin: () => boolean;
  restore: () => Promise<void>;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  setupTotp: () => Promise<AuthMfaSetupResponse>;
  enableTotp: (code: string) => Promise<void>;
  disableTotp: (code: string) => Promise<void>;
}

export interface LoginPayload {
  username: string;
  password: string;
  mfa_code?: string;
  remember?: boolean;
}

export interface RegisterPayload {
  username: string;
  password: string;
  display_name?: string;
  remember?: boolean;
}

export type AuthRefreshAttempt = "refreshed" | "unavailable" | "invalid" | "failed";

const AuthContext = createContext<AuthModel>();
const AUTH_RESTORE_TIMEOUT_MS = 4_000;

export function AuthProvider(props: { children: JSX.Element }) {
  const [status, setStatus] = createSignal<AuthStatus>("restoring");
  const [user, setUser] = createSignal<AuthUser | null>(null);
  const [error, setError] = createSignal("");

  async function applyToken(result: AuthTokenResponse, remember = true) {
    applyAuthTokenResponse(result, remember);
    setUser(result.user);
    setStatus("authenticated");
    setError("");
  }

  async function restore() {
    const cachedUser = getCachedAuthUser();
    const cachedAccessToken = getAuthAccessToken();
    if (cachedAccessToken && cachedUser) {
      setUser(cachedUser);
      setStatus("authenticated");
      setError("");
    } else {
      setStatus("restoring");
    }
    try {
      const current = await authApi.me({ timeoutMs: AUTH_RESTORE_TIMEOUT_MS, retry: false });
      setUser(current.user);
      setCachedAuthUser(current.user);
      setStatus("authenticated");
      setError("");
    } catch (firstError) {
      const couldAttemptRefresh = canAttemptAuthRefresh();
      const refreshAttempt = await tryRefresh();
      if (refreshAttempt === "refreshed") return;
      if (shouldClearStoredAuthAfterRestore(firstError, refreshAttempt, couldAttemptRefresh)) {
        setAuthAccessToken("");
        clearAuthRefreshSession();
        setCachedAuthUser(null);
        setUser(null);
        setStatus("anonymous");
        setError("");
        return;
      }
      if (cachedAccessToken && cachedUser) {
        setUser(cachedUser);
        setStatus("authenticated");
        setError(errorMessage(firstError));
        return;
      }
      setUser(null);
      setStatus("anonymous");
      if (firstError instanceof ApiError && firstError.status === 401) {
        setError("");
      } else {
        setError(errorMessage(firstError));
      }
    }
  }

  async function tryRefresh(): Promise<AuthRefreshAttempt> {
    const refreshToken = getAuthRefreshToken();
    if (!canAttemptAuthRefresh()) return "unavailable";
    try {
      const result = await authApi.refresh(
        { refresh_token: refreshToken },
        currentRefreshTokenRemembered(),
        { timeoutMs: AUTH_RESTORE_TIMEOUT_MS, retry: false },
      );
      await applyToken(result, currentRefreshTokenRemembered());
      return "refreshed";
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return "invalid";
      return "failed";
    }
  }

  const model: AuthModel = {
    status,
    user,
    error,
    isAdmin: () => user()?.roles?.includes("admin") ?? false,
    restore,
    login: async (payload) => {
      const result = await authApi.login({
        username: payload.username,
        password: payload.password,
        mfa_code: payload.mfa_code ?? "",
        device_name: "frontend-next-web",
      }, payload.remember ?? true);
      await applyToken(result, payload.remember ?? true);
    },
    register: async (payload) => {
      const result = await authApi.register({
        username: payload.username,
        password: payload.password,
        display_name: payload.display_name ?? payload.username,
        device_name: "frontend-next-web",
      }, payload.remember ?? true);
      await applyToken(result, payload.remember ?? true);
    },
    logout: async () => {
      const refreshToken = getAuthRefreshToken();
      setAuthAccessToken("");
      clearAuthRefreshSession();
      setCachedAuthUser(null);
      setUser(null);
      setStatus("anonymous");
      await authApi.logout({ refresh_token: refreshToken }).catch(() => undefined);
    },
    setupTotp: () => authApi.setupTotp(),
    enableTotp: async (code) => {
      const result = await authApi.enableTotp({ code });
      setUser(result.user);
    },
    disableTotp: async (code) => {
      const result = await authApi.disableTotp({ code });
      setUser(result.user);
    },
  };

  onMount(() => {
    void restore();
  });

  return <AuthContext.Provider value={model}>{props.children}</AuthContext.Provider>;
}

export function useAuth() {
  const model = useContext(AuthContext);
  if (!model) throw new Error("useAuth must be used inside AuthProvider");
  return model;
}

export function createAuthResource<T>(source: () => T) {
  const auth = useAuth();
  return createResource(() => (auth.status() === "authenticated" ? source() : undefined), (value) => value);
}

export function shouldClearStoredAuthAfterRestore(firstError: unknown, refreshAttempt: AuthRefreshAttempt, couldAttemptRefresh: boolean): boolean {
  if (refreshAttempt === "invalid") return true;
  return !couldAttemptRefresh && firstError instanceof ApiError && firstError.status === 401;
}
