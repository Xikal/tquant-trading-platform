import { createMutationClient } from "../../shared/api/mutations";
import { ShadowActionPanel } from "../../shared/ui/ShadowActionPanel";
import { StatusPill } from "../../shared/ui/StatusPill";
import { factorWeightsPayload, genericMutationPayload, sectorExclusionsPayload, settingsPayload } from "../shared/mutationPayloads";

function contractPills() {
  return (
    <div class="tq-tag-row">
      <StatusPill label="写入" value="本地记录" tone="warn" title="当前先记录操作意图；正式写入需完成安全复验后开启。" />
      <StatusPill label="模式" value="保护模式" tone="warn" />
    </div>
  );
}

function writeResult(liveMessage: string, localMessage: string, mode: "shadow" | "live") {
  return mode === "live" ? liveMessage : localMessage;
}

export function SettingsWritePanel() {
  const client = createMutationClient();
  return (
    <ShadowActionPanel
      title="配置写入"
      actionLabel="记录配置意图"
      resultTitle="配置状态"
      embedded
      beforeFields={contractPills()}
      fields={[
        { key: "section", label: "分区", value: "risk" },
        { key: "key", label: "字段", value: "risk_max_single_loss_pct" },
        { key: "value", label: "目标值", value: "1" },
        { key: "reason", label: "原因", value: "参数观察" },
      ]}
      confirmText="配置写入已进入二次确认"
      onSubmit={async (draft) => {
        const result = await client.updateSettings(settingsPayload(draft));
        return writeResult("配置写入已发送", "配置意图已记录，本地使用不影响当前系统配置", result.mode);
      }}
    />
  );
}

export function SectorExclusionsWritePanel() {
  const client = createMutationClient();
  return (
    <ShadowActionPanel
      title="行业排除管理"
      actionLabel="记录行业排除"
      resultTitle="行业配置状态"
      embedded
      beforeFields={contractPills()}
      fields={[
        { key: "sectors", label: "排除行业", value: "房地产" },
        { key: "reason", label: "原因", value: "风险过滤复核" },
      ]}
      confirmText="行业排除已进入二次确认"
      onSubmit={async (draft) => {
        const result = await client.updateSectorExclusions(sectorExclusionsPayload(draft));
        return writeResult("行业排除写入已发送", "行业排除意图已记录，本地使用不影响生产过滤", result.mode);
      }}
    />
  );
}

export function FactorWeightsWritePanel() {
  const client = createMutationClient();
  return (
    <ShadowActionPanel
      title="因子权重管理"
      actionLabel="记录因子权重"
      resultTitle="因子配置状态"
      embedded
      beforeFields={contractPills()}
      fields={[
        { key: "factor", label: "因子", value: "volume_price" },
        { key: "weight", label: "权重", value: "0.4" },
        { key: "reason", label: "原因", value: "样本外观察" },
      ]}
      confirmText="因子权重已进入二次确认"
      onSubmit={async (draft) => {
        const result = await client.updateFactorWeights(factorWeightsPayload(draft));
        return writeResult("因子权重写入已发送", "因子权重意图已记录，本地使用不改变生产排序", result.mode);
      }}
    />
  );
}

export function QuantParametersWritePanel() {
  return (
    <ShadowActionPanel
      title="量化参数管理"
      actionLabel="记录参数变更"
      resultTitle="量化参数状态"
      embedded
      beforeFields={contractPills()}
      fields={[
        { key: "version", label: "版本", value: "v1" },
        { key: "scope", label: "范围", value: "low_buy" },
        { key: "reason", label: "原因", value: "参数观察" },
      ]}
      confirmText="量化参数已进入二次确认"
      onSubmit={(draft) => `${genericMutationPayload(draft).source ? "量化参数" : "参数"}变更意图已记录，本地使用不改变生产策略`}
    />
  );
}

export function StrategyGovernanceWritePanel() {
  return (
    <ShadowActionPanel
      title="策略治理管理"
      actionLabel="记录治理变更"
      resultTitle="治理状态"
      embedded
      beforeFields={contractPills()}
      fields={[
        { key: "strategy", label: "策略", value: "N形洗盘低吸" },
        { key: "action", label: "动作", value: "review_only" },
        { key: "reason", label: "原因", value: "治理复核" },
      ]}
      confirmText="策略治理已进入二次确认"
      onSubmit={(draft) => `${genericMutationPayload(draft).strategy ? "策略治理" : "治理"}变更意图已记录，本地使用不改变生产策略`}
    />
  );
}
