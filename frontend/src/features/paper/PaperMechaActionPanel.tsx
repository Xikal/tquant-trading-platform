import { useMemo, type ReactNode } from "react";
import type { PaperAgentRun, PaperAutoTradingStatus, RiskEventItem } from "../../types";
import { usePaperUiStore, type PaperMechaUnitId } from "../../stores/paperUiStore";
import type { PixelTraderOrderAction } from "./pixelTrader/types";
import { MECHA_UNITS, PaperMechaAvatar, type PaperMechaVisualState } from "./PaperMechaAvatar";
import { PaperMechaParticles } from "./PaperMechaParticles";

interface PaperMechaActionPanelProps {
  autoTradingStatus: PaperAutoTradingStatus | null;
  autoTradingRuns: PaperAgentRun[];
  riskEvents: RiskEventItem[];
  paused: boolean;
  lastOrderAction: PixelTraderOrderAction | null;
  monitor?: ReactNode;
}

interface MechaHudState {
  key: PaperMechaVisualState;
  label: string;
  syncRate: string;
  caption: string;
}

export function PaperMechaActionPanel({
  autoTradingStatus,
  autoTradingRuns,
  riskEvents,
  paused,
  lastOrderAction,
  monitor,
}: PaperMechaActionPanelProps) {
  const state = resolveMechaHudState(autoTradingStatus, autoTradingRuns, riskEvents, paused, lastOrderAction);
  const activeUnitId = usePaperUiStore((store) => store.selectedMechaUnitId);
  const setActiveUnitId = usePaperUiStore((store) => store.setSelectedMechaUnitId);
  const activeUnit = MECHA_UNITS[activeUnitId] ?? MECHA_UNITS.purple;
  const animationKey = useMemo(
    () => `${state.key}-${activeUnitId}-${lastOrderAction?.timestamp ?? "static"}`,
    [activeUnitId, lastOrderAction?.timestamp, state.key],
  );

  return (
    <aside
      className={`paper-mecha-action-panel paper-mecha-action-panel--${state.key} paper-mecha-action-panel--unit-${activeUnitId}`}
      aria-label="模拟盘机甲交易舱"
    >
      <div className="paper-mecha-action-panel__chooser" aria-label="特设机型选择舱">
        {Object.entries(MECHA_UNITS).map(([unitId, unit]) => {
          const typedUnitId = unitId as PaperMechaUnitId;
          const active = typedUnitId === activeUnitId;
          return (
            <button
              key={unitId}
              type="button"
              className={`paper-mecha-action-panel__unit-option${active ? " paper-mecha-action-panel__unit-option--active" : ""}`}
              onClick={() => setActiveUnitId(typedUnitId)}
              aria-pressed={active}
              title={`${unit.name} - ${unit.desc}`}
            >
              <span className="paper-mecha-action-panel__unit-thumb" aria-hidden="true">
                <PaperMechaAvatar unitId={typedUnitId} state={state.key} mini />
              </span>
              <span>{unit.name}</span>
            </button>
          );
        })}
      </div>
      <div className="paper-mecha-action-panel__stage">
        <PaperMechaParticles state={state.key} />
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
          <span>S2 ENGINE: ACTIVE</span>
          <span>SYNC_RATIO_STATUS</span>
        </div>
        <div key={animationKey} className={`paper-mecha-action-panel__avatar paper-mecha-action-panel__avatar--${state.key}`}>
          <PaperMechaAvatar unitId={activeUnitId} state={state.key} />
          <div className="state-sell-overlay" aria-hidden="true" />
          <div className="state-loss-overlay" aria-hidden="true" />
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
      {monitor ? <div className="paper-mecha-action-panel__monitor">{monitor}</div> : null}
    </aside>
  );
}

function resolveMechaHudState(
  autoTradingStatus: PaperAutoTradingStatus | null,
  autoTradingRuns: PaperAgentRun[],
  riskEvents: RiskEventItem[],
  paused: boolean,
  lastOrderAction: PixelTraderOrderAction | null,
): MechaHudState {
  const hasOpenRisk = riskEvents.some((item) => item.status !== "resolved") || Boolean(autoTradingStatus?.circuit_open);
  if (hasOpenRisk) return { key: "risk", label: "RISK", syncRate: "15.6%", caption: "CRITICAL RISK" };
  if (paused) return { key: "paused", label: "PAUSED", syncRate: "0.0%", caption: "ORDER HOLD" };
  if (lastOrderAction?.type === "buy") return { key: "buy", label: "BUY", syncRate: "93.5%", caption: lastOrderAction.symbol };
  if (lastOrderAction?.type === "sell") return { key: "sell", label: "SELL", syncRate: "88.0%", caption: lastOrderAction.symbol };
  if (autoTradingRuns.some((item) => item.status === "failed")) return { key: "loss", label: "LOSS", syncRate: "31.2%", caption: "DAMAGE CHECK" };
  if (autoTradingStatus?.running || autoTradingStatus?.engine_running) return { key: "auto", label: "AUTO", syncRate: "89.4%", caption: "MAGI LOOP" };
  if (autoTradingStatus?.trading_time === false) return { key: "closed", label: "IDLE", syncRate: "52.0%", caption: "MARKET CLOSED" };
  return { key: "idle", label: "IDLE", syncRate: "84.2%", caption: "PILOT ACTIVE" };
}
