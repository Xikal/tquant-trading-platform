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
import { featureFlagsApi, type FeatureFlagItem } from "../../api/featureFlags";
import { operationAuditApi, type OperationAuditItem } from "../../api/operationAudit";
import { NumberField, TextField } from "../../components/shared/FormFields";
import { AuthSecurityCard } from "./AuthSecurityCard";
import { InfoPill, SettingCard } from "../workspace-shared/WorkspaceComponents";
import {
  FeatureFlagsCard,
  OperationAuditCard,
  RuntimeDiagnosticsCard,
  RuntimeSnapshotPanel,
  SectorFilterCard,
  StrategyGovernanceCard,
} from "./SettingsPagePanels";
import type { SettingsTabItem } from "./SettingsPageTabs";
import { SettingsSection } from "./SettingsSection";
import { AdminTokenGate } from "./AdminTokenGate";
import { DataCenterEntryCard } from "./DataCenterEntryCard";
import { FactorWeightSettingsCard } from "./FactorWeightSettingsCard";
import { LatestDataStatusCard } from "./LatestDataStatusCard";
import { QuantParameterMlCard } from "./QuantParameterMlCard";
import { RitualSettingsCard } from "../ritual-ui";
import { useSettingsUiStore } from "../../stores/settingsUiStore";
import { useServerState } from "../../state/serverState";
import {
  buildSettingsDirtyState,
  integerFieldError,
  percentFieldError,
  sectionError,
  type SettingsSectionKey,
  urlFieldError,
} from "./SettingsPage.helpers";
import { buildSettingsPageViewModel } from "./SettingsPage.viewModel";
import type { SettingsDraft } from "../workspace-shared/workspaceTypes";
import { SettingsLayout } from "./SettingsLayout";
import styles from "./SettingsLayout.module.css";

