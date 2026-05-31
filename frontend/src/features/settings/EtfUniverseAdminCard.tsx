import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo } from "react";
import { Alert, Button, Checkbox, Space, Tag } from "antd";

import { etfUniverseAdminApi } from "../../api/etfUniverseAdmin";
import { NumberField, TextField } from "../../components/shared/FormFields";
import { useEtfUniverseAdminStore } from "../../stores/etfUniverseAdminStore";
import { useServerState } from "../../state/serverState";
import type {
  EtfUniverseAdminProfile,
  EtfUniverseAdminResponse,
  EtfUniverseOverride,
  EtfUniverseOverrideMap,
  EtfUniverseRepairDraftResponse,
} from "../../types/etfUniverseAdmin";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { InfoPill, SettingCard } from "../workspace-shared/WorkspaceComponents";

const FORM_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
};

const PANEL_GRID_STYLE: CSSProperties = {
  display: "grid",
  gap: 10,
  gridTemplateColumns: "minmax(0, 1.1fr) minmax(260px, 0.9fr)",
};

const INLINE_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: 8,
};

export const ETF_UNIVERSE_ADMIN_SERVER_KEYS = {
  payload: ["settings", "etf-universe-admin", "payload"] as const,
  repairDraft: ["settings", "etf-universe-admin", "repair-draft"] as const,
};

