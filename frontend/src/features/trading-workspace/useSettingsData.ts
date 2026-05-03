import { useState } from "react";
import { api } from "../../api/client";
import { getAdminApiToken, setAdminApiToken } from "../../api/base";
import type {
  AdminTaskStatus,
  FactorWeightsResponse,
  LowBuyStrategyGovernanceResponse,
  RuntimeStatus,
  SettingsPayload,
} from "../../types";
import type { SettingsDraft } from "./workspaceTypes";
import { errorMessage } from "./workspaceFormatters";
import { settingsPayload, settingsToDraft } from "./workspaceViewModels";

interface UseSettingsDataParams {
  withLoading: <T>(key: string, action: () => Promise<T>) => Promise<T | undefined>;
  setError: (value: string) => void;
  setNotice: (value: string) => void;
  setRuntime: (value: RuntimeStatus | null) => void;
}

export function useSettingsData({ withLoading, setError, setNotice, setRuntime }: UseSettingsDataParams) {
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [factorWeights, setFactorWeights] = useState<FactorWeightsResponse | null>(null);
  const [adminTasks, setAdminTasks] = useState<AdminTaskStatus[]>([]);
  const [strategyGovernance, setStrategyGovernance] = useState<LowBuyStrategyGovernanceResponse | null>(null);
  const [factorDraft, setFactorDraft] = useState<Record<string, string>>({});
  const [settingsDraft, setSettingsDraft] = useState<SettingsDraft>({
    adminToken: getAdminApiToken(),
    llm_provider: "",
    llm_api_key: "",
    llm_base_url: "",
    llm_model: "",
    data_source: "",
    data_source_base_url: "",
    risk_max_single_loss_pct: "",
    risk_max_daily_loss_pct: "",
    risk_pause_after_losses: "",
    strategy_min_profit_pct: "",
  });

  async function loadSettings() {
    await withLoading("settings", async () => {
      if (settingsDraft.adminToken) {
        setAdminApiToken(settingsDraft.adminToken);
      }
      const shouldLoadFactors = Boolean(getAdminApiToken());
      const [settingsResult, runtimeResult, strategyResult] = await Promise.allSettled([
        api.getSettings(),
        api.getRuntimeStatus(),
        api.getLowBuyStrategies(),
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
      if (shouldLoadFactors) {
        const [factorResult, taskResult] = await Promise.allSettled([
          api.getFactorWeights(),
          api.getAdminTasks(),
        ]);
        if (factorResult.status === "fulfilled") {
          setFactorWeights(factorResult.value);
          setFactorDraft(factorWeightsToDraft(factorResult.value));
        }
        if (taskResult.status === "fulfilled") {
          setAdminTasks(taskResult.value.items);
        }
      }
      const rejected = [settingsResult, runtimeResult, strategyResult].find(
        (item): item is PromiseRejectedResult => item.status === "rejected"
      );
      if (rejected) {
        setError(errorMessage(rejected.reason));
      }
    });
  }

  async function saveSettings(section: "llm" | "risk" | "data") {
    await withLoading(`settings-${section}`, async () => {
      setAdminApiToken(settingsDraft.adminToken);
      const payload = settingsPayload(settingsDraft, section);
      const result = await api.updateSettings(payload);
      setSettings(result.settings);
      setSettingsDraft((draft) => settingsToDraft(result.settings, draft.adminToken));
      setNotice(result.restart_required ? "保存成功，部分配置重启后生效" : "保存成功");
    });
  }

  async function saveFactorWeights() {
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
  }

  return {
    settings,
    factorWeights,
    adminTasks,
    strategyGovernance,
    factorDraft,
    settingsDraft,
    setFactorDraft,
    setSettingsDraft,
    loadSettings,
    saveSettings,
    saveFactorWeights,
  };
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
