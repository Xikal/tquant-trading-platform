import { API_BASE, request } from "../../api/base";
import type {
  BacktestParamGrid,
  BacktestStatus,
} from "../../api/backtests";
import type { BacktestFormState } from "./BacktestDashboard";
import type { OptimizationFormState, ValidationFormState } from "./BacktestResearchPanel";

interface StrategyStreamTokenResponse {
  stream_token: string;
  expires_in: number;
}

interface StrategyProgressMessage {
  type: "progress" | "error" | "ping";
  task_id?: number;
  status?: BacktestStatus;
  progress_pct?: number;
  message?: string;
  completed?: boolean;
}

export type ProgressTask = {
  id: number;
  status: BacktestStatus;
  progress?: number | null;
  progress_pct?: number | null;
  error_message?: string | null;
};

export const initialBacktestForm: BacktestFormState = {
  name: "低吸策略组合回测",
  start_date: "2025-01-02",
  end_date: "2026-04-30",
  initial_capital: "500000",
  strategies: ["first_board", "volume_shrink"],
  execution_model: "conservative_slippage",
  resource_tier: "full",
  max_position_pct: "30",
  max_positions: "8",
  max_daily_loss_pct: "5",
  max_single_order_pct: "30",
  min_cash_reserve: "5000",
  benchmark: "000300",
};

export const initialOptimizationForm: OptimizationFormState = {
  name: "first_board 参数优化",
  strategy: "first_board",
  train_start: "2024-01-02",
  train_end: "2025-12-31",
  test_start: "2026-01-02",
  test_end: "2026-04-30",
  initial_capital: "500000",
  execution_model: "conservative_slippage",
  optimization_target: "sharpe",
  min_score: "70,75,80,85,90",
  max_position_pct: "0.2,0.3",
  max_holding_days: "3,5,7,10",
  stop_loss_pct: "-0.03,-0.05,-0.07",
  take_profit_pct: "0.08,0.12",
};

export const initialValidationForm: ValidationFormState = {
  name: "first_board Walk-Forward 验证",
  strategy: "first_board",
  start_date: "2024-01-02",
  end_date: "2026-04-30",
  window_count: "4",
  train_ratio: "0.75",
  initial_capital: "500000",
  execution_model: "conservative_slippage",
  optimization_target: "sharpe",
  auto_promote_state_params: false,
};

export function validateOptimizationForm(form: OptimizationFormState) {
  if (!form.name.trim()) {
    throw new Error("请填写优化任务名称");
  }
  if (!form.strategy) {
    throw new Error("请选择优化策略");
  }
  if (!form.train_start || !form.train_end || !form.test_start || !form.test_end) {
    throw new Error("请填写训练/验证日期范围");
  }
  if (form.train_start > form.train_end || form.test_start > form.test_end) {
    throw new Error("日期范围不合法");
  }
  if (!Object.keys(buildParamGrid(form)).length) {
    throw new Error("至少填写一个参数网格");
  }
  parsePositiveNumber(form.initial_capital, "初始资金");
}

export function validateValidationForm(form: ValidationFormState) {
  if (!form.name.trim()) {
    throw new Error("请填写验证任务名称");
  }
  if (!form.strategy) {
    throw new Error("请选择验证策略");
  }
  if (!form.start_date || !form.end_date) {
    throw new Error("请填写验证日期范围");
  }
  if (form.start_date > form.end_date) {
    throw new Error("开始日期不能晚于结束日期");
  }
  parsePositiveNumber(form.window_count, "窗口数");
  parsePositiveNumber(form.train_ratio, "训练比例");
  parsePositiveNumber(form.initial_capital, "初始资金");
}

export function buildParamGrid(form: OptimizationFormState): BacktestParamGrid {
  const entries: Array<[keyof OptimizationFormState, string]> = [
    ["min_score", "min_score"],
    ["max_position_pct", "max_position_pct"],
    ["max_holding_days", "max_holding_days"],
    ["stop_loss_pct", "stop_loss_pct"],
    ["take_profit_pct", "take_profit_pct"],
  ];
  return entries.reduce<BacktestParamGrid>((grid, [field, paramName]) => {
    const values = parseParamList(form[field]);
    if (values.length) {
      grid[paramName] = values;
    }
    return grid;
  }, {});
}