const SETTINGS_PAGE_SERVER_KEYS = {
  featureFlags: ["settings-page", "feature-flags"] as const,
  featureFlagAudits: ["settings-page", "feature-flag-audits"] as const,
  operationAudits: ["settings-page", "operation-audits"] as const,
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
  const [featureFlags, setFeatureFlags] = useServerState<FeatureFlagItem[]>(SETTINGS_PAGE_SERVER_KEYS.featureFlags, []);
  const [featureFlagAudits, setFeatureFlagAudits] = useServerState<Awaited<ReturnType<typeof featureFlagsApi.audit>>["items"]>(
    SETTINGS_PAGE_SERVER_KEYS.featureFlagAudits,
    [],
  );
  const featureFlagError = useSettingsUiStore((state) => state.featureFlagError);
  const [operationAudits, setOperationAudits] = useServerState<OperationAuditItem[]>(SETTINGS_PAGE_SERVER_KEYS.operationAudits, []);
  const operationAuditError = useSettingsUiStore((state) => state.operationAuditError);
  const operationAuditLoading = useSettingsUiStore((state) => state.operationAuditLoading);
  const setSectorQuery = useSettingsUiStore((state) => state.setSectorQuery);
  const setActiveTab = useSettingsUiStore((state) => state.setActiveTab);
  const setSavedSection = useSettingsUiStore((state) => state.setSavedSection);
  const setSectorDraft = useSettingsUiStore((state) => state.setSectorDraft);
  const setFeatureFlagError = useSettingsUiStore((state) => state.setFeatureFlagError);
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
  const {
    isAdmin,
    dirtyState,
    sectorDirty,
    unsavedCount,
    filteredSectors,
    settingsTabs,
  } = useMemo(() => buildSettingsPageViewModel({
    currentUser,
    settings,
    factorWeights,
    draft,
    factorDraft,
    sectorDraft,
    sectorQuery,
    sectorExclusions,
  }), [currentUser, draft, factorDraft, factorWeights, sectorDraft, sectorExclusions, sectorQuery, settings]);

  useEffect(() => {
    if (!settingsTabs.some((tab) => tab.key === activeTab)) {
      setActiveTab(settingsTabs[0]?.key ?? "account");
    }
  }, [activeTab, setActiveTab, settingsTabs]);

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
  }, [sectorExclusions, setSectorDraft]);

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
    <SettingsLayout
      activeTab={activeTab}
      loading={Boolean(loading)}
      onRefresh={onRefresh}
      onSaveAll={() => void saveAllDirty()}
      onTabChange={setActiveTab}
      tabs={settingsTabs}
      unsavedCount={unsavedCount}
    >
        {activeTab === "account" ? (
          <SettingsSection title="账户与安全" description="安全、权限和个人偏好。">
            <AuthSecurityCard currentUser={currentUser} onUserUpdate={onUserUpdate} />
            <RitualSettingsCard />
          </SettingsSection>
        ) : null}

        {activeTab === "trading" ? (
        <SettingsSection title="交易偏好" description="风控和行业过滤参数。">
            <SettingCard className="risk-params-card" title="风控参数" button="保存风控参数" onSave={() => void saveSection("risk")} loading={loading === "settings-risk"} saved={savedSection === "risk"} disabled={Boolean(adminTokenError || singleLossError || dailyLossError || pauseLossError || minProfitError)}>
              <div className={styles.formGrid}>
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
          {isAdmin ? (
            <DataCenterEntryCard
              title="交易标的范围"
              description="ETF / 股票池在数据中心统一维护。"
            />
          ) : null}
        </SettingsSection>
        ) : null}

        {isAdmin && activeTab === "llm" ? (
          <SettingsSection title="模型与因子" description="大模型配置、因子权重和 ML 参数。" admin>
            <AdminTokenGate
              error={adminTokenError}
              value={draft.adminToken}
              onChange={(value) => setDraft({ ...draft, adminToken: value })}
            />
            <SettingCard className="llm-config-card" title="大模型配置" button="保存大模型配置" onSave={() => void saveSection("llm")} loading={loading === "settings-llm"} saved={savedSection === "llm"} disabled={Boolean(adminTokenError || llmKeyError || llmBaseUrlError)}>
              <div className={styles.formGrid}>
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
          <SettingsSection title="数据与运行" description="数据源配置、最新数据状态和运行快照。" admin>
            <AdminTokenGate
              error={adminTokenError}
              value={draft.adminToken}
              onChange={(value) => setDraft({ ...draft, adminToken: value })}
            />
            <SettingCard title="数据库与数据源" button="保存数据配置" onSave={() => void saveSection("data")} loading={loading === "settings-data"} saved={savedSection === "data"} disabled={Boolean(adminTokenError || dataSourceUrlError)}>
              <div className={styles.formGrid}>
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
            <DataCenterEntryCard
              title="数据质量与修复"
              description="数据质量、更新任务和修复操作在数据中心统一处理。"
            />
            <RuntimeSnapshotPanel settings={settings} runtime={runtime} />
          </SettingsSection>
        ) : null}

        {isAdmin && activeTab === "governance" ? (
          <SettingsSection title="诊断与审计" description="策略治理、功能开关、运行诊断和操作审计。" admin>
            <AdminTokenGate
              error={adminTokenError}
              value={draft.adminToken}
              onChange={(value) => setDraft({ ...draft, adminToken: value })}
            />
            <StrategyGovernanceCard strategyGovernance={strategyGovernance} loading={loading} onRefresh={onRefresh} onUpdateStrategyGovernance={onUpdateStrategyGovernance} />
            <FeatureFlagsCard featureFlags={featureFlags} featureFlagAudits={featureFlagAudits} featureFlagError={featureFlagError} loading={loading} saved={savedSection === "feature-flags"} onRefresh={() => void loadFeatureFlags({ includeAudit: true })} onToggle={(item) => void toggleFeatureFlag(item)} />
            <RuntimeDiagnosticsCard runtime={runtime} adminTasks={adminTasks} adminMetrics={adminMetrics} loading={loading} onRefresh={onRefresh} />
            <OperationAuditCard items={operationAudits} error={operationAuditError} loading={operationAuditLoading} onRefresh={() => void loadOperationAudits()} />
          </SettingsSection>
        ) : null}
    </SettingsLayout>
  );
}
