import type { PixelTraderOrderAction } from "./types";

export interface MechaParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
  color: string;
  kind: "spark" | "coolant";
}

const BUY_COLORS = ["#c62828", "#e53935", "#ff8a80", "#ffcdd2"];
const SELL_COLORS = ["#1f8b4c", "#43a047", "#a5d6a7", "#c8e6c9"];

export function createActionParticles(action: PixelTraderOrderAction): MechaParticle[] {
  return action.type === "buy" ? createBuyParticles() : createSellParticles();
}

export function updateParticles(particles: MechaParticle[], deltaMs: number): MechaParticle[] {
  const delta = Math.min(deltaMs, 32) / 16.67;
  return particles
    .map((particle) => updateParticle(particle, delta))
    .filter((particle) => particle.life > 0);
}

export function drawParticles(ctx: CanvasRenderingContext2D, particles: MechaParticle[]) {
  for (const particle of particles) {
    const alpha = Math.max(0, particle.life / particle.maxLife);
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = particle.color;
    if (particle.kind === "spark") {
      ctx.fillRect(Math.round(particle.x), Math.round(particle.y), particle.size * 2, particle.size);
      ctx.fillRect(Math.round(particle.x + particle.size / 2), Math.round(particle.y - particle.size / 2), particle.size, particle.size * 2);
    } else {
      ctx.fillRect(Math.round(particle.x), Math.round(particle.y), particle.size, particle.size * 2);
    }
    ctx.restore();
  }
}

function updateParticle(particle: MechaParticle, delta: number): MechaParticle {
  const next = { ...particle };
  next.x += next.vx * delta;
  next.y += next.vy * delta;
  next.vy += (next.kind === "coolant" ? 0.035 : 0.015) * delta;
  next.life -= 16.67 * delta;
  if ((next.x < 4 || next.x > 252) && next.life > next.maxLife * 0.5) {
    next.vx *= -0.5;
  }
  if ((next.y < 4 || next.y > 284) && next.life > next.maxLife * 0.5) {
    next.vy *= -0.5;
  }
  return next;
}

function createBuyParticles(): MechaParticle[] {
  const particles: MechaParticle[] = [];
  for (let index = 0; index < 44; index += 1) {
    const angle = (Math.PI * 2 * index) / 44;
    const speed = 0.7 + Math.random() * 1.2;
    particles.push(makeParticle(128, 140, Math.cos(angle) * speed, Math.sin(angle) * speed, BUY_COLORS, "spark", 900 + Math.random() * 420));
  }
  for (const source of [{ x: 92, y: 102 }, { x: 164, y: 102 }]) {
    for (let index = 0; index < 18; index += 1) {
      particles.push(makeParticle(source.x, source.y, (Math.random() - 0.5) * 1.6, -0.8 - Math.random() * 1.5, BUY_COLORS, "spark", 800 + Math.random() * 320));
    }
  }
  return particles;
}

function createSellParticles(): MechaParticle[] {
  const particles: MechaParticle[] = [];
  for (const source of [{ x: 94, y: 180 }, { x: 162, y: 180 }, { x: 88, y: 122 }, { x: 168, y: 122 }]) {
    for (let index = 0; index < 14; index += 1) {
      particles.push(makeParticle(source.x, source.y, (Math.random() - 0.5) * 0.9, 0.35 + Math.random() * 1.2, SELL_COLORS, "coolant", 760 + Math.random() * 300));
    }
  }
  return particles;
}

function makeParticle(
  x: number,
  y: number,
  vx: number,
  vy: number,
  colors: string[],
  kind: MechaParticle["kind"],
  life: number,
): MechaParticle {
  return {
    x,
    y,
    vx,
    vy,
    life,
    maxLife: life,
    size: kind === "spark" ? 2 + Math.floor(Math.random() * 2) : 2,
    color: colors[Math.floor(Math.random() * colors.length)] ?? colors[0],
    kind,
  };
}
