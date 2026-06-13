import { createEffect, createMemo, createSignal, For, onCleanup, onMount, Show } from "solid-js";
import { useLocation, useNavigate } from "@tanstack/solid-router";
import { errorMessage } from "../../shared/api/errors";
import { useAuth } from "./authModel";
import "./LoginPage.css";

type Mode = "login" | "register";

const tickerItems = [
  ["行情连接", "--", "等待认证"],
  ["策略总闸", "--", "未进入工作台"],
  ["数据链路", "--", "登录后同步"],
  ["风险状态", "--", "等待读取"],
  ["WISE_QUANT", "--", "READY"],
];

const initialLogs = [
  "> NERV_SYSTEM_INITIALIZED...",
  "> Loading MAGI heuristic vectors...",
  "> Gate secured. Awaiting operator link...",
];

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  let canvasRef: HTMLCanvasElement | undefined;
  let talismanRef: HTMLCanvasElement | undefined;
  let cardRef: HTMLDivElement | undefined;
  let containerRef: HTMLElement | undefined;
  const [mode, setMode] = createSignal<Mode>("login");
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [displayName, setDisplayName] = createSignal("");
  const [mfaCode, setMfaCode] = createSignal("");
  const [remember, setRemember] = createSignal(true);
  const [showPassword, setShowPassword] = createSignal(false);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal("");
  const [beastMode, setBeastMode] = createSignal(false);
  const [cableConnected, setCableConnected] = createSignal(true);
  const [countdown, setCountdown] = createSignal(300);
  const [syncRate, setSyncRate] = createSignal(84.2);
  const [plugDepth, setPlugDepth] = createSignal(100);
  const [syncTuning, setSyncTuning] = createSignal(100);
  const [ping, setPing] = createSignal(12);
  const [logs, setLogs] = createSignal(initialLogs);
  const tradeDate = createMemo(() => new Date().toISOString().slice(0, 10));
  const countdownText = createMemo(() => {
    const seconds = countdown();
    const mins = Math.floor(seconds / 60).toString().padStart(2, "0");
    const rest = (seconds % 60).toString().padStart(2, "0");
    return cableConnected() ? "05:00:00" : `${mins}:${rest}:00`;
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    appendLog("> Operator credentials accepted. Deciphering code...");
    try {
      if (mode() === "login") {
        await auth.login({ username: username(), password: password(), mfa_code: mfaCode(), remember: remember() });
      } else {
        await auth.register({ username: username(), password: password(), display_name: displayName(), remember: remember() });
      }
      appendLog("> Console synchronized. Redirecting workspace...");
      await navigate({ to: safeRedirectPath(readSearchValue(location().search, "redirect")) });
    } catch (err) {
      const message = errorMessage(err);
      setError(message);
      appendLog("> SYNCHRONIZATION ERROR: credential gate rejected.");
    } finally {
      setLoading(false);
    }
  }

  function appendLog(line: string) {
    setLogs((items) => [...items.slice(-4), line]);
  }

  onMount(() => {
    const stopCanvas = startLoginCanvas(() => canvasRef, () => beastMode(), () => syncTuning() / 100);
    const stopTalisman = startTalismanCanvas(() => talismanRef, () => beastMode());
    const stopTilt = startCardTilt(() => containerRef, () => cardRef);
    const metricsTimer = window.setInterval(() => {
      setSyncRate(80 + Math.random() * 19.9);
      setPing(Math.floor(10 + Math.random() * 5));
      const nextLogs = [
        "> Syncing plug depth telemetry...",
        "> Re-calibrating A.T. Field indexes...",
        "> MAGI system computing vectors...",
        "> Deploying tactical portfolio buffers...",
      ];
      if (Math.random() < 0.45) appendLog(nextLogs[Math.floor(Math.random() * nextLogs.length)]);
    }, 3000);
    const countdownTimer = window.setInterval(() => {
      if (!cableConnected()) setCountdown((value) => Math.max(0, value - 1));
    }, 1000);

    onCleanup(() => {
      stopCanvas();
      stopTalisman();
      stopTilt();
      window.clearInterval(metricsTimer);
      window.clearInterval(countdownTimer);
    });
  });

  createEffect(() => {
    if (cableConnected()) setCountdown(300);
  });

  return (
    <main class={`wise-nerv-login${beastMode() ? " wise-nerv-login--beast" : ""}`}>
      <header class="wise-nerv-login__header">
        <div class="wise-nerv-login__stripes" />
        <div class="wise-nerv-ticker" aria-label="NERV secure stream">
          <div class="wise-nerv-ticker__track">
            <TickerGroup />
            <TickerGroup />
          </div>
        </div>
      </header>

      <div class="wise-nerv-login__scanlines" aria-hidden="true" />
      <div class="wise-nerv-login__field" aria-hidden="true" />
      <canvas ref={canvasRef} class="wise-nerv-login__canvas" aria-hidden="true" />

      <aside class="wise-nerv-hud wise-nerv-hud--left" aria-label="MAGI decision central">
        <div class="wise-nerv-hud__head">
          <span>[MAGI DECISION CENTRAL]</span>
          <strong>ONLINE</strong>
        </div>
        <div class="wise-nerv-hud__rows">
          <HudRow label="MELCHIOR-1" value="[AGREE]" tone="green" />
          <HudRow label="BALTHASAR-2" value="[AGREE]" tone="green" />
          <HudRow label="CASPAR-3" value="[RESOLVING]" tone="green" />
          <HudRow label="SYNC_RATE" value={`${syncRate().toFixed(1)}%`} tone="green" />
          <HudRow label="LCL_PRESSURE" value={`${(plugDepth() / 100).toFixed(2)} BAR`} tone="orange" />
          <HudRow label="GATE_STATUS" value="SECURED" tone="green" />
          <HudRow label="NET_LATENCY" value={`${ping()} ms`} tone="green" />
        </div>
        <div class="wise-nerv-spectrum" aria-label="synapse brain wave">
          <span>SYNAPSE BRAIN WAVE</span>
          <div>
            <For each={Array.from({ length: 18 })}>
              {(_, index) => <i style={{ "--bar-index": String(index()) }} />}
            </For>
          </div>
        </div>
        <div class="wise-nerv-log">
          <strong>[DIAGNOSTIC LOGS]</strong>
          <For each={logs()}>{(line) => <span>{line}</span>}</For>
        </div>
      </aside>

      <aside class="wise-nerv-hud wise-nerv-hud--right" aria-label="EVA unit diagnostics">
        <span class="wise-nerv-hud__title">EVA_UNIT_01 DIAGS</span>
        <canvas ref={talismanRef} width="160" height="150" class="wise-nerv-talisman" aria-hidden="true" />
        <div class="wise-nerv-power">
          <span>EXTERNAL POWER</span>
          <strong class={cableConnected() ? "wise-nerv-text-green" : "wise-nerv-text-red"}>
            {cableConnected() ? "CONNECTED" : "BATTERY MODE"}
          </strong>
          <em>{countdownText()}</em>
          <button
            type="button"
            onClick={() => {
              setCableConnected((value) => !value);
              appendLog(cableConnected() ? "> Umbilical cable disconnected." : "> Umbilical cable reconnected.");
            }}
          >
            {cableConnected() ? "[ DISCONNECT CABLE ]" : "[ RECONNECT CABLE ]"}
          </button>
        </div>
        <div class="wise-nerv-progress">
          <span>PLUG_DEPTH_BURST</span>
          <svg viewBox="0 0 72 72" aria-hidden="true">
            <circle cx="36" cy="36" r="28" />
            <circle cx="36" cy="36" r="28" style={{ "stroke-dashoffset": String(176 - (176 * syncRate()) / 100) }} />
          </svg>
          <strong>{syncRate().toFixed(1)}%</strong>
        </div>
      </aside>

      <section ref={containerRef} class="wise-nerv-stage">
        <div ref={cardRef} class="wise-nerv-card">
          <CornerMarks />
          <div class="wise-nerv-brand">
            <div class="wise-nerv-logo" aria-hidden="true">
              <span />
              <span />
              <svg viewBox="0 0 24 24" role="img" aria-label="WISE QUANT">
                <path d="M12 2 2 22h20L12 2Zm0 6 6 10H6l6-10Z" />
              </svg>
            </div>
            <h1>WISE <span>QUANT</span></h1>
            <p>初号机驾驶舱 · 极速量化研判终端</p>
          </div>

          <div class="wise-nerv-tabs" role="tablist" aria-label="登录模式">
            <button type="button" class="wise-nerv-tabs__item wise-nerv-tabs__item--active" role="tab" aria-selected="true">
              [ 常规登入 ]
            </button>
            <button type="button" class="wise-nerv-tabs__item" role="tab" aria-selected="false" disabled>
              [ LCL神经同步 ]
            </button>
            <button type="button" class="wise-nerv-tabs__item" role="tab" aria-selected="false" disabled>
              [ MAGI合议 ]
            </button>
          </div>

          <div class="wise-nerv-limiter">
            <div>
              <span>LIMITER OVERRIDE</span>
              <strong>{beastMode() ? "OVERLOAD: TYPE II (THE BEAST)" : "CODE: 02 (THE BEAST)"}</strong>
            </div>
            <button
              type="button"
              onClick={() => {
                setBeastMode((value) => !value);
                appendLog(beastMode() ? "> Limiter engaged: System secured." : "> Limiter released: Synaptic overlock.");
              }}
            >
              {beastMode() ? "[ 限制器复位 ]" : "[ 限制器解除 ]"}
            </button>
          </div>

          <Show when={error()}>
            <div class="wise-nerv-alert" role="alert">
              <span>!</span>
              <p>{error()}</p>
            </div>
          </Show>

          <form class="wise-nerv-form" onSubmit={submit}>
            <label class="wise-nerv-field">
              <input autocomplete="username" value={username()} onInput={(event) => setUsername(event.currentTarget.value)} required placeholder=" " />
              <span>OPERATOR ID / NERV MAIL (操作员账号)</span>
            </label>
            <Show when={mode() === "register"}>
              <label class="wise-nerv-field">
                <input value={displayName()} onInput={(event) => setDisplayName(event.currentTarget.value)} placeholder=" " />
                <span>DISPLAY NAME / PILOT CALLSIGN (操作员昵称)</span>
              </label>
            </Show>
            <label class="wise-nerv-field wise-nerv-field--password">
              <input
                type={showPassword() ? "text" : "password"}
                autocomplete={mode() === "login" ? "current-password" : "new-password"}
                value={password()}
                onInput={(event) => setPassword(event.currentTarget.value)}
                required
                placeholder=" "
              />
              <span>TACTICAL DECRYPT CODE (战术解密编码)</span>
              <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword() ? "隐藏密码" : "显示密码"}>
                {showPassword() ? "HIDE" : "VIEW"}
              </button>
            </label>
            <Show when={mode() === "login"}>
              <label class="wise-nerv-field">
                <input inputmode="numeric" value={mfaCode()} onInput={(event) => setMfaCode(event.currentTarget.value)} placeholder=" " />
                <span>MFA CODE / DYNAMIC TOKEN (未启用可留空)</span>
              </label>
            </Show>

            <div class="wise-nerv-options">
              <label>
                <input type="checkbox" checked={remember()} onChange={(event) => setRemember(event.currentTarget.checked)} />
                <span>突触连接保持与状态锁定</span>
              </label>
              <button type="button" onClick={() => setMode(mode() === "login" ? "register" : "login")} disabled={loading()}>
                {mode() === "login" ? "[ 开开户注册 ]" : "[ 返回登入 ]"}
              </button>
            </div>

            <div class="wise-nerv-actions">
              <button type="submit" class="wise-nerv-primary" disabled={loading()}>
                <span>{loading() ? "DECIPHERING CODE..." : mode() === "login" ? "Connect & Synch Neural Link" : "Create Pilot Access"}</span>
                <Show when={loading()}><i aria-hidden="true" /></Show>
              </button>
              <button type="button" class="wise-nerv-local-status" onClick={() => void navigate({ to: "/next/local-status" })}>
                打开本机状态
              </button>
              <p>登录后请先确认数据状态；页面展示不构成交易建议。</p>
            </div>
          </form>
        </div>
      </section>

      <section class="wise-nerv-controlbar" aria-label="LCL control">
        <label>
          <span>[LCL_FLUID_DEPTH]</span>
          <input type="range" min="50" max="150" value={plugDepth()} onInput={(event) => setPlugDepth(Number(event.currentTarget.value))} />
          <strong>{plugDepth()}%</strong>
        </label>
        <label>
          <span>[SYNAPSE_TUNING]</span>
          <input type="range" min="20" max="250" value={syncTuning()} onInput={(event) => setSyncTuning(Number(event.currentTarget.value))} />
          <strong>{(syncTuning() / 100).toFixed(1)}x</strong>
        </label>
      </section>

      <footer class="wise-nerv-footer">
        <span>TACTICAL PROTOCOL: <strong>MAGI-AES-GCM-256</strong></span>
        <span>TRADE DATE: <strong>{tradeDate()}</strong></span>
        <span>[ 战术风控制度警示 ]</span>
      </footer>
    </main>
  );
}

