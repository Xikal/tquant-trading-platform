import { createEffect, onCleanup } from "solid-js";
import { createReducedMotionSignal } from "../../shared/motion/reducedMotion";
import type { PaperMechaVisualState } from "./PaperMechaAvatar";

interface Particle {
  x: number;
  y: number;
  color: string;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
  shape: "circle" | "hexagon";
}

interface Shockwave {
  x: number;
  y: number;
  color: string;
  radius: number;
  maxRadius: number;
  life: number;
}

interface LanceEffect {
  progress: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export function PaperMechaParticles(props: { state: PaperMechaVisualState }) {
  let canvasRef!: HTMLCanvasElement;
  const reducedMotion = createReducedMotionSignal();

  createEffect(() => {
    const state = props.state;
    const canvas = canvasRef;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    if (reducedMotion()) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    let particles: Particle[] = [];
    let shockwaves: Shockwave[] = [];
    let lanceEffect: LanceEffect | null = null;
    let animationFrameId = 0;
    let width = 0;
    let height = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    resize();
    window.addEventListener("resize", resize);

    const renderLoop = () => {
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "screen";
      triggerBurst(state, width, height, particles, shockwaves, lanceEffect);
      if (state === "sell" && !lanceEffect) {
        lanceEffect = { progress: 0, x1: width + 50, y1: -50, x2: -50, y2: height + 50 };
      }
      particles = particles.filter((particle) => updateAndDrawParticle(ctx, particle));
      shockwaves = shockwaves.filter((shockwave) => updateAndDrawShockwave(ctx, shockwave));
      lanceEffect = drawLanceEffect(ctx, lanceEffect);
      animationFrameId = window.requestAnimationFrame(renderLoop);
    };

    renderLoop();

    onCleanup(() => {
      window.cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", resize);
    });
  });

  return <canvas ref={canvasRef} class="paper-mecha-action-panel__particles" aria-hidden="true" />;
}

function triggerBurst(
  state: PaperMechaVisualState,
  width: number,
  height: number,
  particles: Particle[],
  shockwaves: Shockwave[],
  lanceEffect: LanceEffect | null,
) {
  if (state === "buy") {
    if (Math.random() < 0.12) shockwaves.push(createShockwave(width / 2, height / 2, "rgb(239 68 68)", 150));
    for (let index = 0; index < 6; index += 1) {
      particles.push(createParticle(width / 2 + (Math.random() - 0.5) * 80, height - 30, `rgba(239, 68, 68, ${Math.random() * 0.7 + 0.3})`, (Math.random() - 0.5) * 3, -Math.random() * 8 - 4, Math.random() * 25 + 15, Math.random() * 5 + 3, "hexagon"));
    }
    return;
  }
  if (state === "sell") {
    if (!lanceEffect) shockwaves.push(createShockwave(width / 2, height / 2, "rgb(16 185 129)", 160));
    for (let index = 0; index < 5; index += 1) {
      particles.push(createParticle(Math.random() * width, Math.random() * height, `rgba(16, 185, 129, ${Math.random() * 0.8 + 0.2})`, (Math.random() - 0.5) * 6, (Math.random() - 0.5) * 6, Math.random() * 15 + 10, Math.random() * 3 + 1, "circle"));
    }
    return;
  }
  if (state === "profit" || state === "auto") {
    for (let index = 0; index < 3; index += 1) {
      particles.push(createParticle(width / 2 + (Math.random() - 0.5) * 120, height / 2 + (Math.random() - 0.5) * 120, `rgba(245, 158, 11, ${Math.random() * 0.8 + 0.2})`, (Math.random() - 0.5) * 4, (Math.random() - 0.5) * 4, Math.random() * 30 + 15, Math.random() * 3 + 2, "hexagon"));
    }
    return;
  }
  if (state === "risk") {
    if (Math.random() < 0.08) shockwaves.push(createShockwave(width / 2, height / 2, "rgb(239 68 68)", 120));
    particles.push(createParticle(width / 2 + (Math.random() - 0.5) * 150, height / 2 + (Math.random() - 0.5) * 150, `rgba(239, 68, 68, ${Math.random() * 0.7 + 0.2})`, (Math.random() - 0.5) * 5, (Math.random() - 0.5) * 5, Math.random() * 18 + 10, Math.random() * 4 + 2, "hexagon"));
  }
}

function createParticle(x: number, y: number, color: string, vx: number, vy: number, life: number, size: number, shape: Particle["shape"]): Particle {
  return { x, y, color, vx, vy, life, maxLife: life, size, shape };
}

function createShockwave(x: number, y: number, color: string, maxRadius: number): Shockwave {
  return { x, y, color, radius: 5, maxRadius, life: 25 };
}

function updateAndDrawParticle(ctx: CanvasRenderingContext2D, particle: Particle): boolean {
  particle.x += particle.vx;
  particle.y += particle.vy;
  particle.life -= 1;
  ctx.save();
  ctx.fillStyle = particle.color;
  ctx.globalAlpha = particle.life / particle.maxLife;
  ctx.beginPath();
  if (particle.shape === "hexagon") {
    for (let index = 0; index < 6; index += 1) {
      const angle = (Math.PI / 3) * index;
      const x = particle.x + Math.cos(angle) * particle.size;
      const y = particle.y + Math.sin(angle) * particle.size;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
  } else {
    ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
  }
  ctx.fill();
  ctx.restore();
  return particle.life > 0;
}

function updateAndDrawShockwave(ctx: CanvasRenderingContext2D, shockwave: Shockwave): boolean {
  shockwave.radius += (shockwave.maxRadius - shockwave.radius) * 0.15;
  shockwave.life -= 1;
  ctx.save();
  ctx.strokeStyle = shockwave.color;
  ctx.lineWidth = 2.5;
  ctx.globalAlpha = shockwave.life / 25;
  ctx.beginPath();
  for (let index = 0; index < 6; index += 1) {
    const angle = (Math.PI / 3) * index;
    const x = shockwave.x + Math.cos(angle) * shockwave.radius;
    const y = shockwave.y + Math.sin(angle) * shockwave.radius;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
  return shockwave.life > 0;
}

function drawLanceEffect(ctx: CanvasRenderingContext2D, effect: LanceEffect | null): LanceEffect | null {
  if (!effect) return null;
  effect.progress += 0.08;
  const progress = effect.progress;
  ctx.save();
  ctx.strokeStyle = "rgba(16, 185, 129, 0.9)";
  ctx.lineWidth = Math.max(0, 14 * (1 - progress));
  ctx.shadowColor = "rgb(16 185 129)";
  ctx.shadowBlur = 25;
  ctx.beginPath();
  ctx.moveTo(effect.x1, effect.y1);
  ctx.lineTo(effect.x1 + (effect.x2 - effect.x1) * progress, effect.y1 + (effect.y2 - effect.y1) * progress);
  ctx.stroke();
  ctx.restore();
  return progress >= 1.2 ? null : effect;
}
