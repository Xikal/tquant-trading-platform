import { useCallback, useEffect, useMemo, useRef, type ReactNode } from "react";
import type { PaperAgentRun, PaperAutoTradingStatus, RiskEventItem } from "../../types";
import { usePaperUiStore, type PaperMechaEffectState, type PaperMechaUnitId, type PaperMechaVisualState } from "../../stores/paperUiStore";
import type { PixelTraderOrderAction } from "./pixelTrader/types";
import { MECHA_UNITS, PaperMechaAvatar } from "./PaperMechaAvatar";
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

const MECHA_EFFECT_DURATION_MS = 2600;
const EFFECT_BASE_STATES = new Set<PaperMechaVisualState>(["auto", "risk", "loss"]);

export function PaperMechaActionPanel({
  autoTradingStatus,
  autoTradingRuns,
  riskEvents,
  paused,
  lastOrderAction,
  monitor,
}: PaperMechaActionPanelProps) {
  const baseState = resolveMechaHudState(autoTradingStatus, autoTradingRuns, riskEvents, paused);
  const activeEffect = usePaperUiStore((store) => store.activeMechaEffect);
  useTriggeredMechaEffect(baseState, lastOrderAction);
  const state = activeEffect ?? baseState;
  const effectsActive = Boolean(activeEffect);
  const activeUnitId = usePaperUiStore((store) => store.selectedMechaUnitId);
  const setActiveUnitId = usePaperUiStore((store) => store.setSelectedMechaUnitId);
  const activeUnit = MECHA_UNITS[activeUnitId] ?? MECHA_UNITS.purple;
  const animationKey = useMemo(
    () => `${state.key}-${activeUnitId}-${activeEffect?.token ?? "static"}`,
    [activeEffect?.token, activeUnitId, state.key],
  );

  return (
    <aside
      className={[
        "paper-mecha-action-panel",
        `paper-mecha-action-panel--${state.key}`,
        `paper-mecha-action-panel--unit-${activeUnitId}`,
        effectsActive ? "paper-mecha-action-panel--effects-active" : "",
      ].filter(Boolean).join(" ")}
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
        {effectsActive ? <PaperMechaParticles key={activeEffect?.token} state={state.key} /> : null}
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
): MechaHudState {
  const hasOpenRisk = riskEvents.some((item) => item.status !== "resolved") || Boolean(autoTradingStatus?.circuit_open);
  if (hasOpenRisk) return { key: "risk", label: "RISK", syncRate: "15.6%", caption: "CRITICAL RISK" };
  if (paused) return { key: "paused", label: "PAUSED", syncRate: "0.0%", caption: "ORDER HOLD" };
  if (autoTradingRuns.some((item) => item.status === "failed")) return { key: "loss", label: "LOSS", syncRate: "31.2%", caption: "DAMAGE CHECK" };
  if (autoTradingStatus?.running || autoTradingStatus?.engine_running) return { key: "auto", label: "AUTO", syncRate: "89.4%", caption: "MAGI LOOP" };
  if (autoTradingStatus?.trading_time === false) return { key: "closed", label: "IDLE", syncRate: "52.0%", caption: "MARKET CLOSED" };
  return { key: "idle", label: "IDLE", syncRate: "84.2%", caption: "PILOT ACTIVE" };
}

function useTriggeredMechaEffect(
  baseState: MechaHudState,
  lastOrderAction: PixelTraderOrderAction | null,
): void {
  const setActiveMechaEffect = usePaperUiStore((store) => store.setActiveMechaEffect);
  const effectTimerRef = useRef<number | null>(null);
  const seenOrderTimestampRef = useRef<number | null>(null);
  const orderFeedInitializedRef = useRef(false);
  const previousBaseKeyRef = useRef<PaperMechaVisualState | null>(null);

  const triggerEffect = useCallback((next: PaperMechaEffectState) => {
    if (effectTimerRef.current != null) {
      window.clearTimeout(effectTimerRef.current);
    }
    setActiveMechaEffect(next);
    effectTimerRef.current = window.setTimeout(() => {
      const current = usePaperUiStore.getState().activeMechaEffect;
      if (current?.token === next.token) {
        setActiveMechaEffect(null);
      }
      effectTimerRef.current = null;
    }, MECHA_EFFECT_DURATION_MS);
  }, [setActiveMechaEffect]);

  useEffect(() => {
    return () => {
      if (effectTimerRef.current != null) {
        window.clearTimeout(effectTimerRef.current);
      }
      setActiveMechaEffect(null);
    };
  }, [setActiveMechaEffect]);

  useEffect(() => {
    if (!lastOrderAction || !Number.isFinite(lastOrderAction.timestamp)) {
      orderFeedInitializedRef.current = true;
      return;
    }

    const feedInitialized = orderFeedInitializedRef.current;
    const previousTimestamp = seenOrderTimestampRef.current;
    seenOrderTimestampRef.current = lastOrderAction.timestamp;
    orderFeedInitializedRef.current = true;
    if (!feedInitialized || previousTimestamp === lastOrderAction.timestamp) return;

    triggerEffect({
      key: lastOrderAction.type === "sell" ? "sell" : "buy",
      label: lastOrderAction.type === "sell" ? "SELL" : "BUY",
      syncRate: lastOrderAction.type === "sell" ? "88.0%" : "93.5%",
      caption: lastOrderAction.symbol,
      token: `${lastOrderAction.type}-${lastOrderAction.timestamp}`,
    });
  }, [lastOrderAction, triggerEffect]);

  useEffect(() => {
    const previousBaseKey = previousBaseKeyRef.current;
    previousBaseKeyRef.current = baseState.key;
    if (previousBaseKey == null || previousBaseKey === baseState.key) return;
    if (!EFFECT_BASE_STATES.has(baseState.key)) return;

    triggerEffect({
      ...baseState,
      token: `${baseState.key}-${Date.now()}`,
    });
  }, [baseState.caption, baseState.key, baseState.label, baseState.syncRate, triggerEffect]);

  return undefined;
}
