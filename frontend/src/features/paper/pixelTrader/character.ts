import type { PixelTraderFrame, PixelRect } from "./types";

const COLORS = {
  armorDark: "#0f1923",
  armorMid: "#162235",
  armorLight: "#1a2a3a",
  armorEdge: "#2a3f5a",
  coreGold: "#d6a55c",
  coreHot: "#e8b84b",
  coreWhite: "#fff3d6",
  neonBlue: "#3b82f6",
  neonBlueDark: "#1d4ed8",
  neonCyan: "#06b6d4",
  neonViolet: "#8b5cf6",
  neonPink: "#ec4899",
  neonLime: "#a3e635",
  warningAmber: "var(--warning)",
  tacticalRed: "var(--price-up)",
  tacticalRedHot: "var(--price-up)",
  tacticalGreen: "var(--price-down)",
  tacticalGreenCold: "var(--price-down)",
  cockpitBg: "#0f1724",
  cockpitGrid: "#1e293b",
  hologramGlow: "#1e3a5f",
  text: "#c8d6e5",
  muted: "#66758a",
  pausedOverlay: "#374151",
};

export function drawMechaScene(ctx: CanvasRenderingContext2D, frame: PixelTraderFrame) {
  ctx.imageSmoothingEnabled = false;
  drawCockpit(ctx, frame);
  drawThrusters(ctx, frame);
  drawMecha(ctx, frame);
  drawOverlay(ctx, frame);
}

function drawCockpit(ctx: CanvasRenderingContext2D, frame: PixelTraderFrame) {
  ctx.fillStyle = COLORS.cockpitBg;
  ctx.fillRect(0, 0, 256, 288);
  ctx.fillStyle = "#0b1220";
  ctx.fillRect(8, 10, 240, 268);
  ctx.strokeStyle = COLORS.cockpitGrid;
  ctx.lineWidth = 1;
  for (let x = 24; x < 240; x += 24) {
    line(ctx, x, 18, x, 270);
  }
  for (let y = 28; y < 270; y += 22) {
    line(ctx, 12, y, 244, y);
  }
  drawHologram(ctx, 22, 24, 56, 38, frame, "bars");
  drawHologram(ctx, 100, 18, 56, 42, frame, "matrix");
  drawHologram(ctx, 178, 24, 56, 38, frame, "radar");
  ctx.fillStyle = "#111b2d";
  ctx.fillRect(44, 214, 168, 24);
  ctx.fillStyle = COLORS.armorEdge;
  ctx.fillRect(50, 218, 156, 2);
  ctx.fillRect(68, 226, 34, 3);
  ctx.fillRect(154, 226, 34, 3);
  rects(ctx, [
    { x: 54, y: 224, w: 4, h: 4, color: COLORS.tacticalGreenCold, alpha: 0.85 },
    { x: 60, y: 224, w: 4, h: 4, color: COLORS.warningAmber, alpha: 0.9 },
    { x: 196, y: 224, w: 4, h: 4, color: COLORS.neonPink, alpha: 0.75 + frame.pulse * 0.25 },
    { x: 202, y: 224, w: 4, h: 4, color: COLORS.neonCyan, alpha: 0.75 + frame.pulse * 0.25 },
  ]);
}

