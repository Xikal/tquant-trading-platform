import { Alert, Tag } from "antd";
import type { DecisionContextAttribution, DecisionContextGateContribution, DecisionContextOutcome } from "../../types";
import { DataTable } from "../../ui/table/DataTable";
import { formatPct } from "../workspace-shared/workspaceFormatters";

export function SignalAttributionPanel({ context }: { context?: DecisionContextAttribution }) {
  const payload = context ?? {};
  const reasons = payload.reasons ?? [];
  return (
    <section className="strategy-tracking-detail-section">
      <div className="strategy-tracking-review-head">
        <strong>决策上下文</strong>
        <span>{payload.status === "ok" ? `相似样本 ${payload.similar_history_sample_count ?? 0}` : "暂无归因快照"}</span>
      </div>
      {reasons.length ? <Alert type="warning" showIcon title={reasons.join("；")} /> : null}
      <div className="strategy-tracking-tag-row">
        <Tag color={payload.production_eligible ? "green" : "default"}>{payload.production_eligible ? "生产可追溯" : "研究态"}</Tag>
        <Tag>{payload.strategy_tier || "tier 缺失"}</Tag>
        <Tag>{payload.final_decision || "无最终决策"}</Tag>
        <Tag>{payload.data_quality || "missing"}</Tag>
      </div>
      <DataTable<DecisionContextOutcome>
        rowKey="horizon_days"
        dataSource={payload.outcomes ?? []}
        columns={[
          { title: "信号归因", dataIndex: "horizon_days", width: 96, render: (value) => `${value}日` },
          { title: "收益", dataIndex: "return_pct", width: 88, render: (value) => formatPct(value) },
          { title: "最高", dataIndex: "max_gain_pct", width: 88, render: (value) => formatPct(value) },
          { title: "回撤", dataIndex: "max_drawdown_pct", width: 88, render: (value) => formatPct(value) },
          { title: "结果", dataIndex: "hit", width: 80, render: (value) => (value ? <Tag color="green">命中</Tag> : <Tag color="orange">未命中</Tag>) },
        ]}
        emptyText="信号归因尚未生成"
        scroll={{ x: 480 }}
        defaultScrollY={220}
      />
      <div className="strategy-tracking-context-gates">
        {(payload.gate_contributions ?? []).map((item) => (
          <GateContributionTag key={item.gate} item={item} />
        ))}
      </div>
    </section>
  );
}

function GateContributionTag({ item }: { item: DecisionContextGateContribution }) {
  const reason = item.reasons[0] || gateName(item.gate);
  return (
    <Tag color={gateTone(item.effect)} title={item.reasons.join("；")}>
      {gateName(item.gate)} · {item.decision} · {reason}
    </Tag>
  );
}

function gateName(value: string): string {
  return {
    market_gate: "市场",
    sector_leader_gate: "板块",
    hard_risk_gate: "避坑",
    event_risk_gate: "事件",
    intraday_entry_gate: "分钟",
  }[value] ?? value;
}

function gateTone(effect: string): string {
  if (effect === "positive") return "green";
  if (effect === "negative") return "gold";
  if (effect === "blocked") return "red";
  return "default";
}
