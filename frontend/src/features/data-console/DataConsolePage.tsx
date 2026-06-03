import { Alert, Collapse, Input } from "antd";
import type { AuthUser } from "../../types";
import { setAdminApiToken } from "../../api/base";
import { isAdmin } from "../shared/strategyPermissions";
import { EtfUniverseAdminCard } from "../settings/EtfUniverseAdminCard";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import { Panel } from "../../ui/surfaces";
import { useDataConsoleUiStore } from "../../stores/dataConsoleUiStore";
import { DataHealthOverview } from "./DataHealthOverview";
import { DataSourceHealthPanel } from "./DataSourceHealthPanel";
import { CoveragePanel } from "./CoveragePanel";
import { CollectionJobsPanel } from "./CollectionJobsPanel";
import { DataRepairPanel } from "./DataRepairPanel";
import { InstrumentInspectorPanel } from "./InstrumentInspectorPanel";
import { RuntimeFallbackPanel } from "./RuntimeFallbackPanel";
import { TradeDataGateCard } from "./TradeDataGateCard";
import { useDataConsole } from "./useDataConsole";
import { buildDataConsoleSummary } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

export function DataConsolePage({ currentUser }: { currentUser: AuthUser }) {
  if (!isAdmin(currentUser)) {
    return (
      <Panel title="数据中心">
        <Alert type="warning" showIcon message="当前账号没有数据中心权限" />
      </Panel>
    );
  }

  return <DataConsoleAdminContent />;
}

