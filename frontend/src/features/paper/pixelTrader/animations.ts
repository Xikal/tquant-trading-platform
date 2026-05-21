import type {
  PixelTraderAnimationState,
  PixelTraderFrame,
  PixelTraderMarketState,
  PixelTraderOrderAction,
} from "./types";

const ACTION_DURATION_MS = 1500;

export interface PixelTraderAnimationInput {
  marketState: PixelTraderMarketState;
  paused: boolean;
  autoTradingRunning: boolean;
  lastOrderAction: PixelTraderOrderAction | null;
  consumedActionTimestamp: number;
  currentState: PixelTraderAnimationState;
  stateStartedAt: number;
  now: number;
}

export interface PixelTraderAnimationResult {
  state: PixelTraderAnimationState;
  stateStartedAt: number;
  consumedActionTimestamp: number;
  frame: PixelTraderFrame;
  triggerParticles?: PixelTraderOrderAction;
}

export function resolvePixelTraderFrame(input: PixelTraderAnimationInput): PixelTraderAnimationResult {
  const action = nextAction(input.lastOrderAction, input.consumedActionTimestamp);
  if (action) {
    const state = action.type === "buy" ? "buy_anim" : "sell_anim";
    return buildResult(input, state, input.now, action.timestamp, action);
  }

  if (isActionState(input.currentState)) {
    const runningFor = input.now - input.stateStartedAt;
    if (runningFor < ACTION_DURATION_MS) {
      return buildResult(input, input.currentState, input.stateStartedAt, input.consumedActionTimestamp);
    }
  }

  const baseState = resolveBaseState(input);
  const nextStartedAt = input.currentState === baseState && !isActionState(input.currentState)
    ? input.stateStartedAt
    : input.now;
  return buildResult(input, baseState, nextStartedAt, input.consumedActionTimestamp);
}

function nextAction(action: PixelTraderOrderAction | null, consumedTimestamp: number): PixelTraderOrderAction | null {
  if (!action || action.timestamp <= consumedTimestamp) return null;
  return action;
}

function resolveBaseState(input: PixelTraderAnimationInput): PixelTraderAnimationState {
  if (input.paused) return "paused";
  if (input.autoTradingRunning) return "auto_trading";
  if (input.marketState === "closed") return "closed";
  if (input.marketState === "open") return "working";
  return "idle";
}

function isActionState(state: PixelTraderAnimationState): boolean {
  return state === "buy_anim" || state === "sell_anim";
}

function buildResult(
  input: PixelTraderAnimationInput,
  state: PixelTraderAnimationState,
  stateStartedAt: number,
  consumedActionTimestamp: number,
  triggerParticles?: PixelTraderOrderAction,
): PixelTraderAnimationResult {
  const stateElapsedMs = input.now - stateStartedAt;
  return {
    state,
    stateStartedAt,
    consumedActionTimestamp,
    triggerParticles,
    frame: buildFrame(state, input.now, stateElapsedMs, input.lastOrderAction?.symbol),
  };
}

function buildFrame(
  state: PixelTraderAnimationState,
  now: number,
  stateElapsedMs: number,
  symbol?: string,
): PixelTraderFrame {
  const seconds = now / 1000;
  const fast = state === "auto_trading" || state === "buy_anim";
  const pulseSpeed = fast ? 10 : state === "working" ? 4 : 2.2;
  const pulse = (Math.sin(seconds * pulseSpeed) + 1) / 2;
  const actionProgress = Math.min(1, stateElapsedMs / ACTION_DURATION_MS);
  return {
    state,
    elapsedMs: now,
    stateElapsedMs,
    pulse,
    scanY: fast ? (seconds * 34) % 24 : (seconds * 12) % 24,
    armSwing: resolveArmSwing(state, seconds, actionProgress),
    thrust: resolveThrust(state, pulse, actionProgress),
    flash: isActionState(state) ? Math.max(0, 1 - actionProgress) : state === "auto_trading" ? pulse * 0.45 : 0,
    label: isActionState(state) && symbol ? `${state === "buy_anim" ? "BUY" : "SELL"} ${symbol}` : undefined,
  };
}

function resolveArmSwing(state: PixelTraderAnimationState, seconds: number, actionProgress: number): number {
  if (state === "buy_anim") return -16 + Math.sin(actionProgress * Math.PI) * 28;
  if (state === "sell_anim") return 12 + Math.sin(actionProgress * Math.PI) * 16;
  if (state === "working") return Math.sin(seconds * 8) * 8;
  if (state === "auto_trading") return Math.sin(seconds * 18) * 14;
  if (state === "closed") return -10;
  return Math.sin(seconds * 2) * 2;
}

function resolveThrust(state: PixelTraderAnimationState, pulse: number, actionProgress: number): number {
  if (state === "buy_anim") return Math.sin(actionProgress * Math.PI) * 1;
  if (state === "auto_trading") return 0.45 + pulse * 0.55;
  if (state === "working") return pulse * 0.22;
  return 0;
}
