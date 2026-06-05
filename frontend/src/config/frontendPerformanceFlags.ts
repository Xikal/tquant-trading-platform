export type FrontendPerformanceFlagKey =
  | "frontend_worker_compute_enabled"
  | "frontend_realtime_signals_island_enabled"
  | "frontend_canvas_chart_island_enabled"
  | "frontend_wasm_compute_enabled"
  | "frontend_solid_island_enabled";

const DEFAULT_FLAGS: Record<FrontendPerformanceFlagKey, boolean> = {
  frontend_worker_compute_enabled: true,
  frontend_realtime_signals_island_enabled: true,
  frontend_canvas_chart_island_enabled: true,
  frontend_wasm_compute_enabled: false,
  frontend_solid_island_enabled: false,
};

const ENV_KEYS: Record<FrontendPerformanceFlagKey, string> = {
  frontend_worker_compute_enabled: "VITE_FRONTEND_WORKER_COMPUTE_ENABLED",
  frontend_realtime_signals_island_enabled: "VITE_FRONTEND_REALTIME_SIGNALS_ISLAND_ENABLED",
  frontend_canvas_chart_island_enabled: "VITE_FRONTEND_CANVAS_CHART_ISLAND_ENABLED",
  frontend_wasm_compute_enabled: "VITE_FRONTEND_WASM_COMPUTE_ENABLED",
  frontend_solid_island_enabled: "VITE_FRONTEND_SOLID_ISLAND_ENABLED",
};

export function frontendPerformanceFlagEnabled(
  key: FrontendPerformanceFlagKey,
  overrides?: Partial<Record<FrontendPerformanceFlagKey, boolean>>,
): boolean {
  if (overrides && key in overrides) {
    return Boolean(overrides[key]);
  }
  const envValue = import.meta.env[ENV_KEYS[key] as keyof ImportMetaEnv];
  if (envValue === undefined || envValue === "") {
    return DEFAULT_FLAGS[key];
  }
  return String(envValue).toLowerCase() !== "false";
}

export function frontendPerformanceFlagDefaults(): Record<FrontendPerformanceFlagKey, boolean> {
  return { ...DEFAULT_FLAGS };
}