function DataConsoleAdminContent() {
  const { data, actions } = useDataConsole();
  const adminToken = useDataConsoleUiStore((state) => state.adminToken);
  const coverageStatusFilter = useDataConsoleUiStore((state) => state.coverageStatusFilter);
  const coverageScopeFilter = useDataConsoleUiStore((state) => state.coverageScopeFilter);
  const selectedDatasetKey = useDataConsoleUiStore((state) => state.selectedDatasetKey);
  const selectedScope = useDataConsoleUiStore((state) => state.selectedScope);
  const backfillStartDate = useDataConsoleUiStore((state) => state.backfillStartDate);
  const backfillEndDate = useDataConsoleUiStore((state) => state.backfillEndDate);
  const repairDatasetKey = useDataConsoleUiStore((state) => state.repairDatasetKey);
  const repairConfirmOpen = useDataConsoleUiStore((state) => state.repairConfirmOpen);
  const inspectorSymbol = useDataConsoleUiStore((state) => state.inspectorSymbol);
  const moduleLoading = useDataConsoleUiStore((state) => state.moduleLoading);
  const moduleErrors = useDataConsoleUiStore((state) => state.moduleErrors);
  const setAdminToken = useDataConsoleUiStore((state) => state.setAdminToken);
  const setField = useDataConsoleUiStore((state) => state.setField);
  const adminReady = Boolean(adminToken.trim());
  const disabledReason = "先填管理令牌才能操作";
  const summary = buildDataConsoleSummary(data.sla?.items ?? []);

  function updateAdminToken(value: string) {
    setAdminToken(value);
    setAdminApiToken(value);
  }

  return (
    <div className={styles.page}>
      <WorkspacePageIntro
        title="数据中心"
        summary="先看今日数据能不能用，再看哪里不对，最后去更新或修复。"
        detail="所有更新都交后台处理，不会动你的持仓和交易。"
        tone={summary.status === "blocked" ? "down" : summary.status === "warn" ? "warn" : "up"}
      />

      <Panel title="今日数据能不能用" className={styles.full}>
        <div className={styles.conclusionGrid}>
          <section className={styles.layerSection} aria-label="今日数据状态">
            <h3>今日数据状态</h3>
            <DataHealthOverview
              data={data.sla}
              runtimeFallback={data.runtimeFallback}
              loading={moduleLoading.sla}
              error={moduleErrors.sla}
              onRefresh={() => void actions.refreshSla()}
              onShowBlocked={() => setField("coverageStatusFilter", "blocked")}
            />
          </section>
          <section className={styles.layerSection} aria-label="能否用于交易">
            <h3>能否用于交易</h3>
            <TradeDataGateCard
              gate={data.gate}
              loading={moduleLoading.gate}
              error={moduleErrors.gate}
              onRefresh={() => void actions.refreshGate()}
            />
          </section>
          <section className={styles.layerSection} aria-label="后台兜底状态">
            <h3>后台兜底状态</h3>
            <RuntimeFallbackPanel
              status={data.runtimeFallback}
              loading={moduleLoading.runtimeFallback}
              error={moduleErrors.runtimeFallback}
              onRefresh={() => void actions.refreshRuntimeFallback()}
            />
          </section>
        </div>
      </Panel>

      <Panel title="日常巡检" className={styles.full}>
        <div className={styles.grid}>
          <section className={styles.layerSection} aria-label="数据来源是否正常">
            <h3>数据来源是否正常</h3>
            <DataSourceHealthPanel
              data={data.sourceHealth}
              loading={moduleLoading.sources}
              error={moduleErrors.sources}
              onRefresh={() => void actions.refreshSources()}
            />
          </section>
          <section className={styles.layerSection} aria-label="数据完整度">
            <h3>数据完整度</h3>
            <CoveragePanel
              items={data.sla?.items ?? []}
              detail={data.coverage}
              loading={moduleLoading.coverage}
              error={moduleErrors.coverage}
              statusFilter={coverageStatusFilter}
              scopeFilter={coverageScopeFilter}
              onStatusFilterChange={(value) => setField("coverageStatusFilter", value)}
              onScopeFilterChange={(value) => setField("coverageScopeFilter", value)}
              onSelectDetail={(item) => {
                setField("selectedDatasetKey", item.dataset_key);
                setField("selectedScope", item.scope);
                void actions.refreshCoverage({ dataset_key: item.dataset_key, scope: item.scope });
              }}
              onRefresh={() => void actions.refreshCoverage()}
            />
          </section>
        </div>
      </Panel>

      <Panel title="数据维护" className={styles.full}>
        <div className={styles.maintenanceGate}>
          <div>
            <strong>管理令牌</strong>
            <div className={styles.detail}>
              {adminReady ? "已填写，可以提交后台更新任务。" : disabledReason}
            </div>
          </div>
          <Input.Password
            aria-label="管理令牌"
            value={adminToken}
            placeholder={disabledReason}
            onChange={(event) => updateAdminToken(event.target.value)}
          />
        </div>
        <Collapse
          size="small"
          defaultActiveKey={[]}
          items={[
            {
              key: "jobs",
              label: "数据更新任务",
              children: (
                <CollectionJobsPanel
                  adminReady={adminReady}
                  disabledReason={disabledReason}
                  tasks={data.tasks}
                  loading={moduleLoading.tasks}
                  error={moduleErrors.tasks}
                  datasetKey={selectedDatasetKey}
                  scope={selectedScope}
                  startDate={backfillStartDate}
                  endDate={backfillEndDate}
                  onFieldChange={(field, value) => {
                    const fieldMap = { datasetKey: "selectedDatasetKey", scope: "selectedScope", startDate: "backfillStartDate", endDate: "backfillEndDate" } as const;
                    setField(fieldMap[field], value);
                  }}
                  onSyncInstruments={() => void actions.syncInstruments()}
                  onRefreshCloseData={() => void actions.refreshCloseData()}
                  onBackfill={() => void actions.backfill()}
                  onRefresh={() => void actions.refreshTasks()}
                />
              ),
            },
            {
              key: "repair",
              label: "数据修复",
              children: (
                <DataRepairPanel
                  audits={data.sla?.latest_repair_audits ?? []}
                  adminReady={adminReady}
                  disabledReason={disabledReason}
                  loading={moduleLoading.repair}
                  error={moduleErrors.repair}
                  datasetKey={repairDatasetKey}
                  confirmOpen={repairConfirmOpen}
                  onDatasetChange={(value) => setField("repairDatasetKey", value)}
                  onDryRun={() => void actions.repairDryRun()}
                  onOpenConfirm={() => setField("repairConfirmOpen", true)}
                  onConfirmApply={() => void actions.repairApply()}
                  onCancelConfirm={() => setField("repairConfirmOpen", false)}
                />
              ),
            },
            {
              key: "inspector",
              label: "个股数据检查",
              children: (
                <InstrumentInspectorPanel
                  symbol={inspectorSymbol}
                  result={data.inspector}
                  loading={moduleLoading.inspector}
                  error={moduleErrors.inspector}
                  onSymbolChange={(value) => setField("inspectorSymbol", value)}
                  onInspect={() => void actions.inspectSymbol()}
                />
              ),
            },
            {
              key: "etf-universe",
              label: "交易标的范围（ETF / 股票池）",
              children: <EtfUniverseAdminCard adminReady={adminReady} adminDisabledReason={disabledReason} />,
            },
          ]}
        />
      </Panel>
    </div>
  );
}
