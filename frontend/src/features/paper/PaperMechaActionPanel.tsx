import { useMemo } from "react";
import type { PaperAgentRun, PaperAutoTradingStatus, RiskEventItem } from "../../types";
import { usePaperUiStore, type PaperMechaUnitId } from "../../stores/paperUiStore";
import type { PixelTraderOrderAction } from "./pixelTrader/types";

interface PaperMechaActionPanelProps {
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  riskEvents: RiskEventItem[];
  paused: boolean;
  lastOrderAction: PixelTraderOrderAction | null;
}

const MECHA_UNITS: Record<PaperMechaUnitId, { name: string; desc: string }> = {
  purple: { name: "壹式·紫", desc: "流线高角装甲" },
  blue: { name: "零式·蓝白", desc: "多重透镜单目重铠" },
  red: { name: "贰式·赤", desc: "四复眼突击装甲" },
  black: { name: "陆式·黑", desc: "单角全息夜行战盾" },
  grey: { name: "拾参·灰", desc: "重叠复眼金纹机" },
};

export function PaperMechaActionPanel({
  autoTradingStatus,
  autoTradingRuns,
  riskEvents,
  paused,
  lastOrderAction,
}: PaperMechaActionPanelProps) {
  const state = resolveMechaHudState(autoTradingStatus, autoTradingRuns, riskEvents, paused, lastOrderAction);
  const activeUnitId = usePaperUiStore((store) => store.selectedMechaUnitId);
  const setActiveUnitId = usePaperUiStore((store) => store.setSelectedMechaUnitId);
  const activeUnit = MECHA_UNITS[activeUnitId];
  const animationKey = useMemo(() => `${state.key}-${activeUnitId}-${lastOrderAction?.timestamp ?? "static"}`, [activeUnitId, lastOrderAction?.timestamp, state.key]);

  return (
    <aside
      className={`paper-mecha-action-panel paper-mecha-action-panel--${state.key} paper-mecha-action-panel--unit-${activeUnitId}`}
      aria-label="模拟盘机甲交易舱"
    >
      <div className="paper-mecha-action-panel__chooser" aria-label="特设机型选择舱">
        {Object.entries(MECHA_UNITS).map(([unitId, unit]) => (
          <button
            key={unitId}
            type="button"
            className={`paper-mecha-action-panel__unit-option${unitId === activeUnitId ? " paper-mecha-action-panel__unit-option--active" : ""}`}
            onClick={() => setActiveUnitId(unitId as PaperMechaUnitId)}
            aria-pressed={unitId === activeUnitId}
            title={`${unit.name} - ${unit.desc}`}
          >
            <span className="paper-mecha-action-panel__unit-dot" />
            <span>{unit.name}</span>
          </button>
        ))}
      </div>
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
        <div key={animationKey} className={`paper-mecha-action-panel__avatar paper-mecha-action-panel__avatar--${state.key}`}>
          <MechaUnitSvg unitId={activeUnitId} />
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
          <strong>{activeUnit.name}</strong>
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

function MechaUnitSvg({ unitId }: { unitId: PaperMechaUnitId }) {
  if (unitId === "blue") return <BlueMechaSvg />;
  if (unitId === "red") return <RedMechaSvg />;
  if (unitId === "black") return <BlackMechaSvg />;
  if (unitId === "grey") return <GreyMechaSvg />;
  return <PurpleMechaSvg />;
}

function PurpleMechaSvg() {
  return (
    <svg viewBox="0 0 100 100" className="paper-mecha-action-panel__unit" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="paper-purple-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fdba74" />
          <stop offset="100%" stopColor="var(--u-purple-core)" />
        </radialGradient>
      </defs>
      <path d="M 15 50 L 5 45 L 8 20 L 22 25 Z" fill="var(--u-purple-primary)" stroke="#8b5cf6" strokeWidth="1.5" />
      <path d="M 85 50 L 95 45 L 92 20 L 78 25 Z" fill="var(--u-purple-primary)" stroke="#8b5cf6" strokeWidth="1.5" />
      <path d="M 12 25 L 20 28 L 18 12 Z" fill="var(--u-purple-accent)" />
      <path d="M 88 25 L 80 28 L 82 12 Z" fill="var(--u-purple-accent)" />
      <path d="M 35 60 L 50 72 L 65 60 L 60 95 L 40 95 Z" fill="var(--u-purple-base)" stroke="#312e81" strokeWidth="1" />
      <circle className="mecha-core animate-core" cx="50" cy="84" r="8" fill="url(#paper-purple-core-grad)" />
      <path d="M 35 55 L 50 25 L 65 55 L 50 68 Z" fill="var(--u-purple-primary)" stroke="#8b5cf6" strokeWidth="1.5" />
      <path d="M 47 28 L 50 3 L 53 28 L 50 25 Z" fill="var(--u-purple-accent)" />
      <path d="M 42 42 L 50 48 L 58 42 L 50 38 Z" fill="var(--u-purple-base)" stroke="var(--u-purple-accent)" strokeWidth="1" />
      <polygon className="animate-eye" points="40,38 48,39 46,43" fill="var(--u-purple-eye)" />
      <polygon className="animate-eye" points="60,38 52,39 54,43" fill="var(--u-purple-eye)" />
      <rect x="46" y="58" width="8" height="6" fill="var(--u-purple-accent)" rx="1" />
    </svg>
  );
}

function BlueMechaSvg() {
  return (
    <svg viewBox="0 0 100 100" className="paper-mecha-action-panel__unit" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="paper-blue-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ff8787" />
          <stop offset="100%" stopColor="var(--u-blue-core)" />
        </radialGradient>
      </defs>
      <path d="M 16 55 C 8 50, 10 25, 24 30 Z" fill="var(--u-blue-primary)" stroke="#3b82f6" strokeWidth="1.5" />
      <path d="M 84 55 C 92 50, 90 25, 76 30 Z" fill="var(--u-blue-primary)" stroke="#3b82f6" strokeWidth="1.5" />
      <circle cx="20" cy="36" r="3" fill="#ffffff" />
      <circle cx="80" cy="36" r="3" fill="#ffffff" />
      <path d="M 36 60 L 50 74 L 64 60 L 58 95 L 42 95 Z" fill="#475569" stroke="#cbd5e1" strokeWidth="1" />
      <circle className="mecha-core animate-core" cx="50" cy="85" r="7" fill="url(#paper-blue-core-grad)" />
      <path d="M 36 54 Q 50 18 64 54 Q 50 64 36 54 Z" fill="var(--u-blue-base)" stroke="#94a3b8" strokeWidth="1.5" />
      <path d="M 48 20 L 52 20 L 52 50 L 48 50 Z" fill="var(--u-blue-primary)" />
      <circle className="animate-eye" cx="50" cy="38" r="7" fill="var(--u-blue-eye)" />
      <circle cx="50" cy="38" r="2.5" fill="#ffffff" />
    </svg>
  );
}

function RedMechaSvg() {
  return (
    <svg viewBox="0 0 100 100" className="paper-mecha-action-panel__unit" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="paper-red-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#86efac" />
          <stop offset="100%" stopColor="var(--u-red-core)" />
        </radialGradient>
      </defs>
      <polygon points="12,50 4,40 10,18 24,24" fill="var(--u-red-primary)" stroke="#f43f5e" strokeWidth="1.5" />
      <polygon points="88,50 96,40 90,18 76,24" fill="var(--u-red-primary)" stroke="#f43f5e" strokeWidth="1.5" />
      <line x1="12" y1="28" x2="22" y2="30" stroke="var(--u-red-accent)" strokeWidth="2" />
      <line x1="88" y1="28" x2="78" y2="30" stroke="var(--u-red-accent)" strokeWidth="2" />
      <path d="M 35 60 L 50 72 L 65 60 L 59 95 L 41 95 Z" fill="var(--u-red-base)" stroke="#312e81" strokeWidth="1" />
      <circle className="mecha-core animate-core" cx="50" cy="82" r="7.5" fill="url(#paper-red-core-grad)" />
      <path d="M 34 52 L 50 24 L 66 52 L 50 66 Z" fill="var(--u-red-primary)" stroke="#f43f5e" strokeWidth="1.5" />
      <path d="M 38 28 L 26 12 L 40 22 Z" fill="var(--u-red-primary)" />
      <path d="M 62 28 L 74 12 L 60 22 Z" fill="var(--u-red-primary)" />
      <circle className="animate-eye" cx="44" cy="38" r="2.2" fill="var(--u-red-eye)" />
      <circle className="animate-eye" cx="56" cy="38" r="2.2" fill="var(--u-red-eye)" />
      <circle className="animate-eye" cx="42" cy="45" r="2.2" fill="var(--u-red-eye)" />
      <circle className="animate-eye" cx="58" cy="45" r="2.2" fill="var(--u-red-eye)" />
    </svg>
  );
}

function BlackMechaSvg() {
  return (
    <svg viewBox="0 0 100 100" className="paper-mecha-action-panel__unit" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="paper-black-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#a5f3fc" />
          <stop offset="100%" stopColor="var(--u-black-core)" />
        </radialGradient>
      </defs>
      <path d="M 15 48 L 2 30 L 10 22 L 24 28 Z" fill="var(--u-black-primary)" stroke="#475569" strokeWidth="1.5" />
      <path d="M 85 48 L 98 30 L 90 22 L 76 28 Z" fill="var(--u-black-primary)" stroke="#475569" strokeWidth="1.5" />
      <path d="M 35 60 L 50 72 L 65 60 L 58 95 L 42 95 Z" fill="var(--u-black-base)" stroke="#334155" strokeWidth="1" />
      <circle className="mecha-core animate-core" cx="50" cy="83" r="7" fill="url(#paper-black-core-grad)" />
      <path d="M 33 54 L 50 20 L 67 54 L 50 64 Z" fill="var(--u-black-primary)" stroke="#334155" strokeWidth="1.5" />
      <path d="M 49 18 L 51 6 L 53 18 Z" fill="var(--u-black-accent)" />
      <path className="animate-eye" d="M 38 40 Q 50 45 62 40 Q 50 48 38 40" fill="none" stroke="var(--u-black-eye)" strokeWidth="2.5" />
    </svg>
  );
}

function GreyMechaSvg() {
  return (
    <svg viewBox="0 0 100 100" className="paper-mecha-action-panel__unit" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="paper-grey-core-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="100%" stopColor="var(--u-grey-core)" />
        </radialGradient>
      </defs>
      <path d="M 16 52 L 6 42 L 8 18 L 22 24 Z" fill="var(--u-grey-primary)" stroke="#94a3b8" strokeWidth="1" />
      <path d="M 12 40 L 4 32 L 6 12 L 18 18 Z" fill="#475569" stroke="#cbd5e1" strokeWidth="0.8" />
      <path d="M 84 52 L 94 42 L 92 18 L 78 24 Z" fill="var(--u-grey-primary)" stroke="#94a3b8" strokeWidth="1" />
      <path d="M 88 40 L 96 32 L 94 12 L 82 18 Z" fill="#475569" stroke="#cbd5e1" strokeWidth="0.8" />
      <path d="M 36 58 L 50 72 L 64 58 L 58 95 L 42 95 Z" fill="#475569" stroke="#cbd5e1" strokeWidth="1" />
      <circle className="mecha-core animate-core" cx="50" cy="81" r="8" fill="url(#paper-grey-core-grad)" />
      <path d="M 33 54 L 50 24 L 67 54 L 50 66 Z" fill="var(--u-grey-primary)" stroke="#cbd5e1" strokeWidth="1.5" />
      <path d="M 44 26 L 50 4 L 56 26 Z" fill="var(--u-grey-accent)" />
      <circle className="animate-eye" cx="42" cy="38" r="2" fill="var(--u-grey-eye)" />
      <circle className="animate-eye" cx="58" cy="38" r="2" fill="var(--u-grey-eye)" />
      <circle className="animate-eye" cx="46" cy="45" r="1.8" fill="var(--u-grey-eye)" />
      <circle className="animate-eye" cx="54" cy="45" r="1.8" fill="var(--u-grey-eye)" />
      <path d="M 40 50 L 50 56 L 60 50" fill="none" stroke="var(--u-grey-accent)" strokeWidth="1.2" />
    </svg>
  );
}
