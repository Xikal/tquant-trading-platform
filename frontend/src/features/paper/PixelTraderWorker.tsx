import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "antd";
import {
  resolvePixelTraderFrame,
} from "./pixelTrader/animations";
import { drawMechaScene } from "./pixelTrader/character";
import {
  createActionParticles,
  drawParticles,
  updateParticles,
  type MechaParticle,
} from "./pixelTrader/particles";
import type {
  PixelTraderAnimationState,
  PixelTraderMarketState,
  PixelTraderOrderAction,
  PixelTraderRecentTrade,
} from "./pixelTrader/types";
import "./PixelTraderWorker.css";

interface PixelTraderWorkerProps {
  marketState: PixelTraderMarketState;
  paused: boolean;
  autoTradingRunning: boolean;
  lastOrderAction: PixelTraderOrderAction | null;
  loading: boolean;
  onOpenOrderEntry: () => void;
  recentTrades: PixelTraderRecentTrade[];
}

const CANVAS_WIDTH = 256;
const CANVAS_HEIGHT = 288;

export function PixelTraderWorker({
  marketState,
  paused,
  autoTradingRunning,
  lastOrderAction,
  loading,
  onOpenOrderEntry,
  recentTrades,
}: PixelTraderWorkerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const particlesRef = useRef<MechaParticle[]>([]);
  const animationRef = useRef({
    state: "idle" as PixelTraderAnimationState,
    stateStartedAt: 0,
    consumedActionTimestamp: 0,
    lastFrameAt: 0,
  });
  const [visualState, setVisualState] = useState<PixelTraderAnimationState>("idle");
  const latestTradeText = useMemo(() => formatLatestTrade(recentTrades), [recentTrades]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return undefined;

    let rafId = 0;
    let hidden = false;

    const onVisibilityChange = () => {
      hidden = document.hidden;
      animationRef.current.lastFrameAt = performance.now();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    const render = (now: number) => {
      const state = animationRef.current;
      const delta = state.lastFrameAt ? now - state.lastFrameAt : 16;
      state.lastFrameAt = now;

      if (!hidden) {
        const result = resolvePixelTraderFrame({
          marketState,
          paused,
          autoTradingRunning,
          lastOrderAction,
          consumedActionTimestamp: state.consumedActionTimestamp,
          currentState: state.state,
          stateStartedAt: state.stateStartedAt || now,
          now,
        });
        state.state = result.state;
        state.stateStartedAt = result.stateStartedAt || now;
        state.consumedActionTimestamp = result.consumedActionTimestamp;
        if (result.triggerParticles) {
          state.consumedActionTimestamp = result.triggerParticles.timestamp;
          particlesRef.current = [
            ...particlesRef.current.slice(-40),
            ...createActionParticles(result.triggerParticles),
          ];
        }
        particlesRef.current = updateParticles(particlesRef.current, delta);

        ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
        drawMechaScene(ctx, result.frame);
        drawParticles(ctx, particlesRef.current);

        setVisualState((current) => (current === result.state ? current : result.state));
      }
      rafId = window.requestAnimationFrame(render);
    };

    rafId = window.requestAnimationFrame(render);
    return () => {
      window.cancelAnimationFrame(rafId);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [autoTradingRunning, lastOrderAction, marketState, paused]);

  const status = statusConfig(visualState, marketState, paused, autoTradingRunning);

  return (
    <section className={`pixel-trader-container ${status.className}`} aria-label="机甲指挥舱">
      <div className="pixel-trader-head">
        <div>
          <span className="pixel-trader-kicker">MECHA TRADER</span>
          <h2>机甲指挥舱</h2>
        </div>
        <div className="pixel-trader-actions">
          <Button className="pixel-trader-mini-button" onClick={onOpenOrderEntry} disabled={loading || paused || autoTradingRunning}>
            +委托
          </Button>
          <span className={`pixel-trader-state ${status.className}`}>{status.label}</span>
        </div>
      </div>

      <Button
        type="text"
        className="pixel-trader-canvas-button"
        onClick={onOpenOrderEntry}
        disabled={loading || paused || autoTradingRunning}
        aria-label="打开模拟委托弹窗"
      >
        <canvas ref={canvasRef} width={CANVAS_WIDTH} height={CANVAS_HEIGHT} />
      </Button>

      <div className="pixel-trader-status-bar">
        <span>
          <i className={`pixel-trader-status-dot ${status.className}`} />
          最近动作：{latestTradeText}
        </span>
        <span>核心温度：{autoTradingRunning ? "98%" : paused ? "18%" : marketState === "closed" ? "24%" : "72%"}</span>
      </div>
    </section>
  );
}

function formatLatestTrade(items: PixelTraderRecentTrade[]): string {
  const latest = items[0];
  if (!latest) return "等待首个委托";
  const action = latest.type === "buy" ? "买入" : "卖出";
  return `${action} ${latest.symbol} ${latest.name || ""} · ${latest.time}`;
}

function statusConfig(
  state: PixelTraderAnimationState,
  marketState: PixelTraderMarketState,
  paused: boolean,
  autoTradingRunning: boolean,
) {
  if (paused) return { className: "paused", label: "冻结" };
  if (autoTradingRunning || state === "auto_trading") return { className: "auto", label: "超频" };
  if (state === "buy_anim") return { className: "buy", label: "买入充能" };
  if (state === "sell_anim") return { className: "sell", label: "卖出冷却" };
  if (marketState === "closed" || state === "closed") return { className: "closed", label: "休眠" };
  if (marketState === "open" || state === "working") return { className: "working", label: "扫描中" };
  return { className: "idle", label: "待命" };
}
