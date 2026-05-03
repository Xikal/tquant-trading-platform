import type {
  AdminTaskStatus,
  FactorWeightsResponse,
  LowBuyStrategyGovernanceResponse,
  RuntimeStatus,
  SettingsPayload,
} from "../../types";
import { EditableGrid, InfoPill, PanelTitle, SettingCard } from "./WorkspaceComponents";
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
  onSave: (section: "llm" | "risk" | "data") => void;
  onSaveFactors: () => void;
  onRefresh: () => void;
}) {
  return (
    <section className="page-grid settings-grid">
      <div className="panel settings-hero">
        <PanelTitle title="开放式系统配置" actions={<button onClick={onRefresh} disabled={loading === "settings"}>刷新配置</button>} />
        <p className="hint">管理大模型、数据库、数据源、风险控制和策略阈值。敏感值只保存，不回显明文。</p>
      </div>
      <div className="settings-cards">
        <SettingCard title="大模型配置" button="保存大模型配置" onSave={() => onSave("llm")} loading={loading === "settings-llm"}>
          <EditableGrid
            fields={[
              ["管理令牌", draft.adminToken, (value) => setDraft({ ...draft, adminToken: value })],
              ["API Key", draft.llm_api_key, (value) => setDraft({ ...draft, llm_api_key: value })],
              ["Base URL", draft.llm_base_url, (value) => setDraft({ ...draft, llm_base_url: value })],
              ["模型名", draft.llm_model, (value) => setDraft({ ...draft, llm_model: value })],
            ]}
          />
          <label className="select-field">
            <span>供应商</span>
            <input value={draft.llm_provider} onChange={(event) => setDraft({ ...draft, llm_provider: event.target.value })} placeholder="openai / deepseek" />
          </label>
          <p className="hint">当前状态：{settings?.llm_api_key_configured ? "Key 已配置" : "Key 未配置"}</p>
        </SettingCard>
        <SettingCard title="数据库与数据源" button="保存数据配置" onSave={() => onSave("data")} loading={loading === "settings-data"}>
          <EditableGrid
            fields={[
              ["数据源", draft.data_source, (value) => setDraft({ ...draft, data_source: value })],
              ["数据源地址", draft.data_source_base_url, (value) => setDraft({ ...draft, data_source_base_url: value })],
            ]}
          />
          <InfoPill label="数据库" value={runtime?.database_url_masked ?? "--"} />
          <InfoPill label="接口前缀" value={runtime?.api_prefix ?? "/api"} />
        </SettingCard>
        <SettingCard title="风控参数" button="保存风控参数" onSave={() => onSave("risk")} loading={loading === "settings-risk"}>
          <EditableGrid
            fields={[
              ["单笔最大亏损%", draft.risk_max_single_loss_pct, (value) => setDraft({ ...draft, risk_max_single_loss_pct: value })],
              ["日内最大亏损%", draft.risk_max_daily_loss_pct, (value) => setDraft({ ...draft, risk_max_daily_loss_pct: value })],
              ["连亏暂停", draft.risk_pause_after_losses, (value) => setDraft({ ...draft, risk_pause_after_losses: value })],
              ["最小收益%", draft.strategy_min_profit_pct, (value) => setDraft({ ...draft, strategy_min_profit_pct: value })],
            ]}
          />
          <p className="hint">保存后会影响后续信号，不会修改已有复盘记录。</p>
        </SettingCard>
        <SettingCard title="因子权重" button="保存因子权重" onSave={onSaveFactors} loading={loading === "settings-factor"}>
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
              {strategyGovernance.items.slice(0, 6).map((item) => (
                <div key={item.strategy_key} className="settings-mini-row">
                  <span>{item.strategy_title}</span>
                  <strong className={`governance-status ${item.status}`}>
                    {item.strategy_health_score ? `${item.strategy_health_score} / ${item.status_text || item.status}` : item.status_text || item.status}
                  </strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="hint">策略治理未加载，刷新后会显示生产/研究/因子分层。</p>
          )}
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
