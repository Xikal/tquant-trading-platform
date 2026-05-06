import type {
  AdminTaskStatus,
  FactorWeightsResponse,
  LowBuyStrategyGovernanceResponse,
  RuntimeStatus,
  SettingsPayload,
} from "../../types";
import { useEffect, useMemo, useRef, useState } from "react";
import { featureFlagsApi, type FeatureFlagItem } from "../../api/featureFlags";
import { NumberField, TextField } from "../../components/shared/FormFields";
import { InfoPill, PanelTitle, SettingCard } from "./WorkspaceComponents";
import { readySummary } from "./workspaceFormatters";
import type { SettingsDraft } from "./workspaceTypes";

export function SettingsPage({
  settings,
  runtime,
  factorWeights,
  adminTasks,
  strategyGovernance,
  factorDraft,
  draft,
  setDraft,
  setFactorDraft,
  loading,
  onSave,
  onSaveFactors,
  onRefresh,
  onUpdateStrategyGovernance,
}: {
  settings: SettingsPayload | null;
  runtime: RuntimeStatus | null;
  factorWeights: FactorWeightsResponse | null;
  adminTasks: AdminTaskStatus[];
  strategyGovernance: LowBuyStrategyGovernanceResponse | null;
  factorDraft: Record<string, string>;
  draft: SettingsDraft;
  setDraft: (draft: SettingsDraft) => void;
  setFactorDraft: (draft: Record<string, string>) => void;
  loading: string;
  onSave: (section: "llm" | "risk" | "data") => void | Promise<void>;
  onSaveFactors: () => void | Promise<void>;
  onRefresh: () => void;
  onUpdateStrategyGovernance: (strategyKey: string, status: "active" | "watch" | "paused") => void;
}) {
  const [savedSection, setSavedSection] = useState("");
  const [featureFlags, setFeatureFlags] = useState<FeatureFlagItem[]>([]);
  const [featureFlagError, setFeatureFlagError] = useState("");
  const savedTimerRef = useRef<number | null>(null);
  const adminTokenError = draft.adminToken.trim() ? "" : "保存配置前需要填写管理令牌";
  const llmKeyError = !settings?.llm_api_key_configured && !draft.llm_api_key.trim() ? "首次配置大模型需要填写 API Key" : "";
  const llmBaseUrlError = urlFieldError(draft.llm_base_url, "模型接口地址");
  const dataSourceUrlError = urlFieldError(draft.data_source_base_url, "数据源地址");
  const singleLossError = percentFieldError(draft.risk_max_single_loss_pct, "单笔最大亏损");
  const dailyLossError = percentFieldError(draft.risk_max_daily_loss_pct, "日内最大亏损");
  const pauseLossError = integerFieldError(draft.risk_pause_after_losses, "连亏暂停");
  const minProfitError = percentFieldError(draft.strategy_min_profit_pct, "最小收益");
  const dirtyState = useMemo(() => buildSettingsDirtyState(settings, factorWeights, draft, factorDraft), [draft, factorDraft, factorWeights, settings]);
  const unsavedCount = Object.values(dirtyState).filter(Boolean).length;

  async function saveSection(section: "llm" | "risk" | "data" | "factor") {
    const error = sectionError(section, {
      adminTokenError,
      llmKeyError,
      llmBaseUrlError,
      dataSourceUrlError,
      singleLossError,
      dailyLossError,
      pauseLossError,
      minProfitError,
    });
    if (error) {
      return;
    }
    if (section === "factor") {
      await Promise.resolve(onSaveFactors());
    } else {
      await Promise.resolve(onSave(section));
    }
    markSaved(section);
  }

  async function saveAllDirty() {
    const sections: Array<"llm" | "risk" | "data" | "factor"> = [];
    if (dirtyState.llm) sections.push("llm");
    if (dirtyState.data) sections.push("data");
    if (dirtyState.risk) sections.push("risk");
    if (dirtyState.factor) sections.push("factor");
    for (const section of sections) {
      await saveSection(section);
    }
  }

  function markSaved(section: string) {
    setSavedSection(section);
    if (savedTimerRef.current) {
      window.clearTimeout(savedTimerRef.current);
    }
    savedTimerRef.current = window.setTimeout(() => setSavedSection(""), 3000);
  }

  useEffect(() => {
    let cancelled = false;
    featureFlagsApi.list()
      .then((payload) => {
        if (!cancelled) {
          setFeatureFlags(payload.items ?? []);
          setFeatureFlagError("");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setFeatureFlagError(error instanceof Error ? error.message : "功能开关加载失败");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function toggleFeatureFlag(item: FeatureFlagItem) {
    try {
      const updated = await featureFlagsApi.update(item.key, !item.enabled);
      setFeatureFlags((current) => current.map((flag) => flag.key === item.key ? updated.item : flag));
      markSaved("feature-flags");
      setFeatureFlagError("");
    } catch (error) {
      setFeatureFlagError(error instanceof Error ? error.message : "功能开关更新失败");
    }
  }

  return (
    <section className="page-grid settings-grid">
      <div className="panel settings-hero">
        <PanelTitle title="开放式系统配置" actions={<button onClick={onRefresh} disabled={loading === "settings"}>刷新配置</button>} />
        <p className="hint">管理大模型、数据库、数据源、风险控制和策略阈值。敏感值只保存，不回显明文。</p>
        {unsavedCount > 0 ? (
          <div className="settings-unsaved-banner">
            <span>有 {unsavedCount} 项未保存的更改</span>
            <button type="button" onClick={() => void saveAllDirty()} disabled={Boolean(loading)}>
              全部保存
            </button>
          </div>
        ) : null}
      </div>
      <div className="settings-cards">
        <SettingCard title="大模型配置" button="保存大模型配置" onSave={() => void saveSection("llm")} loading={loading === "settings-llm"} saved={savedSection === "llm"} disabled={Boolean(adminTokenError || llmKeyError || llmBaseUrlError)}>
          <div className="compact-form-grid">
            <TextField label="管理令牌" value={draft.adminToken} error={adminTokenError} onChange={(event) => setDraft({ ...draft, adminToken: event.target.value })} />
            <TextField label="API Key" value={draft.llm_api_key} error={llmKeyError} onChange={(event) => setDraft({ ...draft, llm_api_key: event.target.value })} />
            <TextField label="Base URL" value={draft.llm_base_url} error={llmBaseUrlError} onChange={(event) => setDraft({ ...draft, llm_base_url: event.target.value })} />
            <TextField label="模型名" value={draft.llm_model} onChange={(event) => setDraft({ ...draft, llm_model: event.target.value })} />
            <TextField label="供应商" value={draft.llm_provider} placeholder="openai / deepseek" onChange={(event) => setDraft({ ...draft, llm_provider: event.target.value })} />
          </div>
          <p className="hint">当前状态：{settings?.llm_api_key_configured ? "Key 已配置" : "Key 未配置"}</p>
        </SettingCard>
        <SettingCard title="数据库与数据源" button="保存数据配置" onSave={() => void saveSection("data")} loading={loading === "settings-data"} saved={savedSection === "data"} disabled={Boolean(adminTokenError || dataSourceUrlError)}>
          <div className="compact-form-grid">
            <TextField label="数据源" value={draft.data_source} hint={adminTokenError || "保存数据源配置同样需要管理令牌。"} onChange={(event) => setDraft({ ...draft, data_source: event.target.value })} />
            <TextField label="数据源地址" value={draft.data_source_base_url} error={dataSourceUrlError} onChange={(event) => setDraft({ ...draft, data_source_base_url: event.target.value })} />
          </div>
          <InfoPill label="数据库" value={runtime?.database_url_masked ?? "--"} />
          <InfoPill label="接口前缀" value={runtime?.api_prefix ?? "/api"} />
        </SettingCard>
        <SettingCard title="风控参数" button="保存风控参数" onSave={() => void saveSection("risk")} loading={loading === "settings-risk"} saved={savedSection === "risk"} disabled={Boolean(adminTokenError || singleLossError || dailyLossError || pauseLossError || minProfitError)}>
          <div className="compact-form-grid">
            <NumberField label="单笔最大亏损" suffix="%" value={draft.risk_max_single_loss_pct} error={singleLossError} onChange={(event) => setDraft({ ...draft, risk_max_single_loss_pct: event.target.value })} />
            <NumberField label="日内最大亏损" suffix="%" value={draft.risk_max_daily_loss_pct} error={dailyLossError} onChange={(event) => setDraft({ ...draft, risk_max_daily_loss_pct: event.target.value })} />
            <NumberField label="连亏暂停" value={draft.risk_pause_after_losses} error={pauseLossError} onChange={(event) => setDraft({ ...draft, risk_pause_after_losses: event.target.value })} />
            <NumberField label="最小收益" suffix="%" value={draft.strategy_min_profit_pct} error={minProfitError} onChange={(event) => setDraft({ ...draft, strategy_min_profit_pct: event.target.value })} />
          </div>
          <p className="hint">{adminTokenError || "保存后会影响后续信号，不会修改已有复盘记录。"}</p>
        </SettingCard>
        <SettingCard title="因子权重" button="保存因子权重" onSave={() => void saveSection("factor")} loading={loading === "settings-factor"} saved={savedSection === "factor"} disabled={Boolean(adminTokenError)}>
          {factorWeights ? (
            <div className="factor-weight-grid">
              {factorWeights.factors.map((factor) => (
                <label key={factor.name}>
                  <span>{factor.name}</span>
                  <input
                    value={factorDraft[factor.name] ?? String(factorWeights.weights[factor.name] ?? factor.weight)}
                    inputMode="decimal"
                    onChange={(event) => setFactorDraft({ ...factorDraft, [factor.name]: event.target.value })}
                  />
                  <small>{factor.data_dependencies.join(" / ") || "基础因子"}</small>
                  <small className={`factor-status ${factor.status}`}>{factor.status_text || factor.status}</small>
                </label>
              ))}
            </div>
          ) : (
            <p className="hint">填写管理令牌后点击刷新配置，即可加载因子权重。未加载时不会影响策略运行。</p>
          )}
        </SettingCard>
        <SettingCard title="策略治理" button="刷新策略状态" onSave={onRefresh} loading={loading === "settings"}>
          <InfoPill label="默认策略" value={strategyGovernance?.default_strategy ?? "--"} />
          <InfoPill label="生产策略" value={strategyGovernance ? `${strategyGovernance.production_strategies.length} 个` : "--"} />
          <InfoPill label="治理状态" value={strategyGovernance ? strategyGovernanceSummary(strategyGovernance) : "--"} />
          {strategyGovernance ? (
            <div className="settings-mini-list">
              {strategyGovernance.items.slice(0, 8).map((item) => (
                <div key={item.strategy_key} className="settings-mini-row">
                  <span>
                    {item.strategy_title}
                    <small className="hint">{item.strategy_key}</small>
                  </span>
                  <strong className={`governance-status ${item.status}`}>
                    {item.strategy_health_score ? `${item.strategy_health_score} / ${item.status_text || item.status}` : item.status_text || item.status}
                  </strong>
                  {item.auto_governance_reason ? (
                    <small className="hint">{item.auto_governance_reason}</small>
                  ) : null}
                  <div className="settings-row-actions">
                    <button type="button" onClick={() => onUpdateStrategyGovernance(item.strategy_key, "active")} disabled={loading === "settings"}>恢复</button>
                    <button type="button" onClick={() => onUpdateStrategyGovernance(item.strategy_key, "watch")} disabled={loading === "settings"}>观察</button>
                    <button type="button" onClick={() => onUpdateStrategyGovernance(item.strategy_key, "paused")} disabled={loading === "settings"}>暂停</button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="hint">策略治理未加载，刷新后会显示生产/研究/因子分层。</p>
          )}
        </SettingCard>
        <SettingCard title="功能开关" button="刷新开关" onSave={() => {
          featureFlagsApi.list()
            .then((payload) => {
              setFeatureFlags(payload.items ?? []);
              setFeatureFlagError("");
            })
            .catch((error) => setFeatureFlagError(error instanceof Error ? error.message : "功能开关加载失败"));
        }} loading={loading === "settings"} saved={savedSection === "feature-flags"}>
          {featureFlagError ? <p className="form-error">{featureFlagError}</p> : null}
          <div className="settings-mini-list">
            {featureFlags.length ? featureFlags.map((item) => (
              <div key={item.key} className="settings-mini-row">
                <span>
                  {item.key}
                  <small className="hint">{item.description || "无说明"}</small>
                </span>
                <strong className={item.enabled ? "task-ok" : "task-error"}>{item.enabled ? "开启" : "关闭"}</strong>
                <button type="button" onClick={() => void toggleFeatureFlag(item)}>
                  {item.enabled ? "关闭" : "开启"}
                </button>
              </div>
            )) : <p className="hint">功能开关未加载。</p>}
          </div>
          <p className="hint">普通用户可查看，只有管理员可以修改；修改会写入审计日志。</p>
        </SettingCard>
        <SettingCard title="运行诊断" button="重新检测" onSave={onRefresh} loading={loading === "settings"}>
          <InfoPill label="前端产物" value={runtime?.frontend_dist_ready ? "正常" : "--"} />
          <InfoPill label="AI 分析" value={runtime?.llm_configured ? "已配置" : "未配置"} />
          <InfoPill label="环境文件" value={runtime?.runtime_env_exists ? "存在" : "--"} />
          <InfoPill label="数据库后端" value={runtime?.database_backend ?? "--"} />
          <InfoPill label="后台任务" value={taskHealthSummary(adminTasks)} />
          {adminTasks.length > 0 ? (
            <div className="settings-mini-list">
              {adminTasks.slice(0, 4).map((task) => (
                <div key={task.name} className="settings-mini-row">
                  <span>{task.name}</span>
                  <strong className={task.last_error ? "task-error" : task.running ? "task-running" : "task-ok"}>
                    {task.last_error ? "异常" : task.running ? "运行中" : task.last_success_at ? "正常" : "等待"}
                  </strong>
                </div>
              ))}
            </div>
          ) : null}
        </SettingCard>
      </div>
      <aside className="panel dark settings-snapshot">
        <PanelTitle title="运行快照" />
        <InfoPill label="数据库" value={runtime?.database_backend ?? "--"} />
        <InfoPill label="数据源" value={settings?.data_source || "--"} />
        <InfoPill label="AI 分析" value={runtime?.llm_configured ? "已配置" : "未配置"} />
        <InfoPill label="运行诊断" value={runtime?.ready_checks ? readySummary(runtime.ready_checks) : "--"} />
      </aside>
    </section>
  );
}

type SectionErrorMap = {
  adminTokenError: string;
  llmKeyError: string;
  llmBaseUrlError: string;
  dataSourceUrlError: string;
  singleLossError: string;
  dailyLossError: string;
  pauseLossError: string;
  minProfitError: string;
};

function sectionError(section: "llm" | "risk" | "data" | "factor", errors: SectionErrorMap): string {
  if (errors.adminTokenError) return errors.adminTokenError;
  if (section === "llm") return errors.llmKeyError || errors.llmBaseUrlError;
  if (section === "data") return errors.dataSourceUrlError;
  if (section === "risk") return errors.singleLossError || errors.dailyLossError || errors.pauseLossError || errors.minProfitError;
  return "";
}

function buildSettingsDirtyState(
  settings: SettingsPayload | null,
  factorWeights: FactorWeightsResponse | null,
  draft: SettingsDraft,
  factorDraft: Record<string, string>,
) {
  const llm = Boolean(
    draft.llm_api_key.trim() ||
    draft.llm_provider !== (settings?.llm_provider || "") ||
    draft.llm_base_url !== (settings?.llm_base_url || "") ||
    draft.llm_model !== (settings?.llm_model || "")
  );
  const data = Boolean(
    draft.data_source !== (settings?.data_source || "") ||
    draft.data_source_base_url !== (settings?.data_source_base_url || "")
  );
  const risk = Boolean(
    draft.risk_max_single_loss_pct !== String(settings?.risk_max_single_loss_pct ?? "") ||
    draft.risk_max_daily_loss_pct !== String(settings?.risk_max_daily_loss_pct ?? "") ||
    draft.risk_pause_after_losses !== String(settings?.risk_pause_after_losses ?? "") ||
    draft.strategy_min_profit_pct !== String(settings?.strategy_min_profit_pct ?? "")
  );
  const factor = Boolean(
    factorWeights &&
    Object.entries(factorDraft).some(([key, value]) => value !== String(factorWeights.weights[key] ?? ""))
  );
  return { llm, data, risk, factor };
}

function urlFieldError(value: string, label: string): string {
  const cleaned = value.trim();
  if (!cleaned) {
    return "";
  }
  try {
    const parsed = new URL(cleaned);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return `${label}必须是 http 或 https 地址`;
    }
  } catch {
    return `${label}格式不正确`;
  }
  return "";
}

function percentFieldError(value: string, label: string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return `${label}必须是非负数字`;
  }
  if (parsed > 100) {
    return `${label}不能超过 100%`;
  }
  return "";
}

function integerFieldError(value: string, label: string): string {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) {
    return `${label}必须是非负整数`;
  }
  return "";
}

function strategyGovernanceSummary(payload: LowBuyStrategyGovernanceResponse): string {
  const active = payload.items.filter((item) => item.status === "active").length;
  const watch = payload.items.filter((item) => item.status === "watch").length;
  const research = payload.items.filter((item) => item.layer === "research").length;
  return `生产 ${active} / 观察 ${watch} / 研究 ${research}`;
}

function taskHealthSummary(tasks: AdminTaskStatus[]): string {
  if (tasks.length === 0) {
    return "--";
  }
  const running = tasks.filter((task) => task.running).length;
  const errored = tasks.filter((task) => task.last_error).length;
  if (errored > 0) {
    return `${errored} 个异常`;
  }
  if (running > 0) {
    return `${running} 个运行中`;
  }
  return `${tasks.length} 个已接入`;
}
