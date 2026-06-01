import { useCallback, useEffect } from "react";
import { setAdminApiToken } from "../../api/base";
import { api } from "../../api/client";
import { dataConsoleInspectorApi } from "../../api/dataConsoleInspector";
import { dataQualityApi, type DataQualityCoverageResponse, type DataQualitySlaResponse } from "../../api/dataQuality";
import { dataSourcesApi } from "../../api/dataSources";
import { runtimeTasksApi, type RuntimeTaskOut } from "../../api/runtimeTasks";
import { useDataConsoleUiStore, type DataConsoleModuleKey } from "../../stores/dataConsoleUiStore";
import { useServerState } from "../../state/serverState";
import type { DataSourceProbeResponse } from "../../types";
import type { InstrumentInspectorResponse } from "../../api/dataConsoleInspector";
import type { TradeDataGateResponse } from "../../api/dataQuality";
import type { DataConsoleActions, DataConsoleData } from "./dataConsoleTypes";

const DATA_CONSOLE_SERVER_KEYS = {
  sla: ["data-console", "sla"] as const,
  sources: ["data-console", "sources"] as const,
  coverage: ["data-console", "coverage"] as const,
  tasks: ["data-console", "tasks"] as const,
  inspector: ["data-console", "inspector"] as const,
  gate: ["data-console", "gate"] as const,
};

const READ_REFRESH_MS = 5 * 60 * 1000;
const TASK_REFRESH_MS = 2500;
const EMPTY_TASKS: RuntimeTaskOut[] = [];

