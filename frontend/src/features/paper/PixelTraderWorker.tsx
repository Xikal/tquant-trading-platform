import { useEffect, useRef } from "react";
import { resolvePixelTraderFrame } from "./pixelTrader/animations";
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
} from "./pixelTrader/types";
import { usePaperUiStore } from "../../stores/paperUiStore";

interface PixelTraderCoreProps {
  marketState: PixelTraderMarketState;
  paused: boolean;
  autoTradingRunning: boolean;
  lastOrderAction: PixelTraderOrderAction | null;
}

const CANVAS_WIDTH = 256;
const CANVAS_HEIGHT = 288;

export function PixelTraderAvatar(props: PixelTraderCoreProps) {
  const { canvasRef } = usePixelTraderCanvas(props);
  return (
    <div
      aria-label="模拟盘像素图"
      className="paper-conclusion__pixel"
    >
      <canvas
        ref={canvasRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        className="paper-conclusion__pixel-canvas"
      />
    </div>
  );
}

function usePixelTraderCanvas({
  marketState,
  paused,
  autoTradingRunning,
  lastOrderAction,
}: PixelTraderCoreProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const particlesRef = useRef<MechaParticle[]>([]);
  const animationRef = useRef({
    state: "idle" as PixelTraderAnimationState,
    stateStartedAt: 0,
    consumedActionTimestamp: 0,
    lastFrameAt: 0,
  });
  const setVisualState = usePaperUiStore((state) => state.setPixelTraderVisualState);

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

        if (usePaperUiStore.getState().pixelTraderVisualState !== result.state) {
          setVisualState(result.state);
        }
      }
      rafId = window.requestAnimationFrame(render);
    };

    rafId = window.requestAnimationFrame(render);
    return () => {
      window.cancelAnimationFrame(rafId);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [autoTradingRunning, lastOrderAction, marketState, paused, setVisualState]);

  return { canvasRef };
}
