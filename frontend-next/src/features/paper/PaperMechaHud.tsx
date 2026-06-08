import { For, createSignal } from "solid-js";
import { readArray, readRecord, text } from "../shared/dataAccess";
import { MECHA_UNITS, PaperMechaAvatar, type PaperMechaUnitId, type PaperMechaVisualState } from "./PaperMechaAvatar";
import { PaperMechaParticles } from "./PaperMechaParticles";

interface MechaHudState {
  key: PaperMechaVisualState;
  label: string;
  syncRate: string;
  caption: string;
  apiLabel: string;
}

export function PaperMechaHud(props: { root: Record<string, unknown>; apiState?: "loading" | "ready" | "error" }) {
  const [activeUnitId, setActiveUnitId] = createSignal<PaperMechaUnitId>("purple");
  const state = () => resolveMechaHudState(props.root, props.apiState ?? "ready");
  const activeUnit = () => MECHA_UNITS[activeUnitId()] ?? MECHA_UNITS.purple;

  return (
    <aside class={`paper-mecha-action-panel paper-mecha-action-panel--${state().key} paper-mecha-action-panel--unit-${activeUnitId()} paper-mecha-action-panel--effects-active`} aria-label="模拟盘机甲交易舱">
      <div class="paper-mecha-action-panel__chooser" aria-label="特设机型选择舱">
        <For each={Object.entries(MECHA_UNITS)}>
          {([unitId, unit]) => {
            const typedUnitId = unitId as PaperMechaUnitId;
            const active = () => typedUnitId === activeUnitId();
            return (
              <button
                type="button"
                class={`paper-mecha-action-panel__unit-option${active() ? " paper-mecha-action-panel__unit-option--active" : ""}`}
                onClick={() => setActiveUnitId(typedUnitId)}
                aria-pressed={active()}
                title={`${unit.name} - ${unit.desc}`}
              >
                <span class="paper-mecha-action-panel__unit-thumb" aria-hidden="true">
                  <PaperMechaAvatar unitId={typedUnitId} state={state().key} mini />
                </span>
                <span>{unit.name}</span>
              </button>
            );
          }}
        </For>
      </div>
      <div class="paper-mecha-action-panel__stage">
        <PaperMechaParticles state={state().key} />
        <div class="paper-mecha-action-panel__glow" aria-hidden="true" />
        <div class="paper-mecha-action-panel__at-field" aria-hidden="true">
          <svg viewBox="0 0 100 100">
            <polygon points="50,3 93,28 93,78 50,103 7,78 7,28" />
            <polygon points="50,10 87,31 87,71 50,92 13,71 13,31" />
            <polygon points="50,18 80,35 80,67 50,84 20,67 20,35" />
          </svg>
        </div>
        <svg class="paper-mecha-action-panel__ring paper-mecha-action-panel__ring--slow" viewBox="0 0 200 200" aria-hidden="true">
          <circle cx="100" cy="100" r="92" />
          <circle cx="100" cy="100" r="88" />
        </svg>
        <svg class="paper-mecha-action-panel__ring paper-mecha-action-panel__ring--reverse" viewBox="0 0 200 200" aria-hidden="true">
          <circle cx="100" cy="100" r="84" />
          <path d="M 100,6 A 94,94 0 0,1 194,100" />
        </svg>
        <div class="paper-mecha-action-panel__readout" aria-hidden="true">
          <span>二号机：激活</span>
          <span>同步状态</span>
        </div>
        <div class={`paper-mecha-action-panel__avatar paper-mecha-action-panel__avatar--${state().key}`}>
          <PaperMechaAvatar unitId={activeUnitId()} state={state().key} />
          <div class="state-sell-overlay" aria-hidden="true" />
          <div class="state-loss-overlay" aria-hidden="true" />
        </div>
        <div class="paper-mecha-action-panel__sync">
          <strong>同步：{state().syncRate}</strong>
          <span>{state().caption}</span>
        </div>
      </div>
      <div class="paper-mecha-action-panel__status">
        <div>
          <span>当前代号：</span>
          <strong>{activeUnit().name}</strong>
        </div>
        <div>
          <span>实时状态：</span>
          <strong>{state().label}</strong>
        </div>
        <div>
          <span>数据：</span>
          <strong>{state().apiLabel}</strong>
        </div>
      </div>
      <div class="paper-mecha-action-panel__monitor">
        <PaperMechaLog root={props.root} apiState={props.apiState ?? "ready"} />
      </div>
    </aside>
  );
}

