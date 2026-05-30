import { Collapse, Space, Typography } from "antd";
import type { PaperPortfolioExecutionPreview, PaperPortfolioMetrics } from "../../types";
import { DataTable } from "../../ui/table/DataTable";
import { EmptyState, InfoPill } from "../workspace-shared/WorkspaceComponents";
import { formatInteger, formatPct, toneFromChange } from "../workspace-shared/workspaceFormatters";

export function PortfolioExecutionPanel({ preview }: { preview?: PaperPortfolioExecutionPreview }) {
  const rows = preview ? [preview.max_5, preview.max_10] : [];
  return (
    <Collapse
      size="small"
      items={[{
        key: "portfolio-execution-preview",
        label: `组合执行预览 · ${preview?.candidate_count ?? 0} 个闭合样本`,
        children: (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Space wrap size={[6, 6]}>
              <InfoPill compact label="口径" value={preview?.capital_model_label || "真实组合执行预览"} />
              <InfoPill compact label="来源" value={preview?.source || "paper_trades"} />
              <InfoPill compact label="跳过原因" value={Object.keys(preview?.skip_reason_counts ?? {}).length ? "已统计" : "无跳过"} />
            </Space>
            <DataTable<PaperPortfolioMetrics>
              rowKey={(item) => item.capital_model}
              dataSource={rows}
              defaultScrollY={220}
              locale={{ emptyText: <EmptyState text="暂无可执行组合预览样本" /> }}
              columns={[
                { title: "组合", dataIndex: "capital_model_label", width: 150 },
                { title: "候选", dataIndex: "candidate_count", width: 80, align: "right", render: (value) => formatInteger(value) },
                { title: "成交", dataIndex: "trade_count", width: 80, align: "right", render: (value) => formatInteger(value) },
                { title: "跳过", dataIndex: "skipped_count", width: 80, align: "right", render: (value) => formatInteger(value) },
                { title: "收益", dataIndex: "portfolio_return_pct", width: 90, align: "right", render: (value) => <span className={toneFromChange(value)}>{formatPct(value)}</span> },
                { title: "回撤", dataIndex: "max_drawdown_pct", width: 90, align: "right", render: (value) => formatPct(value) },
                { title: "PF", dataIndex: "profit_factor", width: 80, align: "right" },
                { title: "资金占用", dataIndex: "avg_capital_utilization_pct", width: 100, align: "right", render: (value) => formatPct(value) },
              ]}
              scroll={{ x: 820 }}
            />
            <SkipReasonText counts={preview?.skip_reason_counts ?? {}} />
            {preview?.notes?.[0] ? <Typography.Text type="secondary" style={{ fontSize: 11 }}>{preview.notes[0]}</Typography.Text> : null}
          </Space>
        ),
      }]}
    />
  );
}

function SkipReasonText({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (!entries.length) {
    return <Typography.Text type="secondary" style={{ fontSize: 11 }}>当前闭合样本未触发组合跳过约束。</Typography.Text>;
  }
  return (
    <Typography.Text type="secondary" style={{ fontSize: 11 }}>
      跳过原因：{entries.map(([key, value]) => `${key} ${value}`).join(" / ")}
    </Typography.Text>
  );
}