function TickerGroup() {
  return (
    <div class="wise-nerv-ticker__group">
      <strong>NERV SECURE STREAM:</strong>
      <For each={tickerItems}>
        {([name, value, change]) => (
          <span>
            {name} <em>{value}</em> <b>{change}</b>
          </span>
        )}
      </For>
    </div>
  );
}

function HudRow(props: { label: string; value: string; tone: "green" | "orange" }) {
  return (
    <p>
      <span>{props.label}:</span>
      <strong class={props.tone === "green" ? "wise-nerv-text-green" : "wise-nerv-text-orange"}>{props.value}</strong>
    </p>
  );
}

function CornerMarks() {
  return (
    <>
      <i class="wise-nerv-corner wise-nerv-corner--tl" />
      <i class="wise-nerv-corner wise-nerv-corner--tr" />
      <i class="wise-nerv-corner wise-nerv-corner--bl" />
      <i class="wise-nerv-corner wise-nerv-corner--br" />
    </>
  );
}

function startCardTilt(container: () => HTMLElement | undefined, card: () => HTMLElement | undefined) {
  const onMove = (event: MouseEvent) => {
    const target = card();
    if (!target) return;
    const rect = target.getBoundingClientRect();
    const x = event.clientX - rect.left - rect.width / 2;
    const y = event.clientY - rect.top - rect.height / 2;
    const rotateX = -(y / (rect.height / 2)) * 9;
    const rotateY = (x / (rect.width / 2)) * 9;
    target.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
  };
  const onLeave = () => {
    const target = card();
    if (target) target.style.transform = "rotateX(0deg) rotateY(0deg)";
  };
  const target = container();
  target?.addEventListener("mousemove", onMove);
  target?.addEventListener("mouseleave", onLeave);
  return () => {
    target?.removeEventListener("mousemove", onMove);
    target?.removeEventListener("mouseleave", onLeave);
  };
}

