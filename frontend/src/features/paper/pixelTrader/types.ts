export type PixelTraderMarketState = "open" | "closed" | "lunch_break";

export type PixelTraderAnimationState =
  | "idle"
  | "working"
  | "paused"
  | "closed"
  | "auto_trading"
  | "buy_anim"
  | "sell_anim";

export interface PixelTraderOrderAction {
  type: "buy" | "sell";
  symbol: string;
  timestamp: number;
}

export interface PixelTraderRecentTrade {
  type: "buy" | "sell";
  symbol: string;
  name: string;
  time: string;
}

export interface PixelTraderFrame {
  state: PixelTraderAnimationState;
  elapsedMs: number;
  stateElapsedMs: number;
  pulse: number;
  scanY: number;
  armSwing: number;
  thrust: number;
  flash: number;
  label?: string;
}

export interface PixelRect {
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  alpha?: number;
}
