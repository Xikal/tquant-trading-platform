import type { CSSProperties } from "react";
import type {
  AdminTaskStatus,
  AdminMetricsResponse,
  AuthUser,
  FactorWeightsResponse,
  LowBuyStrategyGovernanceResponse,
  RuntimeStatus,
  SettingsPayload,
  UserSectorExclusionsResponse,
} from "../../types";
import { useEffect, useMemo, useRef } from "react";
import { Button } from "antd";
import { featureFlagsApi, type FeatureFlagItem } from "../../api/featureFlags";
import { operationAuditApi } from "../../api/operationAudit";
import { NumberField, TextField } from "../../components/shared/FormFields";
import { AuthSecurityCard } from "./AuthSecurityCard";
import { InfoPill, PanelTitle, SettingCard } from "../workspace-shared/WorkspaceComponents";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import {
  FeatureFlagsCard,
  OperationAuditCard,
  RuntimeDiagnosticsCard,
  RuntimeSnapshotPanel,
  SectorFilterCard,
  StrategyGovernanceCard,
} from "./SettingsPagePanels";
import { SettingsPageTabs, type SettingsTabItem, type SettingsTabKey } from "./SettingsPageTabs";
import { SettingsSection } from "./SettingsSection";
import { FactorWeightSettingsCard } from "./FactorWeightSettingsCard";
import { LatestDataStatusCard } from "./LatestDataStatusCard";
import { QuantParameterMlCard } from "./QuantParameterMlCard";
import { QuantParameterPaperExitCard } from "./QuantParameterPaperExitCard";
import { QuantParameterSectorEtfCard } from "./QuantParameterSectorEtfCard";
import { EtfUniverseAdminCard } from "./EtfUniverseAdminCard";
import { useSettingsUiStore } from "../../stores/settingsUiStore";
import {
  buildSettingsDirtyState,
  integerFieldError,
  percentFieldError,
  sameStringSet,
  sectionError,
  type SettingsSectionKey,
  urlFieldError,
} from "./SettingsPage.helpers";
import type { SettingsDraft } from "../workspace-shared/workspaceTypes";

const SETTINGS_PAGE_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  gridTemplateColumns: "minmax(0, 1fr)",
  gridTemplateAreas: '"hero" "tabs" "cards"',
};

const SETTINGS_HERO_STYLE: CSSProperties = { gridArea: "hero" };
const SETTINGS_TABS_STYLE: CSSProperties = { gridArea: "tabs" };
const SETTINGS_CARDS_STYLE: CSSProperties = {
  display: "grid",
  alignItems: "start",
  gap: 14,
  gridArea: "cards",
  gridTemplateColumns: "minmax(0, 1fr)",
};
const SETTINGS_FORM_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};
const SETTINGS_FORM_GRID_COMPACT_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
};
const SETTINGS_UNSAVED_BANNER_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  marginTop: 10,
  padding: "8px 10px",
  border: "1px solid #f3d08b",
  borderRadius: 10,
  background: "#fff8e6",
  color: "#7c4a03",
  fontSize: 12,
  fontWeight: 800,
};