function drawHologram(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  frame: PixelTraderFrame,
  mode: "bars" | "matrix" | "radar",
) {
  ctx.save();
  ctx.globalAlpha = 0.72;
  ctx.fillStyle = "#102a45";
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = COLORS.neonBlue;
  ctx.strokeRect(x, y, w, h);
  ctx.globalAlpha = 0.45 + frame.pulse * 0.25;
  ctx.fillStyle = COLORS.neonCyan;
  if (mode === "bars") {
    for (let i = 0; i < 10; i += 1) {
      const barHeight = 5 + ((i * 7 + Math.floor(frame.elapsedMs / 130)) % 24);
      ctx.fillStyle = i % 3 === 0 ? COLORS.tacticalRedHot : i % 3 === 1 ? COLORS.tacticalGreenCold : COLORS.warningAmber;
      ctx.fillRect(x + 5 + i * 5, y + h - 5 - barHeight, 2, barHeight);
    }
  } else if (mode === "matrix") {
    for (let row = 0; row < 4; row += 1) {
      for (let col = 0; col < 6; col += 1) {
        if ((row + col + Math.floor(frame.elapsedMs / 180)) % 3 !== 0) {
          ctx.fillStyle = (row + col) % 2 === 0 ? COLORS.neonViolet : COLORS.neonCyan;
          ctx.fillRect(x + 7 + col * 7, y + 7 + row * 8, 3, 3);
        }
      }
    }
  } else {
    ctx.strokeStyle = COLORS.neonCyan;
    ctx.beginPath();
    ctx.arc(x + w / 2, y + h / 2, 12, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = COLORS.neonViolet;
    ctx.beginPath();
    ctx.arc(x + w / 2, y + h / 2, 18, 0.2, Math.PI * 1.55);
    ctx.stroke();
    ctx.strokeStyle = COLORS.warningAmber;
    line(ctx, x + w / 2, y + h / 2, x + 10 + ((frame.elapsedMs / 30) % (w - 20)), y + 8);
    ctx.fillStyle = COLORS.neonPink;
    ctx.fillRect(x + 36, y + 13 + Math.sin(frame.elapsedMs / 220) * 8, 3, 3);
    ctx.fillStyle = COLORS.neonLime;
    ctx.fillRect(x + 18, y + 18 + Math.cos(frame.elapsedMs / 260) * 6, 3, 3);
  }
  ctx.restore();
}

function drawThrusters(ctx: CanvasRenderingContext2D, frame: PixelTraderFrame) {
  const flameHeight = Math.round(8 + frame.thrust * 22);
  rects(ctx, [
    { x: 74, y: 94, w: 18, h: 42, color: COLORS.armorDark },
    { x: 164, y: 94, w: 18, h: 42, color: COLORS.armorDark },
    { x: 78, y: 96, w: 10, h: flameHeight, color: frame.state === "buy_anim" ? COLORS.tacticalRedHot : COLORS.neonCyan, alpha: frame.thrust },
    { x: 168, y: 96, w: 10, h: flameHeight, color: frame.state === "buy_anim" ? COLORS.tacticalRedHot : COLORS.neonCyan, alpha: frame.thrust },
  ]);
}

function drawMecha(ctx: CanvasRenderingContext2D, frame: PixelTraderFrame) {
  const yFloat = frame.state === "closed" ? 3 : Math.round(Math.sin(frame.elapsedMs / 420) * 1);
  const arm = Math.round(frame.armSwing);
  drawLegs(ctx, yFloat);
  drawTorso(ctx, yFloat, frame);
  drawArms(ctx, yFloat, arm);
  drawHead(ctx, yFloat, frame);
  if (frame.state === "auto_trading") drawArcEffects(ctx, frame);
}

function drawLegs(ctx: CanvasRenderingContext2D, y: number) {
  rects(ctx, [
    { x: 104, y: 174 + y, w: 18, h: 34, color: COLORS.armorMid },
    { x: 134, y: 174 + y, w: 18, h: 34, color: COLORS.armorMid },
    { x: 100, y: 204 + y, w: 24, h: 10, color: COLORS.armorLight },
    { x: 132, y: 204 + y, w: 24, h: 10, color: COLORS.armorLight },
    { x: 105, y: 181 + y, w: 14, h: 3, color: COLORS.coreGold },
    { x: 137, y: 181 + y, w: 14, h: 3, color: COLORS.coreGold },
    { x: 110, y: 160 + y, w: 36, h: 18, color: COLORS.armorLight },
    { x: 116, y: 164 + y, w: 24, h: 6, color: COLORS.armorEdge },
  ]);
}

function drawTorso(ctx: CanvasRenderingContext2D, y: number, frame: PixelTraderFrame) {
  const coreAlpha = 0.35 + frame.pulse * 0.55;
  rects(ctx, [
    { x: 92, y: 94 + y, w: 72, h: 58, color: COLORS.armorMid },
    { x: 86, y: 100 + y, w: 84, h: 18, color: COLORS.armorLight },
    { x: 96, y: 104 + y, w: 64, h: 42, color: COLORS.armorDark },
    { x: 72, y: 88 + y, w: 34, h: 24, color: COLORS.armorLight },
    { x: 150, y: 88 + y, w: 34, h: 24, color: COLORS.armorLight },
    { x: 78, y: 94 + y, w: 20, h: 3, color: COLORS.neonViolet, alpha: 0.65 + frame.pulse * 0.25 },
    { x: 158, y: 94 + y, w: 20, h: 3, color: COLORS.neonCyan, alpha: 0.65 + frame.pulse * 0.25 },
    { x: 82, y: 104 + y, w: 12, h: 3, color: COLORS.warningAmber, alpha: 0.78 },
    { x: 162, y: 104 + y, w: 12, h: 3, color: COLORS.neonPink, alpha: 0.72 },
    { x: 111, y: 118 + y, w: 34, h: 30, color: COLORS.coreGold, alpha: 0.4 + frame.flash * 0.4 },
    { x: 116, y: 123 + y, w: 24, h: 20, color: frame.state === "sell_anim" ? COLORS.tacticalGreenCold : COLORS.coreHot, alpha: coreAlpha },
    { x: 123, y: 128 + y, w: 10, h: 10, color: COLORS.coreWhite, alpha: 0.55 + frame.pulse * 0.45 },
    { x: 102, y: 134 + y, w: 4, h: 4, color: COLORS.tacticalRedHot, alpha: 0.78 + frame.flash * 0.22 },
    { x: 150, y: 134 + y, w: 4, h: 4, color: COLORS.neonLime, alpha: 0.78 + frame.pulse * 0.22 },
  ]);
}

function drawArms(ctx: CanvasRenderingContext2D, y: number, arm: number) {
  rects(ctx, [
    { x: 68, y: 112 + y - Math.max(0, arm / 3), w: 20, h: 46, color: COLORS.armorMid },
    { x: 62, y: 138 + y - Math.max(0, arm / 4), w: 26, h: 24, color: COLORS.armorLight },
    { x: 168, y: 112 + y + Math.min(0, arm / 3), w: 20, h: 46, color: COLORS.armorMid },
    { x: 168, y: 138 + y + Math.min(0, arm / 4), w: 26, h: 24, color: COLORS.armorLight },
    { x: 74, y: 119 + y, w: 4, h: 28, color: COLORS.coreGold },
    { x: 178, y: 119 + y, w: 4, h: 28, color: COLORS.coreGold },
    { x: 66, y: 146 + y - Math.max(0, arm / 4), w: 14, h: 3, color: COLORS.neonPink, alpha: 0.72 },
    { x: 176, y: 146 + y + Math.min(0, arm / 4), w: 14, h: 3, color: COLORS.neonCyan, alpha: 0.72 },
  ]);
}

function drawHead(ctx: CanvasRenderingContext2D, y: number, frame: PixelTraderFrame) {
  const headY = 64 + y + (frame.state === "closed" ? 4 : 0);
  rects(ctx, [
    { x: 106, y: headY, w: 44, h: 28, color: COLORS.armorDark },
    { x: 112, y: headY + 5, w: 32, h: 16, color: COLORS.armorLight },
    { x: 116, y: headY + 9, w: 24, h: 7, color: COLORS.neonBlueDark },
    { x: 120, y: headY - 8, w: 4, h: 10, color: COLORS.warningAmber },
    { x: 132, y: headY - 8, w: 4, h: 10, color: COLORS.neonViolet },
    { x: 119, y: headY - 11, w: 6, h: 3, color: COLORS.neonPink, alpha: 0.75 + frame.pulse * 0.25 },
    { x: 131, y: headY - 11, w: 6, h: 3, color: COLORS.neonLime, alpha: 0.75 + frame.pulse * 0.25 },
  ]);
  if (frame.state !== "closed") {
    const scanY = headY + 9 + Math.round(frame.scanY % 7);
    ctx.fillStyle = COLORS.neonBlue;
    ctx.fillRect(117, scanY, 22, 1);
  } else {
    drawPixelText(ctx, "Z", 122, headY + 9, COLORS.muted);
  }
}

function drawArcEffects(ctx: CanvasRenderingContext2D, frame: PixelTraderFrame) {
  ctx.save();
  ctx.globalAlpha = 0.3 + frame.pulse * 0.35;
  ctx.strokeStyle = COLORS.coreGold;
  ctx.lineWidth = 2;
  line(ctx, 88, 96, 70 + Math.sin(frame.elapsedMs / 90) * 6, 78);
  line(ctx, 166, 98, 190 + Math.cos(frame.elapsedMs / 110) * 6, 78);
  line(ctx, 128, 118, 128 + Math.sin(frame.elapsedMs / 80) * 28, 84);
  ctx.restore();
}

function drawOverlay(ctx: CanvasRenderingContext2D, frame: PixelTraderFrame) {
  if (frame.flash > 0) {
    ctx.save();
    ctx.globalAlpha = frame.flash * 0.16;
    ctx.fillStyle = frame.state === "sell_anim" ? COLORS.tacticalGreen : COLORS.tacticalRed;
    ctx.fillRect(0, 0, 256, 288);
    ctx.restore();
  }
  if (frame.state === "paused") {
    ctx.save();
    ctx.globalAlpha = 0.24;
    ctx.fillStyle = COLORS.pausedOverlay;
    ctx.fillRect(0, 0, 256, 288);
    ctx.restore();
  }
  if (frame.label) {
    drawPixelText(ctx, frame.label, 84, 46 - Math.round(frame.stateElapsedMs / 90), frame.state === "sell_anim" ? COLORS.tacticalGreenCold : COLORS.tacticalRedHot);
  }
}

function rects(ctx: CanvasRenderingContext2D, items: PixelRect[]) {
  for (const item of items) {
    ctx.save();
    if (typeof item.alpha === "number") ctx.globalAlpha = Math.max(0, Math.min(1, item.alpha));
    ctx.fillStyle = item.color;
    ctx.fillRect(Math.round(item.x), Math.round(item.y), Math.round(item.w), Math.round(item.h));
    ctx.restore();
  }
}

function line(ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) {
  ctx.beginPath();
  ctx.moveTo(Math.round(x1), Math.round(y1));
  ctx.lineTo(Math.round(x2), Math.round(y2));
  ctx.stroke();
}

function drawPixelText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string) {
  ctx.save();
  ctx.fillStyle = color;
  ctx.font = "8px monospace";
  ctx.textBaseline = "top";
  ctx.fillText(text, x, y);
  ctx.restore();
}
