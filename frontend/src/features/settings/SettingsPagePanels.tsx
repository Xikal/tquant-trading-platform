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
import type { CSSProperties } from "react";
import { Button, Checkbox, Space, Switch, Tag } from "antd";
import { TextField } from "../../components/shared/FormFields";
import { InfoPill, PanelTitle, SettingCard } from "../workspace-shared/WorkspaceComponents";
import { readySummary } from "../workspace-shared/workspaceFormatters";
import { DataTable } from "../../ui/table/DataTable";

const SECTOR_FILTER_SUMMARY_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: 8,
};

const SECTOR_FILTER_LIST_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: 6,
  maxHeight: 240,
  overflow: "auto",
  padding: 6,
  border: "1px solid var(--line)",
  borderRadius: 10,
  background: "#f8fafc",
};

const SECTOR_FILTER_OPTION_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "flex-start",
  gap: 6,
  minWidth: 0,
  minHeight: 32,
  padding: "6px 8px",
  border: "1px solid transparent",
  borderRadius: 8,
  color: "var(--text)",
  fontSize: 11,
  fontWeight: 800,
  cursor: "pointer",
};

const SECTOR_FILTER_OPTION_ACTIVE_STYLE: CSSProperties = {
  borderColor: "#f59e0b",
  color: "#92400e",
  background: "#fffbeb",
};

