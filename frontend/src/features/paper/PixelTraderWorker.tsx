import { useEffect, useMemo, useRef, type CSSProperties } from "react";
import { Button, Tag, Typography } from "antd";
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
  PixelTraderRecentTrade,
} from "./pixelTrader/types";
import { usePaperUiStore } from "../../stores/paperUiStore";

interface PixelTraderWorkerProps {
  marketState: PixelTraderMarketState;
  paused: boolean;
  autoTradingRunning: boolean;
  lastOrderAction: PixelTraderOrderAction | null;
  loading: boolean;
  onOpenOrderEntry: () => void;
  recentTrades: PixelTraderRecentTrade[];
}

type PixelTraderTone = "neutral" | "amber" | "cyan" | "green";

interface PixelTraderTheme {
  label: string;
  tone: PixelTraderTone;
  surfaceBackground: string;
  surfaceBorder: string;
  surfaceShadow: string;
  textColor: string;
  kickerColor: string;
  titleColor: string;
  buttonBackground: string;
  buttonBorder: string;
  buttonColor: string;
  badgeBackground: string;
  badgeBorder: string;
  badgeColor: string;
  dotColor: string;
  dotShadow?: string;
  canvasBackground: string;
  canvasBorder: string;
  canvasShadow: string;
  canvasFilter?: string;
  statusBarBackground: string;
  statusBarBorder: string;
  statusBarColor: string;
}

const CANVAS_WIDTH = 256;
const CANVAS_HEIGHT = 288;

const SURFACE_STYLE: CSSProperties = {
  position: "relative",
  minHeight: 300,
  display: "grid",
  gap: 8,
  overflow: "visible",
  padding: 10,
  borderRadius: 8,
  color: "#c8d6e5",
};

const HEADER_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 12,
  alignItems: "flex-start",
};

const KICKER_STYLE: CSSProperties = {
  display: "block",
  marginBottom: 3,
  fontFamily: '"IBM Plex Mono", "SFMono-Regular", monospace',
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.16em",
};

const TITLE_STYLE: CSSProperties = {
  margin: 0,
  fontSize: 13,
  lineHeight: 1.15,
};

const ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  gap: 7,
  alignItems: "center",
  flexWrap: "wrap",
  justifyContent: "flex-end",
};

const MINI_BUTTON_STYLE: CSSProperties = {
  minHeight: 24,
  padding: "3px 8px",
  borderRadius: 8,
  fontWeight: 700,
  fontSize: 12,
};

const BADGE_STYLE: CSSProperties = {
  minHeight: 24,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0 8px",
  borderRadius: 999,
  fontSize: 12,
  fontWeight: 700,
  margin: 0,
};

const CANVAS_BUTTON_STYLE: CSSProperties = {
  width: "min(100%, 260px)",
  height: "auto",
  minHeight: 0,
  margin: "0 auto",
  display: "grid",
  placeItems: "center",
  overflow: "visible",
  padding: 5,
  borderRadius: 10,
  lineHeight: 1,
};

const CANVAS_STYLE: CSSProperties = {
  width: "min(256px, 100%)",
  maxWidth: "100%",
  height: "auto",
  display: "block",
  imageRendering: "pixelated",
};

const STATUS_BAR_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: 8,
  alignItems: "center",
  width: "100%",
  padding: "6px 8px",
  borderRadius: 8,
  fontFamily: '"IBM Plex Mono", "SFMono-Regular", monospace',
  fontSize: 12,
  flexWrap: "wrap",
};

const STATUS_TEXT_STYLE: CSSProperties = {
  minWidth: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  display: "inline-flex",
  alignItems: "center",
};

const DOT_STYLE: CSSProperties = {
  width: 6,
  height: 6,
  display: "inline-block",
  marginRight: 5,
  borderRadius: "50%",
};