export function useDataConsole(): { data: DataConsoleData; actions: DataConsoleActions } {
  const [sla, setSla] = useServerState<DataQualitySlaResponse | null>(DATA_CONSOLE_SERVER_KEYS.sla, null);
  const [sourceHealth, setSourceHealth] = useServerState<DataSourceProbeResponse | null>(DATA_CONSOLE_SERVER_KEYS.sources, null);
  const [coverage, setCoverage] = useServerState<DataQualityCoverageResponse | null>(DATA_CONSOLE_SERVER_KEYS.coverage, null);
  const [tasks, setTasks] = useServerState<RuntimeTaskOut[]>(DATA_CONSOLE_SERVER_KEYS.tasks, EMPTY_TASKS);
  const [inspector, setInspector] = useServerState<InstrumentInspectorResponse | null>(DATA_CONSOLE_SERVER_KEYS.inspector, null);
  const [gate, setGate] = useServerState<TradeDataGateResponse | null>(DATA_CONSOLE_SERVER_KEYS.gate, null);
  const selectedDatasetKey = useDataConsoleUiStore((state) => state.selectedDatasetKey);
  const selectedScope = useDataConsoleUiStore((state) => state.selectedScope);
  const backfillStartDate = useDataConsoleUiStore((state) => state.backfillStartDate);
  const backfillEndDate = useDataConsoleUiStore((state) => state.backfillEndDate);
  const repairDatasetKey = useDataConsoleUiStore((state) => state.repairDatasetKey);
  const inspectorSymbol = useDataConsoleUiStore((state) => state.inspectorSymbol);
  const adminToken = useDataConsoleUiStore((state) => state.adminToken);
  const setModuleLoading = useDataConsoleUiStore((state) => state.setModuleLoading);
  const setModuleError = useDataConsoleUiStore((state) => state.setModuleError);
  const setField = useDataConsoleUiStore((state) => state.setField);

  useEffect(() => {
    setAdminApiToken(adminToken);
  }, [adminToken]);

  const refreshSla = useCallback(async () => {
    await loadModule("sla", setModuleLoading, setModuleError, async () => setSla(await dataQualityApi.sla()));
  }, [setModuleError, setModuleLoading, setSla]);

  const refreshSources = useCallback(async () => {
    await loadModule("sources", setModuleLoading, setModuleError, async () => setSourceHealth(await dataSourcesApi.health()));
  }, [setModuleError, setModuleLoading, setSourceHealth]);

  const refreshCoverage = useCallback(async (next?: { dataset_key: string; scope: string }) => {
    await loadModule("coverage", setModuleLoading, setModuleError, async () => {
      setCoverage(await dataQualityApi.coverage(next ?? { dataset_key: selectedDatasetKey, scope: selectedScope }));
    });
  }, [selectedDatasetKey, selectedScope, setCoverage, setModuleError, setModuleLoading]);

  const refreshTasks = useCallback(async () => {
    await loadModule("tasks", setModuleLoading, setModuleError, async () => setTasks((await runtimeTasksApi.list("", 80)).items));
  }, [setModuleError, setModuleLoading, setTasks]);

  const refreshGate = useCallback(async () => {
    await loadModule("gate", setModuleLoading, setModuleError, async () => setGate(await dataQualityApi.tradeGate()));
  }, [setGate, setModuleError, setModuleLoading]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshSla(), refreshSources(), refreshCoverage(), refreshTasks(), refreshGate()]);
  }, [refreshCoverage, refreshGate, refreshSla, refreshSources, refreshTasks]);

  const syncInstruments = useCallback(async () => {
    await loadModule("tasks", setModuleLoading, setModuleError, async () => {
      await api.syncInstruments();
      setTasks((await runtimeTasksApi.list("", 80)).items);
    });
  }, [setModuleError, setModuleLoading, setTasks]);

  const refreshCloseData = useCallback(async () => {
    await loadModule("tasks", setModuleLoading, setModuleError, async () => {
      await runtimeTasksApi.enqueue({
        task_type: "daily_bar_refresh",
        payload: { limit: 6000, reason: "data_console_close_refresh" },
        priority: 20,
        max_attempts: 2,
      });
      setTasks((await runtimeTasksApi.list("", 80)).items);
    });
  }, [setModuleError, setModuleLoading, setTasks]);

  const backfill = useCallback(async () => {
    await loadModule("tasks", setModuleLoading, setModuleError, async () => {
      await dataQualityApi.backfill({
        dataset_key: selectedDatasetKey,
        scope: selectedScope,
        start_date: backfillStartDate,
        end_date: backfillEndDate,
      });
      setTasks((await runtimeTasksApi.list("", 80)).items);
    });
  }, [backfillEndDate, backfillStartDate, selectedDatasetKey, selectedScope, setModuleError, setModuleLoading, setTasks]);

  const repairDryRun = useCallback(async () => {
    await loadModule("repair", setModuleLoading, setModuleError, async () => {
      await dataQualityApi.repair({ dataset_key: repairDatasetKey, dry_run: true });
      await refreshSla();
    });
  }, [refreshSla, repairDatasetKey, setModuleError, setModuleLoading]);

  const repairApply = useCallback(async () => {
    await loadModule("repair", setModuleLoading, setModuleError, async () => {
      await dataQualityApi.repair({ dataset_key: repairDatasetKey, dry_run: false });
      setField("repairConfirmOpen", false);
      await refreshTasks();
      await refreshSla();
    });
  }, [refreshSla, refreshTasks, repairDatasetKey, setField, setModuleError, setModuleLoading]);

  const inspectSymbol = useCallback(async () => {
    const symbol = inspectorSymbol.trim();
    if (!symbol) {
      setInspector(null);
      return;
    }
    await loadModule("inspector", setModuleLoading, setModuleError, async () => setInspector(await dataConsoleInspectorApi.inspect(symbol)));
  }, [inspectorSymbol, setInspector, setModuleError, setModuleLoading]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void Promise.all([refreshSla(), refreshSources(), refreshCoverage(), refreshGate()]);
      }
    }, READ_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refreshCoverage, refreshGate, refreshSla, refreshSources]);

  useEffect(() => {
    if (!shouldPollRuntimeTasks(tasks, document.visibilityState)) {
      return undefined;
    }
    const timer = window.setInterval(() => void refreshTasks(), TASK_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refreshTasks, tasks]);

  return {
    data: { sla, sourceHealth, coverage, tasks, inspector, gate },
    actions: {
      refreshSla,
      refreshSources,
      refreshCoverage,
      refreshTasks,
      refreshGate,
      refreshAll,
      syncInstruments,
      refreshCloseData,
      backfill,
      repairDryRun,
      repairApply,
      inspectSymbol,
    },
  };
}

export function shouldPollRuntimeTasks(tasks: Array<Pick<RuntimeTaskOut, "status">>, visibilityState: DocumentVisibilityState): boolean {
  return visibilityState === "visible" && tasks.some((item) => item.status === "queued" || item.status === "running");
}

async function loadModule(
  key: DataConsoleModuleKey,
  setLoading: (key: DataConsoleModuleKey, loading: boolean) => void,
  setError: (key: DataConsoleModuleKey, error: string) => void,
  runner: () => Promise<void>,
) {
  setLoading(key, true);
  try {
    await runner();
    setError(key, "");
  } catch (error) {
    setError(key, error instanceof Error ? error.message : "模块加载失败");
  } finally {
    setLoading(key, false);
  }
}
