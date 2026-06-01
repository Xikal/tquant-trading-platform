import { useCallback } from "react";
import { api } from "../../api/client";
import { getAdminApiToken, setAdminApiToken } from "../../api/base";
import { useSettingsUiStore } from "../../stores/settingsUiStore";
import { useServerState } from "../../state/serverState";
import type {
  AdminLatestDataRefreshResponse,
  AdminMetricsResponse,
  AdminTaskStatus,
  FactorWeightsResponse,
  LowBuyStrategyGovernanceResponse,
  RuntimeStatus,
  SettingsPayload,
  SettingsWorkspaceBffResponse,
  UserSectorExclusionsResponse,
} from "../../types";
import { errorMessage } from "../workspace-shared/workspaceFormatters";
import { settingsPayload, settingsToDraft } from "../workspace-shared/workspaceViewModels";

interface UseSettingsDataParams {
  withLoading: <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
  setRuntime: (value: RuntimeStatus | null) => void;
}

const SETTINGS_SERVER_KEYS = {
  settings: ["settings", "payload"] as const,
  factorWeights: ["settings", "factor-weights"] as const,
  adminTasks: ["settings", "admin-tasks"] as const,
  strategyGovernance: ["settings", "strategy-governance"] as const,
  sectorExclusions: ["settings", "sector-exclusions"] as const,
  adminMetrics: ["settings", "admin-metrics"] as const,
};