export function EtfUniverseAdminCard() {
  const [payload, setPayload] = useServerState<EtfUniverseAdminResponse | null>(ETF_UNIVERSE_ADMIN_SERVER_KEYS.payload, null);
  const [repairDraft, setRepairDraft] = useServerState<EtfUniverseRepairDraftResponse | null>(
    ETF_UNIVERSE_ADMIN_SERVER_KEYS.repairDraft,
    null,
  );
  const draftOverrides = useEtfUniverseAdminStore((state) => state.draftOverrides);
  const filter = useEtfUniverseAdminStore((state) => state.filter);
  const repairSymbol = useEtfUniverseAdminStore((state) => state.repairSymbol);
  const repairName = useEtfUniverseAdminStore((state) => state.repairName);
  const repairCategory = useEtfUniverseAdminStore((state) => state.repairCategory);
  const version = useEtfUniverseAdminStore((state) => state.version);
  const description = useEtfUniverseAdminStore((state) => state.description);
  const activate = useEtfUniverseAdminStore((state) => state.activate);
  const confirmHighRisk = useEtfUniverseAdminStore((state) => state.confirmHighRisk);
  const rollbackVersion = useEtfUniverseAdminStore((state) => state.rollbackVersion);
  const loading = useEtfUniverseAdminStore((state) => state.loading);
  const error = useEtfUniverseAdminStore((state) => state.error);
  const message = useEtfUniverseAdminStore((state) => state.message);
  const setDraftOverrides = useEtfUniverseAdminStore((state) => state.setDraftOverrides);
  const setField = useEtfUniverseAdminStore((state) => state.setField);
  const mergeDraftOverrides = useEtfUniverseAdminStore((state) => state.mergeDraftOverrides);

  const load = useCallback(async () => {
    setField("loading", true);
    setField("error", "");
    try {
      const response = await etfUniverseAdminApi.getAdmin();
      setPayload(response);
      setDraftOverrides(response.normalized_overrides ?? {});
      setField("rollbackVersion", response.recent_versions?.[0]?.version ?? "");
      setField("message", "");
    } catch (exc: unknown) {
      setField("error", exc instanceof Error ? exc.message : "ETF Universe 加载失败");
    } finally {
      setField("loading", false);
    }
  }, [setField, setPayload]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredItems = useMemo(() => {
    const query = filter.trim().toLowerCase();
    const items = payload?.items ?? [];
    if (!query) return items;
    return items.filter((item) =>
      [item.symbol, item.name, item.category, item.tracking_index, item.notes].some((value) => String(value || "").toLowerCase().includes(query))
    );
  }, [filter, payload]);

  const highRiskCount = useMemo(() => payload?.diff.filter((item) => item.risk_level === "high").length ?? 0, [payload]);
  const applyDisabled = !version.trim() || !description.trim() || Boolean(payload?.validation.error_count) || (activate && highRiskCount > 0 && !confirmHighRisk);

  async function validateDraft() {
    setField("loading", true);
    setField("error", "");
    try {
      const response = await etfUniverseAdminApi.validate(draftOverrides);
      setPayload(response);
      setDraftOverrides(response.normalized_overrides ?? draftOverrides);
      setField("message", "草稿校验完成。");
    } catch (exc: unknown) {
      setField("error", exc instanceof Error ? exc.message : "草稿校验失败");
    } finally {
      setField("loading", false);
    }
  }

  async function buildRepairDraft() {
    setField("loading", true);
    setField("error", "");
    try {
      const response = await etfUniverseAdminApi.repairDraft({
        symbol: repairSymbol,
        name: repairName,
        category: repairCategory,
      });
      setRepairDraft(response);
      mergeDraftOverrides(response.draft_overrides);
      setField("message", "修复向导已生成草稿，保存前请先校验。");
    } catch (exc: unknown) {
      setField("error", exc instanceof Error ? exc.message : "修复草稿生成失败");
    } finally {
      setField("loading", false);
    }
  }

  async function applyDraft() {
    setField("loading", true);
    setField("error", "");
    try {
      const response = await etfUniverseAdminApi.apply({
        draft_overrides: draftOverrides,
        version,
        description,
        activate,
        confirm_high_risk: confirmHighRisk,
      });
      setPayload(response.admin);
      setDraftOverrides(response.admin.normalized_overrides ?? {});
      setField("rollbackVersion", response.admin.recent_versions?.[0]?.version ?? "");
      setField("message", response.message);
      setField("version", `etf-universe-${Date.now()}`);
      setField("description", "");
    } catch (exc: unknown) {
      setField("error", exc instanceof Error ? exc.message : "ETF Universe 保存失败");
    } finally {
      setField("loading", false);
    }
  }

  async function rollback() {
    if (!rollbackVersion.trim()) return;
    setField("loading", true);
    setField("error", "");
    try {
      const response = await etfUniverseAdminApi.rollback({ version: rollbackVersion, confirm: true });
      setPayload(response.admin);
      setDraftOverrides(response.admin.normalized_overrides ?? {});
      setField("rollbackVersion", response.admin.recent_versions?.[0]?.version ?? "");
      setField("message", response.message);
    } catch (exc: unknown) {
      setField("error", exc instanceof Error ? exc.message : "ETF Universe 回滚失败");
    } finally {
      setField("loading", false);
    }
  }

  return (
    <SettingCard
      className="etf-universe-admin-card"
      title="ETF Universe 管理"
      button="刷新 Universe"
      onSave={() => void load()}
      loading={loading}
      disabled={loading}
    >
      <p className="muted">仅管理员可改 universe 覆盖项；这里维护品种能力、T+0 规则和执行约束，不生成策略信号。</p>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {message ? <Alert type="success" showIcon message={message} /> : null}
      <div style={INLINE_STYLE}>
        <InfoPill label="Universe" value={payload?.version ?? "--"} />
        <InfoPill label="总数" value={payload ? String(payload.current_count) : "--"} />
        <InfoPill label="T+0 可用" value={payload ? String(payload.t0_enabled_count) : "--"} />
        <InfoPill label="覆盖项" value={payload ? String(payload.override_count) : "--"} />
        <InfoPill label="异常" value={payload ? `${payload.validation.error_count} error / ${payload.validation.warning_count} warning` : "--"} />
        <InfoPill label="高风险 diff" value={String(highRiskCount)} tone={highRiskCount ? "warn" : "neutral"} />
      </div>
      <TextField label="筛选" value={filter} placeholder="代码、名称、分类、指数、备注" onChange={(event) => setField("filter", event.target.value)} />

      <div style={PANEL_GRID_STYLE}>
        <VirtualGrid<EtfUniverseAdminProfile>
          rowKey="symbol"
          dataSource={filteredItems}
          scroll={{ x: 940 }}
          columns={[
            { title: "代码", dataIndex: "symbol", width: 90, render: (value, item) => <span><strong>{value}</strong><small className="hint">{item.name}</small></span> },
            { title: "分类", dataIndex: "category", width: 110, render: (value, item) => <Tag color={item.source === "override" ? "blue" : "default"}>{value}</Tag> },
            { title: "T+0", dataIndex: "same_day_sell_allowed", width: 90, render: (value, item) => <Tag color={value ? "green" : "default"}>{value ? "可用" : item.t0_eligible ? "禁用" : "不可用"}</Tag> },
            { title: "结算", dataIndex: "settlement_rule", width: 80 },
            { title: "最低额", dataIndex: "min_amount", width: 110, render: (value) => `${Math.round(Number(value || 0) / 10000)} 万` },
            { title: "价差/滑点", width: 120, render: (_, item) => `${item.max_spread_bps} / ${item.slippage_bps} bps` },
            { title: "校验", dataIndex: "validation_severity", width: 90, render: (value) => <Tag color={severityColor(value)}>{value}</Tag> },
            { title: "备注", dataIndex: "notes", ellipsis: true },
          ]}
        />

        <div style={{ display: "grid", gap: 10 }}>
          <div style={FORM_GRID_STYLE}>
            <TextField label="代码" value={repairSymbol} onChange={(event) => setField("repairSymbol", event.target.value)} />
            <TextField label="名称" value={repairName} onChange={(event) => setField("repairName", event.target.value)} />
            <TextField label="分类" value={repairCategory} placeholder="sector / gold / cross_border" onChange={(event) => setField("repairCategory", event.target.value)} />
          </div>
          <Button htmlType="button" onClick={() => void buildRepairDraft()} disabled={!repairSymbol.trim() || loading}>生成修复草稿</Button>
          {repairDraft ? <Alert type={repairDraft.validation.error_count ? "error" : "warning"} showIcon message={repairDraft.notes[0] || "修复草稿已生成"} /> : null}
          <OverrideEditor draft={draftOverrides} onChange={setDraftOverrides} />
          <Button htmlType="button" onClick={() => void validateDraft()} disabled={loading}>校验草稿</Button>
        </div>
      </div>

      <VirtualGrid
        rowKey={(item) => `${item.symbol}-${item.field}-${item.message}`}
        dataSource={payload?.validation.issues ?? []}
        locale={{ emptyText: "未发现校验问题" }}
        columns={[
          { title: "级别", dataIndex: "severity", width: 90, render: (value) => <Tag color={severityColor(value)}>{value}</Tag> },
          { title: "代码", dataIndex: "symbol", width: 90 },
          { title: "字段", dataIndex: "field", width: 160 },
          { title: "问题", dataIndex: "message" },
        ]}
      />

      <VirtualGrid
        rowKey={(item) => `${item.symbol}-${item.field}`}
        dataSource={payload?.diff ?? []}
        locale={{ emptyText: "当前草稿与运行时无差异" }}
        columns={[
          { title: "风险", dataIndex: "risk_level", width: 90, render: (value) => <Tag color={riskColor(value)}>{value}</Tag> },
          { title: "代码", dataIndex: "symbol", width: 90 },
          { title: "字段", dataIndex: "field", width: 150 },
          { title: "说明", dataIndex: "message" },
        ]}
      />

      <div style={FORM_GRID_STYLE}>
        <TextField label="版本号" value={version} onChange={(event) => setField("version", event.target.value)} />
        <TextField label="变更说明" value={description} onChange={(event) => setField("description", event.target.value)} />
        <label style={INLINE_STYLE}>
          <Checkbox checked={activate} onChange={(event) => setField("activate", event.target.checked)} />
          <span>保存并激活</span>
        </label>
        <label style={INLINE_STYLE}>
          <Checkbox checked={confirmHighRisk} onChange={(event) => setField("confirmHighRisk", event.target.checked)} />
          <span>确认高风险 diff</span>
        </label>
      </div>
      <Space wrap>
        <Button type="primary" htmlType="button" onClick={() => void applyDraft()} disabled={applyDisabled || loading}>保存 Universe</Button>
        <TextField label="回滚版本" value={rollbackVersion} onChange={(event) => setField("rollbackVersion", event.target.value)} />
        <Button danger htmlType="button" onClick={() => void rollback()} disabled={!rollbackVersion || loading}>回滚</Button>
      </Space>
      <p className="hint">回滚与保存都会写入 quant parameter audit 和 operation audit；自动交易仍受模拟盘权限、风控和确认机制约束。</p>
    </SettingCard>
  );
}

function OverrideEditor({ draft, onChange }: { draft: EtfUniverseOverrideMap; onChange: (draft: EtfUniverseOverrideMap) => void }) {
  const overrides = Object.values(draft);
  if (!overrides.length) {
    return <p className="hint">当前没有 universe 覆盖项。可通过修复向导生成草稿。</p>;
  }
  return (
    <VirtualGrid<EtfUniverseOverride>
      rowKey="symbol"
      dataSource={overrides}
      scroll={{ x: 860 }}
      columns={[
        { title: "代码", dataIndex: "symbol", width: 86 },
        { title: "名称", dataIndex: "name", width: 130 },
        { title: "分类", dataIndex: "category", width: 110 },
        { title: "T0", dataIndex: "t0_eligible", width: 68, render: (value) => <Tag color={value ? "green" : "default"}>{value ? "是" : "否"}</Tag> },
        { title: "启用", dataIndex: "enabled_for_t0", width: 74, render: (value) => <Tag color={value ? "green" : "default"}>{value ? "是" : "否"}</Tag> },
        {
          title: "最低额",
          dataIndex: "min_amount",
          width: 150,
          render: (value, item) => (
            <NumberField
              label="最低额"
              value={String(value ?? "")}
              onChange={(event) => onChange({ ...draft, [item.symbol]: { ...item, min_amount: Number(event.target.value) } })}
            />
          ),
        },
        { title: "备注", dataIndex: "notes", ellipsis: true },
      ]}
    />
  );
}

function severityColor(value: string) {
  if (value === "error") return "red";
  if (value === "warning") return "orange";
  if (value === "info") return "blue";
  return "green";
}

function riskColor(value: string) {
  if (value === "high") return "red";
  if (value === "medium") return "orange";
  return "default";
}