function PaperMechaLog(props: { root: Record<string, unknown>; apiState: "loading" | "ready" | "error" }) {
  const actions = () => buildActionTimeline(props.root, props.apiState);
  return (
    <section class="paper-action-hud paper-action-hud--embedded" aria-label="今日动作与自动交易状态">
      <div class="paper-action-hud__monitor">
        <div class="paper-action-hud__panel-title paper-action-hud__panel-title--split">
          <span>
            <span class="paper-action-hud__title-mark paper-action-hud__title-mark--pulse" />
            实时同步监控日志
          </span>
          <strong>系统流：正常</strong>
        </div>
        <div class="paper-action-hud__console" role="log">
          <For each={actions()}>
            {(item) => (
              <p>
                <span>[{item.time}] </span>
                <strong class={`paper-action-hud__log-tag paper-action-hud__log-tag--${item.tone}`}>{item.title}：</strong>
                <span> {item.detail}</span>
              </p>
            )}
          </For>
        </div>
      </div>
    </section>
  );
}

function resolveMechaHudState(root: Record<string, unknown>, apiState: "loading" | "ready" | "error"): MechaHudState {
  if (apiState === "error") return { key: "risk", label: "数据异常", syncRate: "00.0%", caption: "降级显示", apiLabel: "暂不可用" };
  if (apiState === "loading") return { key: "auto", label: "同步中", syncRate: "42.0%", caption: "等待数据", apiLabel: "加载中" };
  const autoTradingStatus = readRecord(root.auto_trading_status);
  const autoTradingRuns = readArray<Record<string, unknown>>(root.auto_trading_runs);
  const riskEvents = readArray<Record<string, unknown>>(root.risk_events);
  const hasOpenRisk = riskEvents.some((item) => text(item.status) !== "已解决") || autoTradingStatus.circuit_open === true;
  if (hasOpenRisk) return { key: "risk", label: "风险拦截", syncRate: "15.6%", caption: "风险检查", apiLabel: "正常" };
  if (autoTradingRuns.some((item) => item.status === "failed")) return { key: "loss", label: "异常复核", syncRate: "31.2%", caption: "损伤检查", apiLabel: "正常" };
  if (autoTradingStatus.running === true || autoTradingStatus.engine_running === true) return { key: "auto", label: "自动监控", syncRate: "89.4%", caption: "循环同步", apiLabel: "正常" };
  if (autoTradingStatus.trading_time === false) return { key: "closed", label: "休眠", syncRate: "52.0%", caption: "市场休眠", apiLabel: "正常" };
  return { key: "idle", label: "待命", syncRate: "84.2%", caption: "执行待命", apiLabel: "正常" };
}

function buildActionTimeline(root: Record<string, unknown>, apiState: "loading" | "ready" | "error") {
  const autoTradingStatus = readRecord(root.auto_trading_status);
  const autoTradingRuns = readArray<Record<string, unknown>>(root.auto_trading_runs);
  const items = autoTradingRuns.slice(0, 3).map((item) => {
    const response = readRecord(item.response);
    const summary = text(response.summary ?? item.error_message ?? runStatusText(item.status));
    return {
      time: formatPaperTime(item.created_at),
      title: runStatusText(item.status),
      detail: summary,
      tone: runStatusTone(item.status),
    };
  });
  if (autoTradingStatus.last_cycle_at && autoTradingStatus.last_cycle_summary) {
    items.unshift({
      time: formatPaperTime(autoTradingStatus.last_cycle_at),
      title: "信息",
      detail: text(autoTradingStatus.last_cycle_summary),
      tone: "info",
    });
  }
  if (apiState === "error") {
    items.unshift({
      time: formatPaperTime(new Date().toISOString()),
      title: "风险",
      detail: "模拟盘数据暂不可用，头像与特效保持可见",
      tone: "risk",
    });
  }
  if (apiState === "loading") {
    items.unshift({
      time: formatPaperTime(new Date().toISOString()),
      title: "连接",
      detail: "正在等待模拟盘数据，同步失败会显示为降级状态",
      tone: "link",
    });
  }
  if (!items.length) {
    items.push(
      { time: "09:30:00", title: "启动", detail: "维斯量化终端同步启动", tone: "init" },
      { time: "09:30:05", title: "连接", detail: "神经元连接同步率稳定在 84.2%", tone: "link" },
      { time: "09:31:24", title: "信息", detail: "沪深两市指数馈入开始", tone: "info" },
    );
  }
  return items.slice(0, 4);
}

function formatPaperTime(value: unknown): string {
  if (!value) return "09:30:00";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "09:30:00";
  return date.toLocaleTimeString("zh-CN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function runStatusText(status: unknown): string {
  if (status === "succeeded") return "卖出";
  if (status === "failed") return "风险";
  if (status === "skipped") return "信息";
  if (status === "running") return "自动";
  return "连接";
}

function runStatusTone(status: unknown): string {
  if (status === "succeeded") return "sell";
  if (status === "failed") return "risk";
  if (status === "running") return "auto";
  return "info";
}