const BASE_THEME: Omit<PixelTraderTheme, "label" | "tone"> = {
  surfaceBackground: "#101826",
  surfaceBorder: "rgba(148, 163, 184, 0.18)",
  surfaceShadow: "inset 0 0 0 1px rgba(148, 163, 184, 0.08), 0 10px 24px rgba(15, 23, 42, 0.18)",
  textColor: "#c8d6e5",
  kickerColor: "rgba(200, 214, 229, 0.58)",
  titleColor: "#f8fafc",
  buttonBackground: "rgba(15, 23, 36, 0.72)",
  buttonBorder: "rgba(214, 165, 92, 0.5)",
  buttonColor: "#f4d08a",
  badgeBackground: "rgba(15, 23, 36, 0.72)",
  badgeBorder: "rgba(148, 163, 184, 0.18)",
  badgeColor: "#c8d6e5",
  dotColor: "#66758a",
  canvasBackground: "#08111f",
  canvasBorder: "rgba(42, 63, 90, 0.82)",
  canvasShadow: "inset 0 0 24px rgba(59, 130, 246, 0.08)",
  statusBarBackground: "rgba(15, 23, 36, 0.72)",
  statusBarBorder: "rgba(214, 165, 92, 0.15)",
  statusBarColor: "#c8d6e5",
};

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
  const visualState = usePaperUiStore((state) => state.pixelTraderVisualState);
  const setVisualState = usePaperUiStore((state) => state.setPixelTraderVisualState);
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

  const theme = statusConfig(visualState, marketState, paused, autoTradingRunning);
  const disabled = loading || paused || autoTradingRunning;

  return (
    <section
      aria-label="机甲指挥舱"
      style={{
        ...SURFACE_STYLE,
        border: `1px solid ${theme.surfaceBorder}`,
        background: theme.surfaceBackground,
        boxShadow: theme.surfaceShadow,
      }}
    >
      <div style={HEADER_STYLE}>
        <div>
          <span style={{ ...KICKER_STYLE, color: theme.kickerColor }}>MECHA TRADER</span>
          <Typography.Title level={5} style={{ ...TITLE_STYLE, color: theme.titleColor }}>
            机甲指挥舱
          </Typography.Title>
        </div>
        <div style={ACTIONS_STYLE}>
          <Button
            size="small"
            onClick={onOpenOrderEntry}
            disabled={disabled}
            style={{
              ...MINI_BUTTON_STYLE,
              borderColor: theme.buttonBorder,
              background: theme.buttonBackground,
              color: theme.buttonColor,
            }}
          >
            +委托
          </Button>
          <Tag
            style={{
              ...BADGE_STYLE,
              border: `1px solid ${theme.badgeBorder}`,
              background: theme.badgeBackground,
              color: theme.badgeColor,
            }}
          >
            {theme.label}
          </Tag>
        </div>
      </div>

      <Button
        type="text"
        style={{
          ...CANVAS_BUTTON_STYLE,
          border: `1px solid ${theme.canvasBorder}`,
          background: theme.canvasBackground,
          boxShadow: theme.canvasShadow,
        }}
        onClick={onOpenOrderEntry}
        disabled={disabled}
        aria-label="打开模拟委托弹窗"
      >
        <canvas
          ref={canvasRef}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          style={{
            ...CANVAS_STYLE,
            filter: theme.canvasFilter,
          }}
        />
      </Button>

      <div
        style={{
          ...STATUS_BAR_STYLE,
          border: `1px solid ${theme.statusBarBorder}`,
          background: theme.statusBarBackground,
          color: theme.statusBarColor,
        }}
      >
        <span style={STATUS_TEXT_STYLE}>
          <i
            style={{
              ...DOT_STYLE,
              background: theme.dotColor,
              boxShadow: theme.dotShadow,
            }}
          />
          最近动作：{latestTradeText}
        </span>
        <span style={STATUS_TEXT_STYLE}>
          核心温度：{autoTradingRunning ? "98%" : paused ? "18%" : marketState === "closed" ? "24%" : "72%"}
        </span>
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
): PixelTraderTheme {
  if (paused) {
    return createTheme("冻结", {
      tone: "amber",
      badgeBackground: "rgba(245, 158, 11, 0.12)",
      badgeBorder: "rgba(245, 158, 11, 0.38)",
      badgeColor: "var(--warning)",
      buttonBackground: "rgba(245, 158, 11, 0.1)",
      buttonBorder: "rgba(245, 158, 11, 0.45)",
      buttonColor: "var(--warning)",
      dotColor: "var(--warning)",
      canvasFilter: "grayscale(0.45) brightness(0.72) sepia(0.18)",
      statusBarBorder: "rgba(245, 158, 11, 0.18)",
    });
  }
  if (autoTradingRunning || state === "auto_trading") {
    return createTheme("超频", {
      tone: "amber",
      surfaceBorder: "rgba(214, 165, 92, 0.62)",
      surfaceBackground: "#1a1520",
      badgeBackground: "rgba(214, 165, 92, 0.16)",
      badgeBorder: "rgba(214, 165, 92, 0.58)",
      badgeColor: "var(--accent-gold)",
      buttonBackground: "rgba(214, 165, 92, 0.1)",
      buttonBorder: "rgba(214, 165, 92, 0.5)",
      buttonColor: "var(--accent-gold)",
      dotColor: "var(--accent-gold)",
      statusBarBorder: "rgba(214, 165, 92, 0.18)",
    });
  }
  if (state === "buy_anim") {
    return createTheme("买入充能", {
      tone: "amber",
      badgeBackground: "rgba(214, 165, 92, 0.16)",
      badgeBorder: "rgba(214, 165, 92, 0.58)",
      badgeColor: "var(--accent-gold)",
      buttonBackground: "rgba(214, 165, 92, 0.1)",
      buttonBorder: "rgba(214, 165, 92, 0.5)",
      buttonColor: "var(--accent-gold)",
      dotColor: "var(--accent-gold)",
      statusBarBorder: "rgba(214, 165, 92, 0.18)",
    });
  }
  if (state === "sell_anim") {
    return createTheme("卖出冷却", {
      tone: "cyan",
      badgeBackground: "rgba(6, 182, 212, 0.12)",
      badgeBorder: "rgba(6, 182, 212, 0.38)",
      badgeColor: "var(--info)",
      buttonBackground: "rgba(6, 182, 212, 0.1)",
      buttonBorder: "rgba(6, 182, 212, 0.38)",
      buttonColor: "var(--info)",
      dotColor: "var(--price-down)",
      statusBarBorder: "rgba(6, 182, 212, 0.18)",
    });
  }
  if (marketState === "closed" || state === "closed") {
    return createTheme("休眠", {
      tone: "neutral",
      badgeBackground: "rgba(71, 85, 105, 0.16)",
      badgeBorder: "rgba(100, 116, 139, 0.25)",
      badgeColor: "var(--text-3)",
      buttonBackground: "rgba(71, 85, 105, 0.14)",
      buttonBorder: "rgba(100, 116, 139, 0.22)",
      buttonColor: "var(--text-3)",
      dotColor: "var(--text-2)",
      canvasFilter: "grayscale(0.45) brightness(0.72) sepia(0.18)",
      statusBarBorder: "rgba(100, 116, 139, 0.18)",
    });
  }
  if (marketState === "open" || state === "working") {
    return createTheme("扫描中", {
      tone: "cyan",
      badgeBackground: "rgba(6, 182, 212, 0.12)",
      badgeBorder: "rgba(6, 182, 212, 0.38)",
      badgeColor: "var(--info)",
      buttonBackground: "rgba(6, 182, 212, 0.1)",
      buttonBorder: "rgba(6, 182, 212, 0.38)",
      buttonColor: "var(--info)",
      dotColor: "var(--info)",
      dotShadow: "0 0 6px var(--info)",
      statusBarBorder: "rgba(6, 182, 212, 0.18)",
    });
  }
  return createTheme("待命", {
    tone: "neutral",
  });
}

function createTheme(label: string, overrides: Partial<PixelTraderTheme>): PixelTraderTheme {
  return {
    ...BASE_THEME,
    label,
    tone: "neutral",
    ...overrides,
  };
}
