import type { PaperAgentRun, PaperAutoTradingStatus, RiskEventItem } from "../../types";
import type { PixelTraderOrderAction } from "./pixelTrader/types";

interface PaperMechaActionPanelProps {
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  riskEvents: RiskEventItem[];
  paused: boolean;
  lastOrderAction: PixelTraderOrderAction | null;
}

export function PaperMechaActionPanel({
  autoTradingStatus,
  autoTradingRuns,
  riskEvents,
  paused,
  lastOrderAction,
}: PaperMechaActionPanelProps) {
  const state = resolveMechaHudState(autoTradingStatus, autoTradingRuns, riskEvents, paused, lastOrderAction);

  return (
    <aside
      className={`paper-mecha-action-panel paper-mecha-action-panel--${state.key}`}
      aria-label="模拟盘机甲交易舱"
    >
      <div className="paper-mecha-action-panel__stage">
        <div className="paper-mecha-action-panel__glow" aria-hidden="true" />
        <div className="paper-mecha-action-panel__at-field" aria-hidden="true">
          <svg viewBox="0 0 100 100" focusable="false">
            <polygon points="50,3 93,28 93,78 50,103 7,78 7,28" />
            <polygon points="50,10 87,31 87,71 50,92 13,71 13,31" />
            <polygon points="50,18 80,35 80,67 50,84 20,67 20,35" />
          </svg>
        </div>
        <svg
          className="paper-mecha-action-panel__ring paper-mecha-action-panel__ring--slow"
          viewBox="0 0 200 200"
          aria-hidden="true"
          focusable="false"
        >
          <circle cx="100" cy="100" r="92" />
          <circle cx="100" cy="100" r="88" />
        </svg>
        <svg
          className="paper-mecha-action-panel__ring paper-mecha-action-panel__ring--reverse"
          viewBox="0 0 200 200"
          aria-hidden="true"
          focusable="false"
        >
          <circle cx="100" cy="100" r="84" />
          <path d="M 100,6 A 94,94 0 0,1 194,100" />
        </svg>
        <div className="paper-mecha-action-panel__readout" aria-hidden="true">
          <span>SYS_ON: 2.5</span>
          <span>CONN_OK</span>
        </div>
        <div className="paper-mecha-action-panel__avatar">
          <PurpleMechaSvg />
          <div className="state-sell-overlay" aria-hidden="true" />
        </div>
        <div className="paper-mecha-action-panel__sync">
          <strong>SYNC: {state.syncRate}</strong>
          <span>{state.caption}</span>
        </div>
      </div>
      <div className="paper-mecha-action-panel__status">
        <div>
          <span>当前代号: </span>
          <strong>壹式·紫</strong>
        </div>
        <div>
          <span>实时状态: </span>
          <strong>{state.label}</strong>
        </div>
      </div>
    </aside>
  );
}

function resolveMechaHudState(
  autoTradingStatus: PaperAutoTradingStatus | null,
  autoTradingRuns: PaperAgentRun[],
  riskEvents: RiskEventItem[],
  paused: boolean,
  lastOrderAction: PixelTraderOrderAction | null,
) {
  const hasOpenRisk = riskEvents.some((item) => item.status !== "resolved") || Boolean(autoTradingStatus?.circuit_open);
  if (hasOpenRisk) return { key: "risk", label: "RISK", syncRate: "24.3%", caption: "RISK LOCKED" };
  if (paused) return { key: "paused", label: "PAUSED", syncRate: "0.0%", caption: "ORDER HOLD" };
  if (lastOrderAction?.type === "buy") return { key: "buy", label: "BUY", syncRate: "94.8%", caption: lastOrderAction.symbol };
  if (lastOrderAction?.type === "sell") return { key: "sell", label: "SELL", syncRate: "88.2%", caption: lastOrderAction.symbol };
  if (autoTradingRuns.some((item) => item.status === "failed")) return { key: "loss", label: "LOSS", syncRate: "62.4%", caption: "DAMAGE CHECK" };
  if (autoTradingStatus?.running || autoTradingStatus?.engine_running) return { key: "auto", label: "AUTO", syncRate: "89.5%", caption: "AUTO LOOP" };
  if (autoTradingStatus?.trading_time === false) return { key: "closed", label: "IDLE", syncRate: "52.0%", caption: "MARKET CLOSED" };
  return { key: "idle", label: "IDLE", syncRate: "84.2%", caption: "PILOT ACTIVE" };
}

function PurpleMechaSvg() {
  return (
    <svg
      viewBox="0 0 100 100"
      className="paper-mecha-action-panel__unit"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <radialGradient id="paper-purple-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgb(253 186 116)" />
          <stop offset="100%" stopColor="var(--u-purple-core)" />
        </radialGradient>
      </defs>
      <path d="M 15 50 L 5 45 L 8 20 L 22 25 Z" fill="var(--u-purple-primary)" stroke="rgb(139 92 246)" strokeWidth="1.5" />
      <path d="M 85 50 L 95 45 L 92 20 L 78 25 Z" fill="var(--u-purple-primary)" stroke="rgb(139 92 246)" strokeWidth="1.5" />
      <path d="M 12 25 L 20 28 L 18 12 Z" fill="var(--u-purple-accent)" />
      <path d="M 88 25 L 80 28 L 82 12 Z" fill="var(--u-purple-accent)" />
      <path d="M 35 60 L 50 72 L 65 60 L 60 95 L 40 95 Z" fill="var(--u-purple-base)" stroke="rgb(49 46 129)" strokeWidth="1" />
      <circle className="mecha-core animate-core" cx="50" cy="84" r="8" fill="url(#paper-purple-core-grad)" />
      <path d="M 35 55 L 50 25 L 65 55 L 50 68 Z" fill="var(--u-purple-primary)" stroke="rgb(139 92 246)" strokeWidth="1.5" />
      <path d="M 47 28 L 50 3 L 53 28 L 50 25 Z" fill="var(--u-purple-accent)" />
      <path d="M 42 42 L 50 48 L 58 42 L 50 38 Z" fill="var(--u-purple-base)" stroke="var(--u-purple-accent)" strokeWidth="1" />
      <polygon className="animate-eye" points="40,38 48,39 46,43" fill="var(--u-purple-eye)" />
      <polygon className="animate-eye" points="60,38 52,39 54,43" fill="var(--u-purple-eye)" />
      <rect x="46" y="58" width="8" height="6" fill="var(--u-purple-accent)" rx="1" />
    </svg>
  );
}