const RUNTIME_SNAPSHOT_PANEL_STYLE: CSSProperties = {
  borderColor: "rgba(255, 255, 255, 0.1)",
  background: "linear-gradient(180deg, var(--panel), var(--deep))",
  color: "#dde3ec",
};

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
      className="sector-filter-card"
      onSave={onSave}
      loading={loading === "settings-sector-exclusions"}
      saved={saved}
      disabled={!sectorExclusions || !sectorDirty}
    >
      <p className="hint">选择不想参与的板块后，生产优先榜、选股宝典、App 选股和模拟盘自动买入都会过滤这些板块。已有持仓仍会保留风控监控。</p>
      <div style={SECTOR_FILTER_SUMMARY_STYLE}>
        <InfoPill label="可选板块" value={sectorExclusions ? `${sectorExclusions.available_sectors.length} 个` : "--"} />
        <InfoPill label="已排除" value={`${sectorDraft.length} 个`} />
        <Button size="small" htmlType="button" onClick={onClear} disabled={!sectorDraft.length}>清空</Button>
      </div>
      <TextField label="搜索板块" value={sectorQuery} placeholder="输入板块名称，例如 半导体、银行、医药" onChange={(event) => onQueryChange(event.target.value)} />
      <div style={SECTOR_FILTER_LIST_STYLE}>
        {filteredSectors.length ? filteredSectors.map((sector) => (
          <Checkbox
            key={sector}
            style={sectorDraft.includes(sector) ? { ...SECTOR_FILTER_OPTION_STYLE, ...SECTOR_FILTER_OPTION_ACTIVE_STYLE } : SECTOR_FILTER_OPTION_STYLE}
            checked={sectorDraft.includes(sector)}
            onChange={() => onToggleSector(sector)}
          >
            {sector}
          </Checkbox>
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
    <SettingCard
      title="策略治理"
      button="刷新策略状态"
      onSave={onRefresh}
      loading={loading === "settings"}
      className="strategy-governance-card"
    >
      <InfoPill label="默认策略" value={strategyGovernance?.default_strategy ?? "--"} />
      <InfoPill label="生产策略" value={strategyGovernance ? `${strategyGovernance.production_strategies.length} 个` : "--"} />
      <InfoPill label="治理状态" value={strategyGovernance ? strategyGovernanceSummary(strategyGovernance) : "--"} />
      {strategyGovernance ? (
        <DataTable
          rowKey="strategy_key"
          dataSource={strategyGovernance.items}
          columns={[
            {
              title: "策略",
              dataIndex: "strategy_title",
              render: (value, item) => (
                <span>
                  <strong>{value}</strong>
                  <small className="hint">{item.strategy_key}</small>
                </span>
              ),
            },
            {
              title: "状态",
              dataIndex: "status",
              width: 150,
              render: (_, item) => (
                <Tag color={governanceStatusColor(item.status)}>
                  {item.strategy_health_score ? `${item.strategy_health_score} / ${item.status_text || item.status}` : item.status_text || item.status}
                </Tag>
              ),
            },
            {
              title: "原因",
              dataIndex: "auto_governance_reason",
              render: (value) => value || "--",
            },
            {
              title: "操作",
              width: 170,
              render: (_, item) => (
                <Space size={4} wrap>
                  <Button size="small" htmlType="button" onClick={() => onUpdateStrategyGovernance(item.strategy_key, "active")} disabled={loading === "settings"}>恢复</Button>
                  <Button size="small" htmlType="button" onClick={() => onUpdateStrategyGovernance(item.strategy_key, "watch")} disabled={loading === "settings"}>观察</Button>
                  <Button size="small" danger htmlType="button" onClick={() => onUpdateStrategyGovernance(item.strategy_key, "paused")} disabled={loading === "settings"}>暂停</Button>
                </Space>
              ),
            },
          ]}
        />
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
    <SettingCard
      title="功能开关"
      button="刷新开关"
      onSave={onRefresh}
      loading={loading === "settings"}
      saved={saved}
      className="feature-flags-card"
    >
      {featureFlagError ? <p className="form-error">{featureFlagError}</p> : null}
      <DataTable
        rowKey="key"
        dataSource={featureFlags}
        locale={{ emptyText: "功能开关未加载" }}
        columns={[
          {
            title: "开关",
            dataIndex: "key",
            render: (value, item) => (
              <span>
                <strong>{value}</strong>
                <small className="hint">{item.description || "无说明"}</small>
                <small className="hint">来源 {item.source || "--"}{item.updated_at ? ` / 更新 ${item.updated_at}` : ""}</small>
              </span>
            ),
          },
          {
            title: "状态",
            width: 90,
            render: (_, item) => <Tag color={item.enabled ? "green" : "red"}>{item.enabled ? "开启" : "关闭"}</Tag>,
          },
          {
            title: "操作",
            width: 90,
            render: (_, item) => <Switch checked={item.enabled} checkedChildren="开" unCheckedChildren="关" onChange={() => onToggle(item)} />,
          },
        ]}
      />
      <p className="hint">普通用户可查看，只有管理员可以修改；修改会写入审计日志。</p>
      {featureFlagAudits.length ? (
        <DataTable
          rowKey="id"
          dataSource={featureFlagAudits}
          columns={[
            {
              title: "最近审计",
              dataIndex: "flag_key",
              render: (value, item) => (
                <span>
                  <strong>{value}</strong>
                  <small className="hint">{item.created_at} / 用户 {item.operator_user_id ?? "--"} / {item.operator_ip || "--"}</small>
                </span>
              ),
            },
            {
              title: "变化",
              width: 160,
              render: (_, item) => `${item.old_value} → ${item.new_value}`,
            },
          ]}
        />
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
    <SettingCard
      title="运行诊断"
      button="重新检测"
      onSave={onRefresh}
      loading={loading === "settings"}
      className="runtime-diagnostics-card"
    >
      <InfoPill label="前端产物" value={runtime?.frontend_dist_ready ? "正常" : "--"} />
      <InfoPill label="AI 分析" value={runtime?.llm_configured ? "已配置" : "未配置"} />
      <InfoPill label="环境文件" value={runtime?.runtime_env_exists ? "存在" : "--"} />
      <InfoPill label="数据库后端" value={runtime?.database_backend ?? "--"} />
      <InfoPill label="配置一致性" value={runtime?.settings_consistency_text ?? "--"} />
      <InfoPill label="敏感字段" value={runtime?.runtime_llm_secret_persisted ? "需清理" : "未明文持久化"} />
      <InfoPill label="后台任务" value={taskHealthSummary(adminTasks)} />
      <InfoPill label="行情链路" value={providerSummary ? `${providerOkCount}/${providerSummary.items.length} 可用` : "--"} />
      {adminTasks.length > 0 ? (
        <DataTable
          rowKey="name"
          dataSource={adminTasks}
          columns={[
            { title: "后台任务", dataIndex: "name" },
            {
              title: "状态",
              width: 100,
              render: (_, task) => (
                <Tag color={task.last_error ? "red" : task.running ? "blue" : "green"}>
                  {task.last_error ? "异常" : task.running ? "运行中" : task.last_success_at ? "正常" : "等待"}
                </Tag>
              ),
            },
          ]}
        />
      ) : null}
      {providerSummary?.items?.length ? (
        <DataTable
          rowKey="source"
          dataSource={providerSummary.items}
          columns={[
            {
              title: "数据源健康",
              dataIndex: "source",
              render: (value, item) => (
                <span>
                  <strong>{value}</strong>
                  <small className="hint">{item.latency_ms}ms / {item.quality}{item.is_stale ? " / stale" : ""}</small>
                  {item.warning ? <small className="hint">{item.warning}</small> : null}
                </span>
              ),
            },
            {
              title: "状态",
              width: 90,
              render: (_, item) => <Tag color={item.ok ? "green" : "red"}>{item.ok ? "可用" : "失败"}</Tag>,
            },
          ]}
        />
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
      <DataTable
        rowKey="id"
        dataSource={items}
        locale={{ emptyText: "暂无审计记录，只有管理员可查看" }}
        columns={[
          {
            title: "操作",
            dataIndex: "operation",
            render: (value, item) => (
              <span>
                <strong>{value}</strong>
                <small className="hint">{item.resource_type || "--"} / {item.created_at}</small>
              </span>
            ),
          },
          {
            title: "状态",
            width: 90,
            render: (_, item) => <Tag color={item.status === "ok" ? "green" : "red"}>{item.status}</Tag>,
          },
        ]}
      />
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
    <aside className="panel" style={RUNTIME_SNAPSHOT_PANEL_STYLE}>
      <PanelTitle title="运行快照" />
      <InfoPill label="数据库" value={runtime?.database_backend ?? "--"} />
      <InfoPill label="数据源" value={settings?.data_source || "--"} />
      <InfoPill label="AI 分析" value={runtime?.llm_configured ? "已配置" : "未配置"} />
      <InfoPill label="运行诊断" value={runtime?.ready_checks ? readySummary(runtime.ready_checks) : "--"} />
      <InfoPill label="配置一致性" value={runtime?.settings_consistency_status ?? "--"} />
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

function governanceStatusColor(status: string): string {
  if (status === "active") return "green";
  if (status === "watch") return "gold";
  if (status === "paused" || status === "deprecated") return "red";
  return "default";
}