export function SettingsPage({
  settings,
  runtime,
  factorWeights,
  adminTasks,
  adminMetrics,
  strategyGovernance,
  sectorExclusions,
  factorDraft,
  draft,
  setDraft,
  setFactorDraft,
  loading,
  onSave,
  onSaveFactors,
  onRefresh,
  onRefreshLatestData,
  onUpdateStrategyGovernance,
  onSaveSectorExclusions,
  currentUser,
  onUserUpdate,
}: {
  settings: SettingsPayload | null;
  runtime: RuntimeStatus | null;
  factorWeights: FactorWeightsResponse | null;
  adminTasks: AdminTaskStatus[];
  adminMetrics: AdminMetricsResponse | null;
  strategyGovernance: LowBuyStrategyGovernanceResponse | null;
  sectorExclusions: UserSectorExclusionsResponse | null;
  factorDraft: Record<string, string>;
  draft: SettingsDraft;
  setDraft: (draft: SettingsDraft) => void;
  setFactorDraft: (draft: Record<string, string>) => void;
  loading: string;
  onSave: (section: "llm" | "risk" | "data") => void | Promise<void>;
  onSaveFactors: () => void | Promise<void>;
  onRefresh: () => void;
  onRefreshLatestData: () => void | Promise<void>;
  onUpdateStrategyGovernance: (strategyKey: string, status: "active" | "watch" | "paused") => void;
  onSaveSectorExclusions: (excludedSectors: string[]) => void | Promise<void>;
  currentUser: AuthUser;
  onUserUpdate: (user: AuthUser) => void;
}) {
  const sectorQuery = useSettingsUiStore((state) => state.sectorQuery);
  const activeTab = useSettingsUiStore((state) => state.activeTab);
  const savedSection = useSettingsUiStore((state) => state.savedSection);
  const sectorDraft = useSettingsUiStore((state) => state.sectorDraft);
  const featureFlags = useSettingsUiStore((state) => state.featureFlags);
  const featureFlagAudits = useSettingsUiStore((state) => state.featureFlagAudits);
  const featureFlagError = useSettingsUiStore((state) => state.featureFlagError);
  const operationAudits = useSettingsUiStore((state) => state.operationAudits);
  const operationAuditError = useSettingsUiStore((state) => state.operationAuditError);
  const operationAuditLoading = useSettingsUiStore((state) => state.operationAuditLoading);
  const setSectorQuery = useSettingsUiStore((state) => state.setSectorQuery);
  const setActiveTab = useSettingsUiStore((state) => state.setActiveTab);
  const setSavedSection = useSettingsUiStore((state) => state.setSavedSection);
  const setSectorDraft = useSettingsUiStore((state) => state.setSectorDraft);
  const setFeatureFlags = useSettingsUiStore((state) => state.setFeatureFlags);
  const setFeatureFlagAudits = useSettingsUiStore((state) => state.setFeatureFlagAudits);
  const setFeatureFlagError = useSettingsUiStore((state) => state.setFeatureFlagError);
  const setOperationAudits = useSettingsUiStore((state) => state.setOperationAudits);
  const setOperationAuditError = useSettingsUiStore((state) => state.setOperationAuditError);
  const setOperationAuditLoading = useSettingsUiStore((state) => state.setOperationAuditLoading);
  const savedTimerRef = useRef<number | null>(null);
  const adminTokenError = draft.adminToken.trim() ? "" : "保存配置前需要填写管理令牌";
  const llmKeyError = !settings?.llm_api_key_configured && !draft.llm_api_key.trim() ? "首次配置大模型需要填写 API Key" : "";
  const llmBaseUrlError = urlFieldError(draft.llm_base_url, "模型接口地址");
  const dataSourceUrlError = urlFieldError(draft.data_source_base_url, "数据源地址");
  const singleLossError = percentFieldError(draft.risk_max_single_loss_pct, "单笔最大亏损");
  const dailyLossError = percentFieldError(draft.risk_max_daily_loss_pct, "日内最大亏损");
  const pauseLossError = integerFieldError(draft.risk_pause_after_losses, "连亏暂停");
  const minProfitError = percentFieldError(draft.strategy_min_profit_pct, "最小收益");
  const isAdmin = useMemo(() => currentUser.roles.some((role) => {
    const normalized = role.trim().toLowerCase();
    return normalized === "admin" || normalized === "administrator";
  }), [currentUser.roles]);
  const dirtyState = useMemo(() => buildSettingsDirtyState(settings, factorWeights, draft, factorDraft), [draft, factorDraft, factorWeights, settings]);
  const sectorDirty = useMemo(() => !sameStringSet(sectorDraft, sectorExclusions?.excluded_sectors ?? []), [sectorDraft, sectorExclusions]);
  const visibleDirtyCount = Number(dirtyState.risk) + (isAdmin ? Number(dirtyState.llm) + Number(dirtyState.data) + Number(dirtyState.factor) : 0);
  const unsavedCount = visibleDirtyCount + (sectorDirty ? 1 : 0);
  const filteredSectors = useMemo(() => {
    const query = sectorQuery.trim().toLowerCase();
    const sectors = sectorExclusions?.available_sectors ?? [];
    if (!query) return sectors;
    return sectors.filter((sector) => sector.toLowerCase().includes(query));
  }, [sectorExclusions, sectorQuery]);
  const settingsTabs = useMemo<SettingsTabItem[]>(() => {
    const baseTabs: SettingsTabItem[] = [
      { key: "account", label: "我的账户", description: "安全与权限" },
      { key: "trading", label: "交易参数", description: "风控、行业、退出", dirty: dirtyState.risk || sectorDirty },
    ];
    if (!isAdmin) {
      return baseTabs;
    }
    return [
      ...baseTabs,
      { key: "llm", label: "大模型与因子", description: "DeepSeek、权重、ML", dirty: dirtyState.llm || dirtyState.factor },
      { key: "data", label: "数据库与诊断", description: "数据源、运行状态", dirty: dirtyState.data },
      { key: "governance", label: "策略治理", description: "开关、审计、治理" },
    ];
  }, [dirtyState.data, dirtyState.factor, dirtyState.llm, dirtyState.risk, isAdmin, sectorDirty]);

  useEffect(() => {
    if (!settingsTabs.some((tab) => tab.key === activeTab)) {
      setActiveTab(settingsTabs[0]?.key ?? "account");
    }
  }, [activeTab, settingsTabs]);

  async function saveSection(section: SettingsSectionKey) {
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
    const sections: SettingsSectionKey[] = [];
    if (isAdmin && dirtyState.llm) sections.push("llm");
    if (isAdmin && dirtyState.data) sections.push("data");
    if (dirtyState.risk) sections.push("risk");
    if (isAdmin && dirtyState.factor) sections.push("factor");
    for (const section of sections) {
      await saveSection(section);
    }
    if (sectorDirty) {
      await saveSectorExclusions();
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
    if (!isAdmin) {
      setFeatureFlags([]);
      setFeatureFlagAudits([]);
      setOperationAudits([]);
      return;
    }
    let cancelled = false;
    loadFeatureFlags({ includeAudit: true, cancelled: () => cancelled });
    loadOperationAudits({ cancelled: () => cancelled });
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  useEffect(() => {
    setSectorDraft(sectorExclusions?.excluded_sectors ?? []);
  }, [sectorExclusions]);

  async function loadFeatureFlags(options: { includeAudit?: boolean; cancelled?: () => boolean } = {}) {
    try {
      const payload = await featureFlagsApi.list();
      if (options.cancelled?.()) return;
      setFeatureFlags(payload.items ?? []);
      setFeatureFlagError("");
      if (options.includeAudit) {
        try {
          const auditPayload = await featureFlagsApi.audit();
          if (!options.cancelled?.()) {
            setFeatureFlagAudits(auditPayload.items ?? []);
          }
        } catch {
          if (!options.cancelled?.()) {
            setFeatureFlagAudits([]);
          }
        }
      }
    } catch (error) {
      if (!options.cancelled?.()) {
        setFeatureFlagError(error instanceof Error ? error.message : "功能开关加载失败");
      }
    }
  }

  async function toggleFeatureFlag(item: FeatureFlagItem) {
    try {
      const updated = await featureFlagsApi.update(item.key, !item.enabled);
      setFeatureFlags((current) => current.map((flag) => flag.key === item.key ? updated.item : flag));
      featureFlagsApi.audit()
        .then((payload) => setFeatureFlagAudits(payload.items ?? []))
        .catch(() => setFeatureFlagAudits([]));
      markSaved("feature-flags");
      setFeatureFlagError("");
    } catch (error) {
      setFeatureFlagError(error instanceof Error ? error.message : "功能开关更新失败");
    }
  }

  async function loadOperationAudits(options: { cancelled?: () => boolean } = {}) {
    setOperationAuditLoading(true);
    try {
      const payload = await operationAuditApi.list(20);
      if (!options.cancelled?.()) {
        setOperationAudits(payload.items ?? []);
        setOperationAuditError("");
      }
    } catch (error) {
      if (!options.cancelled?.()) {
        setOperationAudits([]);
        setOperationAuditError(error instanceof Error ? error.message : "操作审计加载失败");
      }
    } finally {
      if (!options.cancelled?.()) {
        setOperationAuditLoading(false);
      }
    }
  }

  async function saveSectorExclusions() {
    await Promise.resolve(onSaveSectorExclusions(sectorDraft));
    markSaved("sector-exclusions");
  }

  function toggleSector(sector: string) {
    setSectorDraft((current) => current.includes(sector)
      ? current.filter((item) => item !== sector)
      : [...current, sector].sort((a, b) => a.localeCompare(b, "zh-Hans-CN"))
    );
  }

  return (
    <section style={SETTINGS_PAGE_STYLE}>
      <div className="panel" style={SETTINGS_HERO_STYLE}>
        <WorkspacePageIntro
          title="系统设置"
          summary={runtime?.settings_consistency_text || "账户安全、风控参数、数据源、策略治理。"}
          more="配置保存采用一致性语义；敏感字段只显示配置状态，不回显真实值。"
          moreLabel="保存规则"
          tone={unsavedCount > 0 ? "warn" : runtime?.settings_consistency_status === "ok" ? "up" : "neutral"}
          actions={<Button onClick={onRefresh} loading={loading === "settings"}>刷新配置</Button>}
          pills={[
            { label: "当前页签", value: settingsTabs.find((tab) => tab.key === activeTab)?.label || "--" },
            { label: "未保存", value: String(unsavedCount), tone: unsavedCount > 0 ? "warn" : "neutral" },
            { label: "数据库", value: runtime?.database_backend || "--" },
            { label: "大模型", value: runtime?.llm_configured ? "已配置" : "未配置", tone: runtime?.llm_configured ? "up" : "neutral" },
          ]}
        />
        {unsavedCount > 0 ? (
          <div style={SETTINGS_UNSAVED_BANNER_STYLE}>
            <span>有 {unsavedCount} 项未保存的更改</span>
            <Button type="primary" size="small" htmlType="button" onClick={() => void saveAllDirty()} disabled={Boolean(loading)}>
              全部保存
            </Button>
          </div>
        ) : null}
      </div>
      <div style={SETTINGS_TABS_STYLE}>
        <SettingsPageTabs tabs={settingsTabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>
      <div style={SETTINGS_CARDS_STYLE}>
        {activeTab === "account" ? (
          <SettingsSection title="我的账户" description="安全 / 权限">
            <AuthSecurityCard currentUser={currentUser} onUserUpdate={onUserUpdate} />
          </SettingsSection>
        ) : null}

        {activeTab === "trading" ? (
        <SettingsSection title="交易参数" description="风控 / 行业 / 退出">
            <SettingCard className="risk-params-card" title="风控参数" button="保存风控参数" onSave={() => void saveSection("risk")} loading={loading === "settings-risk"} saved={savedSection === "risk"} disabled={Boolean(adminTokenError || singleLossError || dailyLossError || pauseLossError || minProfitError)}>
              <div style={SETTINGS_FORM_GRID_STYLE}>
                <NumberField label="单笔最大亏损" suffix="%" value={draft.risk_max_single_loss_pct} error={singleLossError} onChange={(event) => setDraft({ ...draft, risk_max_single_loss_pct: event.target.value })} />
                <NumberField label="日内最大亏损" suffix="%" value={draft.risk_max_daily_loss_pct} error={dailyLossError} onChange={(event) => setDraft({ ...draft, risk_max_daily_loss_pct: event.target.value })} />
                <NumberField label="连亏暂停" value={draft.risk_pause_after_losses} error={pauseLossError} onChange={(event) => setDraft({ ...draft, risk_pause_after_losses: event.target.value })} />
                <NumberField label="最小收益" suffix="%" value={draft.strategy_min_profit_pct} error={minProfitError} onChange={(event) => setDraft({ ...draft, strategy_min_profit_pct: event.target.value })} />
              </div>
            <p className="hint">{adminTokenError || "保存后会影响后续信号，不会修改已有复盘记录。"}</p>
          </SettingCard>
          <SectorFilterCard
            sectorExclusions={sectorExclusions}
            sectorDraft={sectorDraft}
            sectorQuery={sectorQuery}
            filteredSectors={filteredSectors}
            sectorDirty={sectorDirty}
            loading={loading}
            saved={savedSection === "sector-exclusions"}
            onSave={() => void saveSectorExclusions()}
            onClear={() => setSectorDraft([])}
            onQueryChange={setSectorQuery}
            onToggleSector={toggleSector}
          />
          <QuantParameterPaperExitCard adminTokenError={adminTokenError} />
          <QuantParameterSectorEtfCard adminTokenError={adminTokenError} />
          {isAdmin ? <EtfUniverseAdminCard /> : null}
        </SettingsSection>
        ) : null}

        {isAdmin && activeTab === "llm" ? (
          <SettingsSection title="大模型与因子" description="LLM / 因子 / ML" admin>
            <SettingCard className="llm-config-card" title="大模型配置" button="保存大模型配置" onSave={() => void saveSection("llm")} loading={loading === "settings-llm"} saved={savedSection === "llm"} disabled={Boolean(adminTokenError || llmKeyError || llmBaseUrlError)}>
              <div style={SETTINGS_FORM_GRID_STYLE}>
                <TextField label="管理令牌" value={draft.adminToken} error={adminTokenError} onChange={(event) => setDraft({ ...draft, adminToken: event.target.value })} />
                <TextField label="API Key" value={draft.llm_api_key} error={llmKeyError} onChange={(event) => setDraft({ ...draft, llm_api_key: event.target.value })} />
                <TextField label="Base URL" value={draft.llm_base_url} error={llmBaseUrlError} onChange={(event) => setDraft({ ...draft, llm_base_url: event.target.value })} />
                <TextField label="模型名" value={draft.llm_model} onChange={(event) => setDraft({ ...draft, llm_model: event.target.value })} />
                <TextField label="供应商" value={draft.llm_provider} placeholder="openai / deepseek" onChange={(event) => setDraft({ ...draft, llm_provider: event.target.value })} />
              </div>
              <p className="hint">当前状态：{settings?.llm_api_key_configured ? "Key 已配置" : "Key 未配置"}</p>
            </SettingCard>
            <FactorWeightSettingsCard
              factorWeights={factorWeights}
              factorDraft={factorDraft}
              loading={loading === "settings-factor"}
              saved={savedSection === "factor"}
              disabled={Boolean(adminTokenError)}
              onSave={() => void saveSection("factor")}
              onDraftChange={setFactorDraft}
            />
            <QuantParameterMlCard adminTokenError={adminTokenError} />
          </SettingsSection>
        ) : null}

        {isAdmin && activeTab === "data" ? (
          <SettingsSection title="数据库与诊断" description="数据源 / 任务 / 快照" admin>
            <SettingCard title="数据库与数据源" button="保存数据配置" onSave={() => void saveSection("data")} loading={loading === "settings-data"} saved={savedSection === "data"} disabled={Boolean(adminTokenError || dataSourceUrlError)}>
              <div style={SETTINGS_FORM_GRID_COMPACT_STYLE}>
                <TextField label="数据源" value={draft.data_source} hint={adminTokenError || "保存数据源配置同样需要管理令牌。"} onChange={(event) => setDraft({ ...draft, data_source: event.target.value })} />
                <TextField label="数据源地址" value={draft.data_source_base_url} error={dataSourceUrlError} onChange={(event) => setDraft({ ...draft, data_source_base_url: event.target.value })} />
              </div>
              <InfoPill label="数据库" value={runtime?.database_url_masked ?? "--"} />
              <InfoPill label="接口前缀" value={runtime?.api_prefix ?? "/api"} />
            </SettingCard>
            <LatestDataStatusCard
              status={adminMetrics?.latest_low_buy_data ?? null}
              loading={loading === "latest-data-refresh"}
              adminTokenError={adminTokenError}
              onRefresh={onRefreshLatestData}
            />
            <RuntimeDiagnosticsCard runtime={runtime} adminTasks={adminTasks} adminMetrics={adminMetrics} loading={loading} onRefresh={onRefresh} />
            <RuntimeSnapshotPanel settings={settings} runtime={runtime} />
          </SettingsSection>
        ) : null}

        {isAdmin && activeTab === "governance" ? (
          <SettingsSection title="策略治理" description="状态 / 开关 / 审计" admin>
            <StrategyGovernanceCard strategyGovernance={strategyGovernance} loading={loading} onRefresh={onRefresh} onUpdateStrategyGovernance={onUpdateStrategyGovernance} />
            <FeatureFlagsCard featureFlags={featureFlags} featureFlagAudits={featureFlagAudits} featureFlagError={featureFlagError} loading={loading} saved={savedSection === "feature-flags"} onRefresh={() => void loadFeatureFlags({ includeAudit: true })} onToggle={(item) => void toggleFeatureFlag(item)} />
            <OperationAuditCard items={operationAudits} error={operationAuditError} loading={operationAuditLoading} onRefresh={() => void loadOperationAudits()} />
          </SettingsSection>
        ) : null}
      </div>
    </section>
  );
}
