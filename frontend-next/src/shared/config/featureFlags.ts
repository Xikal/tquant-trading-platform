export const FRONTEND_NEXT_FLAGS = {
  workerCompute: "frontend_worker_compute_enabled",
  realtimeSignals: "frontend_realtime_signals_island_enabled",
  canvasCharts: "frontend_canvas_chart_island_enabled",
  wasmCompute: "frontend_wasm_compute_enabled",
  solidFrontend: "frontend_solid_island_enabled",
} as const;

export const featureFlagDefaults = {
  [FRONTEND_NEXT_FLAGS.workerCompute]: true,
  [FRONTEND_NEXT_FLAGS.realtimeSignals]: true,
  [FRONTEND_NEXT_FLAGS.canvasCharts]: true,
  [FRONTEND_NEXT_FLAGS.wasmCompute]: false,
  [FRONTEND_NEXT_FLAGS.solidFrontend]: false,
} as const;