export function useSettingsData({ withLoading, setError, setNotice, setRuntime }: UseSettingsDataParams) {
  const [settings, setSettings] = useServerState<SettingsPayload | null>(SETTINGS_SERVER_KEYS.settings, null);
  const [factorWeights, setFactorWeights] = useServerState<FactorWeightsResponse | null>(SETTINGS_SERVER_KEYS.factorWeights, null);
  const [adminTasks, setAdminTasks] = useServerState<AdminTaskStatus[]>(SETTINGS_SERVER_KEYS.adminTasks, []);
  const [strategyGovernance, setStrategyGovernance] = useServerState<LowBuyStrategyGovernanceResponse | null>(
    SETTINGS_SERVER_KEYS.strategyGovernance,
    null,
  );
  const [sectorExclusions, setSectorExclusions] = useServerState<UserSectorExclusionsResponse | null>(
    SETTINGS_SERVER_KEYS.sectorExclusions,
    null,
  );
  const [adminMetrics, setAdminMetrics] = useServerState<AdminMetricsResponse | null>(SETTINGS_SERVER_KEYS.adminMetrics, null);
  const factorDraft = useSettingsUiStore((state) => state.factorDraft);
  const settingsDraft = useSettingsUiStore((state) => state.settingsDraft);
  const setFactorDraft = useSettingsUiStore((state) => state.setFactorDraft);
  const setSettingsDraft = useSettingsUiStore((state) => state.setSettingsDraft);

  const applySettingsWorkspace = useCallback((workspace: SettingsWorkspaceBffResponse) => {
    if (workspace.settings) {
      setSettings(workspace.settings);
      setSettingsDraft((draft) => settingsToDraft(workspace.settings as SettingsPayload, draft.adminToken));
    }
    if (workspace.runtime) {
      setRuntime(workspace.runtime);
    }
    if (workspace.strategy_governance) {
      setStrategyGovernance(workspace.strategy_governance);
    }
    if (workspace.sector_exclusions) {
      setSectorExclusions(workspace.sector_exclusions);
    }
    if (workspace.factor_weights) {
      setFactorWeights(workspace.factor_weights);
      setFactorDraft(factorWeightsToDraft(workspace.factor_weights));
    } else {
      setFactorWeights(null);
    }
    setAdminTasks(workspace.admin_tasks?.items ?? []);
    setAdminMetrics(workspace.admin_metrics ?? null);
  }, [setRuntime]);

  const loadSettings = useCallback(async () => {
    await withLoading("settings", async () => {
      if (settingsDraft.adminToken) {
        setAdminApiToken(settingsDraft.adminToken);
      }
      try {
        const workspace = await api.getSettingsWorkspaceBff();
        if (!workspace.settings) {
          throw new Error("系统配置 BFF 未返回基础配置");
        }
        applySettingsWorkspace(workspace);
        const blockingErrors = workspace.partial_errors.filter((item) =>
          ["settings", "sector_exclusions"].includes(item.source)
        );
        if (blockingErrors.length > 0) {
          setError(blockingErrors.map((item) => `${item.source}: ${item.detail}`).join("；"));
        }
        return;
      } catch {
        // Keep the legacy fan-out path as a compatibility fallback while the
        // Settings BFF is rolled out across independently deployed services.
      }
      const shouldLoadFactors = Boolean(getAdminApiToken());
      const [settingsResult, runtimeResult, strategyResult, sectorExclusionResult] = await Promise.allSettled([
        api.getSettings(),
        api.getRuntimeStatus(),
        api.getLowBuyStrategies(),
        api.getSectorExclusions(),
      ]);
      if (settingsResult.status === "fulfilled") {
        setSettings(settingsResult.value);
        setSettingsDraft((draft) => settingsToDraft(settingsResult.value, draft.adminToken));
      }
      if (runtimeResult.status === "fulfilled") {
        setRuntime(runtimeResult.value);
      }
      if (strategyResult.status === "fulfilled") {
        setStrategyGovernance(strategyResult.value);
      }
      if (sectorExclusionResult.status === "fulfilled") {
        setSectorExclusions(sectorExclusionResult.value);
      }
      if (shouldLoadFactors) {
        const [factorResult, taskResult, metricsResult] = await Promise.allSettled([
          api.getFactorWeights(),
          api.getAdminTasks(),
          api.getAdminMetrics(),
        ]);
        if (factorResult.status === "fulfilled") {
          setFactorWeights(factorResult.value);
          setFactorDraft(factorWeightsToDraft(factorResult.value));
        }
        if (taskResult.status === "fulfilled") {
          setAdminTasks(taskResult.value.items);
        }
        if (metricsResult.status === "fulfilled") {
          setAdminMetrics(metricsResult.value);
        }
      } else {
        setFactorWeights(null);
        setAdminTasks([]);
        setAdminMetrics(null);
      }
      const rejections = [settingsResult, runtimeResult, strategyResult].filter(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      // 会话过期：把 401 抛给外层 withLoading，由其统一触发登出，避免只弹错误条而不退出登录。
      const authRejection = rejections.find(
        (item) => (item.reason as { status?: number } | null)?.status === 401,
      );
      if (authRejection) {
        throw authRejection.reason;
      }
      if (rejections.length > 0) {
        setError(errorMessage(rejections[0].reason));
      }
    });
  }, [applySettingsWorkspace, setError, settingsDraft.adminToken, withLoading]);

  const saveSettings = useCallback(async (section: "llm" | "risk" | "data") => {
    await withLoading(`settings-${section}`, async () => {
      setAdminApiToken(settingsDraft.adminToken);
      const payload = settingsPayload(settingsDraft, section);
      const result = await api.updateSettings(payload);
      setSettings(result.settings);
      setSettingsDraft((draft) => settingsToDraft(result.settings, draft.adminToken));
      setNotice(result.restart_required ? "保存成功，部分配置重启后生效" : "保存成功");
    });
  }, [settingsDraft, setNotice, withLoading]);

  const saveFactorWeights = useCallback(async () => {
    await withLoading("settings-factor", async () => {
      setAdminApiToken(settingsDraft.adminToken);
      if (!getAdminApiToken()) {
        throw new Error("请先填写正确的管理令牌");
      }
      const nextWeights = parseFactorDraft(factorDraft);
      const result = await api.updateFactorWeights(nextWeights);
      setFactorWeights(result);
      setFactorDraft(factorWeightsToDraft(result));
      setNotice("因子权重已保存");
    });
  }, [factorDraft, settingsDraft.adminToken, setNotice, withLoading]);

  const updateStrategyGovernance = useCallback(async (
    strategyKey: string,
    status: "active" | "watch" | "paused",
  ) => {
    await withLoading("settings", async () => {
      setAdminApiToken(settingsDraft.adminToken);
      if (!getAdminApiToken()) {
        throw new Error("请先填写正确的管理令牌");
      }
      const result = await api.updateLowBuyStrategyGovernance(strategyKey, { status });
      setStrategyGovernance(result);
      setNotice(status === "active" ? "策略已恢复自动治理" : status === "watch" ? "策略已降级为观察" : "策略强信号已暂停");
    });
  }, [settingsDraft.adminToken, setNotice, withLoading]);

  const saveSectorExclusions = useCallback(async (excludedSectors: string[]) => {
    await withLoading("settings-sector-exclusions", async () => {
      const result = await api.updateSectorExclusions(excludedSectors);
      setSectorExclusions(result);
      setNotice(`板块过滤已保存，已排除 ${result.excluded_count} 个板块`);
    });
  }, [setNotice, withLoading]);

  const refreshLatestData = useCallback(async () => {
    await withLoading("latest-data-refresh", async () => {
      setAdminApiToken(settingsDraft.adminToken);
      if (!getAdminApiToken()) {
        throw new Error("请先填写正确的管理令牌");
      }
      const result = await api.refreshLatestLowBuyData();
      const metrics = await api.getAdminMetrics();
      setAdminMetrics(metrics);
      setNotice(latestDataRefreshNotice(result));
    });
  }, [settingsDraft.adminToken, setNotice, withLoading]);

  return {
    settings,
    factorWeights,
    adminTasks,
    adminMetrics,
    strategyGovernance,
    sectorExclusions,
    factorDraft,
    settingsDraft,
    setFactorDraft,
    setSettingsDraft,
    loadSettings,
    saveSettings,
    saveFactorWeights,
    updateStrategyGovernance,
    saveSectorExclusions,
    refreshLatestData,
  };
}

function latestDataRefreshNotice(result: AdminLatestDataRefreshResponse): string {
  if (result.action === "enqueue_daily_bar_refresh") {
    return `已开始补全 ${result.expected_trade_date ?? "当日"} 日线数据，当前 ${result.daily_bar_count ?? 0} 条`;
  }
  if (result.action === "enqueue_low_buy_materialization") {
    const missingCount = result.missing_strategies?.length ?? 0;
    return `日线已补齐，已开始重建 ${missingCount} 个策略快照`;
  }
  if (result.action === "publish_latest_trade_date") {
    return result.ok ? "最新数据已发布，前端可直接使用" : "数据发布仍在等待补齐，请稍后刷新";
  }
  if (result.action === "already_latest") {
    return "最新数据已经发布，无需重复补全";
  }
  if (result.action === "skip_before_close") {
    return "当前未到收盘补全时间，系统会在收盘后自动检查";
  }
  return "已提交最新数据补全检查";
}

function factorWeightsToDraft(payload: FactorWeightsResponse): Record<string, string> {
  return Object.fromEntries(
    Object.entries(payload.weights).map(([key, value]) => [key, String(value)])
  );
}

function parseFactorDraft(draft: Record<string, string>): Record<string, number> {
  const result: Record<string, number> = {};
  for (const [key, value] of Object.entries(draft)) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) {
      throw new Error(`因子 ${key} 的权重必须是非负数字`);
    }
    result[key] = parsed;
  }
  return result;
}