function startLoginCanvas(canvas: () => HTMLCanvasElement | undefined, beastMode: () => boolean, physicsMultiplier: () => number) {
  const canvasEl = canvas();
  if (!canvasEl) return () => undefined;
  const context = canvasEl.getContext("2d");
  if (!context) return () => undefined;
  const target = canvasEl;
  const ctx = context;
  let animation = 0;
  let width = 0;
  let height = 0;
  let mouseX = -9999;
  let mouseY = -9999;
  const particles = Array.from({ length: 52 }, () => ({
    x: Math.random(),
    y: Math.random(),
    vx: (Math.random() - 0.5) * 0.35,
    vy: (Math.random() - 0.5) * 0.35,
    radius: 1.2 + Math.random() * 1.6,
    tone: Math.random() > 0.5 ? "orange" : "green",
  }));

  function resize() {
    width = target.clientWidth || window.innerWidth;
    height = target.clientHeight || window.innerHeight;
    target.width = Math.max(1, Math.floor(width * window.devicePixelRatio));
    target.height = Math.max(1, Math.floor(height * window.devicePixelRatio));
    ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
  }

  function render() {
    const orange = beastMode() ? "#ff003c" : "#ff5500";
    const green = beastMode() ? "#d946ef" : "#00ff66";
    ctx.fillStyle = beastMode() ? "#150114" : "#080112";
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = beastMode() ? "rgba(255, 0, 60, 0.045)" : "rgba(255, 85, 0, 0.035)";
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 60) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const candleCount = 34;
    const step = width / candleCount;
    for (let index = 0; index < candleCount; index += 1) {
      const x = index * step + step / 2;
      const y = height * 0.55 + Math.sin(index * 0.28 + performance.now() / 2800) * 80;
      const bodyHeight = 20 + ((index * 11) % 40);
      const shadowHeight = bodyHeight + 24;
      ctx.save();
      ctx.globalAlpha = 0.12;
      ctx.strokeStyle = orange;
      ctx.fillStyle = orange;
      ctx.beginPath();
      ctx.moveTo(x, y - shadowHeight / 2);
      ctx.lineTo(x, y + shadowHeight / 2);
      ctx.stroke();
      ctx.fillRect(x - Math.min(8, step * 0.22), y - bodyHeight / 2, Math.min(16, step * 0.44), bodyHeight);
      ctx.restore();
    }

    for (let index = 0; index < particles.length; index += 1) {
      const particle = particles[index];
      particle.x += (particle.vx * physicsMultiplier()) / width;
      particle.y += (particle.vy * physicsMultiplier()) / height;
      if (particle.x < 0 || particle.x > 1) particle.vx *= -1;
      if (particle.y < 0 || particle.y > 1) particle.vy *= -1;
      const x = particle.x * width;
      const y = particle.y * height;
      const distance = Math.hypot(mouseX - x, mouseY - y);
      const boost = distance < 140 ? (140 - distance) / 140 : 0;
      ctx.save();
      ctx.globalAlpha = 0.16 + boost * 0.5;
      ctx.fillStyle = particle.tone === "orange" ? orange : green;
      ctx.beginPath();
      ctx.arc(x, y, particle.radius + boost * 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    if (mouseX > 0) {
      ctx.save();
      ctx.strokeStyle = beastMode() ? "rgba(255, 0, 60, 0.24)" : "rgba(255, 85, 0, 0.18)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < 6; i += 1) {
        const angle = (Math.PI / 3) * i;
        const x = mouseX + 78 * Math.cos(angle);
        const y = mouseY + 78 * Math.sin(angle);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();
      ctx.restore();
    }

    animation = requestAnimationFrame(render);
  }

  const onPointerMove = (event: PointerEvent) => {
    mouseX = event.clientX;
    mouseY = event.clientY;
  };
  const onPointerLeave = () => {
    mouseX = -9999;
    mouseY = -9999;
  };

  resize();
  window.addEventListener("resize", resize);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerleave", onPointerLeave);
  render();

  return () => {
    cancelAnimationFrame(animation);
    window.removeEventListener("resize", resize);
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerleave", onPointerLeave);
  };
}

function startTalismanCanvas(canvas: () => HTMLCanvasElement | undefined, beastMode: () => boolean) {
  const canvasEl = canvas();
  if (!canvasEl) return () => undefined;
  const context = canvasEl.getContext("2d");
  if (!context) return () => undefined;
  const target = canvasEl;
  const ctx = context;
  let animation = 0;
  let phase = 0;
  function draw() {
    phase += 0.04;
    ctx.clearRect(0, 0, target.width, target.height);
    const orange = beastMode() ? "#ff003c" : "#ff5500";
    const green = beastMode() ? "#f43f5e" : "#00ff66";
    const cx = 80;
    const cy = 78;
    const jaw = beastMode() ? 9 + Math.sin(phase * 3) * 2 : 0;
    ctx.save();
    ctx.strokeStyle = orange;
    ctx.fillStyle = beastMode() ? "rgba(255,0,60,0.18)" : "rgba(255,85,0,0.14)";
    ctx.lineWidth = 1.3;
    ctx.shadowBlur = 10;
    ctx.shadowColor = orange;
    ctx.beginPath();
    ctx.moveTo(cx, cy - 52);
    ctx.lineTo(cx - 26, cy - 7);
    ctx.lineTo(cx - 16, cy + 18);
    ctx.lineTo(cx + 16, cy + 18);
    ctx.lineTo(cx + 26, cy - 7);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx - 14, cy + 20 + jaw);
    ctx.lineTo(cx - 7, cy + 42 + jaw);
    ctx.lineTo(cx + 7, cy + 42 + jaw);
    ctx.lineTo(cx + 14, cy + 20 + jaw);
    ctx.closePath();
    ctx.stroke();
    ctx.fillStyle = green;
    ctx.shadowColor = green;
    ctx.beginPath();
    ctx.moveTo(cx - 9, cy);
    ctx.lineTo(cx - 3, cy + 3);
    ctx.lineTo(cx - 8, cy + 6);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(cx + 9, cy);
    ctx.lineTo(cx + 3, cy + 3);
    ctx.lineTo(cx + 8, cy + 6);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "rgba(0, 224, 255, 0.58)";
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.moveTo(cx, cy - 34);
    ctx.lineTo(cx - 58, cy - 34);
    ctx.moveTo(cx + 4, cy + 29 + jaw);
    ctx.lineTo(cx - 54, cy + 29 + jaw);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.font = "6px monospace";
    ctx.fillStyle = green;
    ctx.fillText("OPT_COHER", cx + 34, cy + 7);
    ctx.fillText(beastMode() ? "JAW_RELEASE" : "JAW_SEALED", cx - 72, cy + 32 + jaw);
    ctx.restore();
    animation = requestAnimationFrame(draw);
  }
  draw();
  return () => cancelAnimationFrame(animation);
}

function readSearchValue(search: unknown, key: string): unknown {
  return search && typeof search === "object" ? (search as Record<string, unknown>)[key] : undefined;
}

export function safeRedirectPath(value: unknown): "/next/monitor" | string {
  if (typeof value !== "string") return "/next/monitor";
  if (value.startsWith("//") || value.includes("://")) return "/next/monitor";
  if (!value.startsWith("/next/") && !isCutoverRootRedirect(value)) return "/next/monitor";
  return value;
}

function isCutoverRootRedirect(value: string): boolean {
  const path = value.split(/[?#]/, 1)[0];
  return [
    "/monitor",
    "/monitor/market",
    "/strategy-tracking",
    "/analysis",
    "/playbook",
    "/data",
    "/settings",
  ].includes(path);
}
