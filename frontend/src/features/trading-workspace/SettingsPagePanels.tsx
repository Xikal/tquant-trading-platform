import type {
  AdminTaskStatus,
  AdminMetricsResponse,
  LowBuyStrategyGovernanceResponse,
  RuntimeStatus,
  SettingsPayload,
  UserSectorExclusionsResponse,
} from "../../types";
import type { FeatureFlagAuditItem, FeatureFlagItem } from "../../api/featureFlags";
import type { OperationAuditItem } from "../../api/operationAudit";
import { TextField } from "../../components/shared/FormFields";
import { InfoPill, PanelTitle, SettingCard } from "./WorkspaceComponents";
import { readySummary } from "./workspaceFormatters";

export function SectorFilterCard({
  sectorExclusions,
  sectorDraft,
  sectorQuery,
  filteredSectors,
  sectorDirty,
  loading,
  saved,
  onSave,
  onClear,
  onQueryChange,
  onToggleSector,
}: {
  sectorExclusions: UserSectorExclusionsResponse | null;
  sectorDraft: string[];
  sectorQuery: string;
  filteredSectors: string[];
  sectorDirty: boolean;
  loading: string;
  saved: boolean;
  onSave: () => void;
  onClear: () => void;
  onQueryChange: (value: string) => void;
  onToggleSector: (sector: string) => void;
}) {
  return (
    <SettingCard
      title="板块过滤"
      button="保存板块过滤"
      onSave={onSave}
      loading={loading === "settings-sector-exclusions"}
      saved={saved}
      disabled={!sectorExclusions || !sectorDirty}
    >
      <p className="hint">选择不想参与的板块后，全策略榜单、选股宝典、App 选股和模拟盘自动买入都会过滤这些板块。已有持仓仍会保留风控监控。</p>
      <div className="sector-filter-summary">
        <InfoPill label="可选板块" value={sectorExclusions ? `${sectorExclusions.available_sectors.length} 个` : "--"} />
        <InfoPill label="已排除" value={`${sectorDraft.length} 个`} />
        <button type="button" onClick={onClear} disabled={!sectorDraft.length}>清空</button>
      </div>
      <TextField label="搜索板块" value={sectorQuery} placeholder="输入板块名称，例如 半导体、银行、医药" onChange={(event) => onQueryChange(event.target.value)} />
      <div className="sector-filter-list">
        {filteredSectors.length ? filteredSectors.map((sector) => (
          <label key={sector} className={sectorDraft.includes(sector) ? "sector-filter-option active" : "sector-filter-option"}>
            <input
              type="checkbox"
              checked={sectorDraft.includes(sector)}
              onChange={() => onToggleSector(sector)}
            />
            <span>{sector}</span>
          </label>
        )) : (
          <p className="hint">没有匹配的板块。请先同步标的库，或换一个关键词。</p>
        )}
      </div>
      {sectorDraft.length ? (
        <p className="hint">当前已排除：{sectorDraft.slice(0, 12).join("、")}{sectorDraft.length > 12 ? ` 等 ${sectorDraft.length} 个` : ""}</p>
      ) : (
        <p className="hint">当前未排除任何板块。</p>
      )}
    </SettingCard>
  );
}

export function StrategyGovernanceCard({
  strategyGovernance,
  loading,
  onRefresh,
  onUpdateStrategyGovernance,
}: {
  strategyGovernance: LowBuyStrategyGovernanceResponse | null;
  loading: string;
  onRefresh: () => void;
  onUpdateStrategyGovernance: (strategyKey: string, status: "active" | "watch" | "paused") => void;
}) {
  return (
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
  );
}