export function parseRunIds(value: string): number[] {
  const runIds = value
    .split(/[,\s]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
  if (!runIds.length) {
    throw new Error("请至少输入一个有效 run id");
  }
  return [...new Set(runIds)];
}

export function validateForm(form: BacktestFormState) {
  if (!form.name.trim()) {
    throw new Error("请填写回测任务名称");
  }
  if (!form.start_date || !form.end_date) {
    throw new Error("请选择回测日期范围");
  }
  if (form.start_date > form.end_date) {
    throw new Error("开始日期不能晚于结束日期");
  }
  if (!form.strategies.length) {
    throw new Error("至少选择一个策略");
  }
  parsePositiveNumber(form.initial_capital, "初始资金");
  parsePositiveNumber(form.max_positions, "最大持仓数");
}

export function parsePositiveNumber(value: string, label = "数值"): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${label}必须大于 0`);
  }
  return parsed;
}

export function parseNullableNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return parsePositiveNumber(trimmed);
}

export function parsePercent(value: string): number {
  return parsePositiveNumber(value, "百分比") / 100;
}

export function parseNullablePercent(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return parsePercent(trimmed);
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "请求失败";
}

export function isActiveStatus(status: BacktestStatus): boolean {
  return status === "pending" || status === "queued" || status === "running";
}

export function compactProgressPatch<T extends ProgressTask>(item: T, patch: Partial<ProgressTask>): T {
  return {
    ...item,
    ...(patch.status ? { status: patch.status } : {}),
    ...(typeof patch.progress === "number" ? { progress: patch.progress } : {}),
    ...(typeof patch.progress_pct === "number" ? { progress_pct: patch.progress_pct } : {}),
    ...(patch.error_message ? { error_message: patch.error_message } : {}),
  };
}

export function startStrategyProgressStream({
  taskType,
  taskId,
  currentStatus,
  onPatch,
  onComplete,
  onFallback,
  onError,
}: {
  taskType: "backtest" | "optimize" | "validate";
  taskId: number;
  currentStatus: BacktestStatus;
  onPatch: (patch: Partial<ProgressTask>) => void;
  onComplete: () => void;
  onFallback: () => void;
  onError: (message: string) => void;
}): () => void {
  let closed = false;
  let socket: WebSocket | null = null;
  let fallbackTimer: number | undefined;
  let reconnectTimer: number | undefined;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;

  const startFallback = () => {
    if (fallbackTimer || closed) return;
    fallbackTimer = window.setInterval(onFallback, 3000);
  };

  const closeSocket = () => {
    const currentSocket = socket;
    socket = null;
    if (currentSocket && currentSocket.readyState !== WebSocket.CLOSED) {
      currentSocket.close();
    }
  };

  const scheduleReconnect = () => {
    if (closed || fallbackTimer || reconnectTimer) return;
    if (reconnectAttempts >= maxReconnectAttempts) {
      startFallback();
      return;
    }
    reconnectAttempts += 1;
    const delayMs = Math.min(1000 * 2 ** (reconnectAttempts - 1), 16000);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = undefined;
      connect();
    }, delayMs);
    closeSocket();
  };

  const connect = () => {
    request<StrategyStreamTokenResponse>("/strategy/stream-token", { method: "POST" })
      .then((payload) => {
        if (closed || !payload.stream_token) return;
        socket = new WebSocket(strategyProgressUrl(taskType, taskId, payload.stream_token));
        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as StrategyProgressMessage;
            if (message.task_id !== taskId) return;
            if (message.type === "ping") return;
            reconnectAttempts = 0;
            if (message.type === "error") {
              onError(message.message || "策略任务进度连接异常，已切换轮询。");
              startFallback();
              return;
            }
            const patch: Partial<ProgressTask> = {
              status: message.status ?? currentStatus,
              progress: message.progress_pct,
              progress_pct: message.progress_pct,
            };
            onPatch(patch);
            if (message.completed) onComplete();
          } catch {
            scheduleReconnect();
          }
        };
        socket.onerror = scheduleReconnect;
        socket.onclose = (event) => {
          if (!closed && event.code !== 1000) {
            scheduleReconnect();
          }
        };
      })
      .catch(scheduleReconnect);
  };

  connect();

  return () => {
    closed = true;
    if (fallbackTimer) window.clearInterval(fallbackTimer);
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    closeSocket();
  };
}

function parseParamList(value: string): Array<number | string> {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const parsed = Number(item);
      return Number.isFinite(parsed) ? parsed : item;
    });
}

function strategyProgressUrl(taskType: string, taskId: number, streamToken: string): string {
  const apiBase = API_BASE === "__NATIVE_API_BASE_REQUIRED__" ? "/api" : API_BASE;
  const base = apiBase.startsWith("http")
    ? apiBase.replace(/\/api\/?$/, "").replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
  const params = new URLSearchParams({
    stream_token: streamToken,
    interval_seconds: "3",
  });
  return `${base}/ws/strategy/${encodeURIComponent(taskType)}/${encodeURIComponent(String(taskId))}?${params.toString()}`;
}
