import { Alert, Button, Collapse, Input } from "antd";
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
import { TradeDataGateCard } from "./TradeDataGateCard";
import { useDataConsole } from "./useDataConsole";
import { buildDataConsoleSummary } from "./dataConsoleTypes";
import styles from "./DataConsolePage.module.css";

export function DataConsolePage({ currentUser }: { currentUser: AuthUser }) {
  if (!isAdmin(currentUser)) {
    return (
      <Panel title="数据控制台">
        <Alert type="warning" showIcon message="当前账号没有数据控制台权限" />
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
  const disabledReason = "需填写管理令牌";
  const summary = buildDataConsoleSummary(data.sla?.items ?? []);

  function updateAdminToken(value: string) {
    setAdminToken(value);
    setAdminApiToken(value);
  }

  return (
    <div className={styles.page}>
      <WorkspacePageIntro
        title="数据控制台"
        summary="集中查看数据健康、源状态、采集任务、修复审计和实盘前数据门。"
        detail="所有采集、修复、回补只提交后台任务，Web 不执行重逻辑，不触发交易。"
        pills={[
          { label: "综合灯", value: summary.conclusion, tone: summary.status === "blocked" ? "down" : summary.status === "warn" ? "warn" : "up" },
          { label: "阻断", value: String(summary.blocked), tone: summary.blocked ? "down" : "neutral" },
          { label: "缺失", value: String(summary.missing), tone: summary.missing ? "warn" : "neutral" },
        ]}
        actions={(
          <Input.Password
            aria-label="管理令牌"
            value={adminToken}
            placeholder={disabledReason}
            onChange={(event) => updateAdminToken(event.target.value)}
          />
        )}
      />

      <Panel title="A 数据健康总览" className={styles.full}>
        <DataHealthOverview
          data={data.sla}
          loading={moduleLoading.sla}
          error={moduleErrors.sla}
          onRefresh={() => void actions.refreshSla()}
          onShowBlocked={() => setField("coverageStatusFilter", "blocked")}
        />
      </Panel>

      <div className={styles.grid}>
        <Panel title="B 数据源健康">
          <DataSourceHealthPanel
            data={data.sourceHealth}
            loading={moduleLoading.sources}
            error={moduleErrors.sources}
            onRefresh={() => void actions.refreshSources()}
          />
        </Panel>
        <Panel title="H 实盘前数据门">
          <TradeDataGateCard
            gate={data.gate}
            loading={moduleLoading.gate}
            error={moduleErrors.gate}
            onRefresh={() => void actions.refreshGate()}
          />
        </Panel>
      </div>

      <Panel title="C 覆盖率与新鲜度" className={styles.full}>
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
      </Panel>

      <Panel title="D 采集任务与调度" className={styles.full}>
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
      </Panel>

      <div className={styles.grid}>
        <Panel title="E 数据修复与对账">
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
        </Panel>
        <Panel title="F 单票数据巡检">
          <InstrumentInspectorPanel
            symbol={inspectorSymbol}
            result={data.inspector}
            loading={moduleLoading.inspector}
            error={moduleErrors.inspector}
            onSymbolChange={(value) => setField("inspectorSymbol", value)}
            onInspect={() => void actions.inspectSymbol()}
          />
        </Panel>
      </div>

      <Panel title="G ETF / 股票池管理" className={styles.full}>
        <Collapse
          size="small"
          items={[
            {
              key: "etf-universe",
              label: "展开 ETF Universe 管理",
              children: <EtfUniverseAdminCard adminReady={adminReady} adminDisabledReason={disabledReason} />,
            },
          ]}
        />
      </Panel>
    </div>
  );
}