export function FeatureFlagsCard({
  featureFlags,
  featureFlagAudits,
  featureFlagError,
  loading,
  saved,
  onRefresh,
  onToggle,
}: {
  featureFlags: FeatureFlagItem[];
  featureFlagAudits: FeatureFlagAuditItem[];
  featureFlagError: string;
  loading: string;
  saved: boolean;
  onRefresh: () => void;
  onToggle: (item: FeatureFlagItem) => void;
}) {
  return (
    <SettingCard title="功能开关" button="刷新开关" onSave={onRefresh} loading={loading === "settings"} saved={saved}>
      {featureFlagError ? <p className="form-error">{featureFlagError}</p> : null}
      <div className="settings-mini-list">
        {featureFlags.length ? featureFlags.map((item) => (
          <div key={item.key} className="settings-mini-row">
            <span>
              {item.key}
              <small className="hint">{item.description || "无说明"}</small>
              <small className="hint">来源 {item.source || "--"}{item.updated_at ? ` / 更新 ${item.updated_at}` : ""}</small>
            </span>
            <strong className={item.enabled ? "task-ok" : "task-error"}>{item.enabled ? "开启" : "关闭"}</strong>
            <button type="button" onClick={() => onToggle(item)}>
              {item.enabled ? "关闭" : "开启"}
            </button>
          </div>
        )) : <p className="hint">功能开关未加载。</p>}
      </div>
      <p className="hint">普通用户可查看，只有管理员可以修改；修改会写入审计日志。</p>
      {featureFlagAudits.length ? (
        <div className="settings-mini-list feature-flag-audit-list">
          <strong>最近审计</strong>
          {featureFlagAudits.slice(0, 6).map((item) => (
            <div key={item.id} className="settings-mini-row">
              <span>
                {item.flag_key}
                <small className="hint">{item.created_at} / 用户 {item.operator_user_id ?? "--"} / {item.operator_ip || "--"}</small>
              </span>
              <strong>{item.old_value} → {item.new_value}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </SettingCard>
  );
}

export function RuntimeDiagnosticsCard({
  runtime,
  adminTasks,
  adminMetrics,
  loading,
  onRefresh,
}: {
  runtime: RuntimeStatus | null;
  adminTasks: AdminTaskStatus[];
  adminMetrics: AdminMetricsResponse | null;
  loading: string;
  onRefresh: () => void;
}) {
  const providerSummary = adminMetrics?.market_data_sources;
  const providerOkCount = providerSummary?.items.filter((item) => item.ok).length ?? 0;
  return (
    <SettingCard title="运行诊断" button="重新检测" onSave={onRefresh} loading={loading === "settings"}>
      <InfoPill label="前端产物" value={runtime?.frontend_dist_ready ? "正常" : "--"} />
      <InfoPill label="AI 分析" value={runtime?.llm_configured ? "已配置" : "未配置"} />
      <InfoPill label="环境文件" value={runtime?.runtime_env_exists ? "存在" : "--"} />
      <InfoPill label="数据库后端" value={runtime?.database_backend ?? "--"} />
      <InfoPill label="后台任务" value={taskHealthSummary(adminTasks)} />
      <InfoPill label="行情链路" value={providerSummary ? `${providerOkCount}/${providerSummary.items.length} 可用` : "--"} />
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
      {providerSummary?.items?.length ? (
        <div className="settings-mini-list">
          <strong>数据源健康</strong>
          {providerSummary.items.map((item) => (
            <div key={item.source} className="settings-mini-row">
              <span>
                {item.source}
                <small className="hint">{item.latency_ms}ms / {item.quality}{item.is_stale ? " / stale" : ""}</small>
                {item.warning ? <small className="hint">{item.warning}</small> : null}
              </span>
              <strong className={item.ok ? "task-ok" : "task-error"}>{item.ok ? "可用" : "失败"}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </SettingCard>
  );
}

export function OperationAuditCard({
  items,
  error,
  loading,
  onRefresh,
}: {
  items: OperationAuditItem[];
  error: string;
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <SettingCard title="操作审计" button="刷新审计" onSave={onRefresh} loading={loading}>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="settings-mini-list">
        {items.length ? items.slice(0, 8).map((item) => (
          <div key={item.id} className="settings-mini-row">
            <span>
              {item.operation}
              <small className="hint">{item.resource_type || "--"} / {item.created_at}</small>
            </span>
            <strong className={item.status === "ok" ? "task-ok" : "task-error"}>{item.status}</strong>
          </div>
        )) : <p className="hint">暂无审计记录，只有管理员可查看。</p>}
      </div>
    </SettingCard>
  );
}

export function RuntimeSnapshotPanel({
  settings,
  runtime,
}: {
  settings: SettingsPayload | null;
  runtime: RuntimeStatus | null;
}) {
  return (
    <aside className="panel dark settings-snapshot">
      <PanelTitle title="运行快照" />
      <InfoPill label="数据库" value={runtime?.database_backend ?? "--"} />
      <InfoPill label="数据源" value={settings?.data_source || "--"} />
      <InfoPill label="AI 分析" value={runtime?.llm_configured ? "已配置" : "未配置"} />
      <InfoPill label="运行诊断" value={runtime?.ready_checks ? readySummary(runtime.ready_checks) : "--"} />
    </aside>
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
