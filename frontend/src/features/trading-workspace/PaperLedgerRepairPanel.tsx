import type { PaperLedgerRepairResponse } from "../../types";
import {
  formatMoneyPlain,
  plainTradingText,
  toneFromChange,
} from "./workspaceFormatters";

interface PaperLedgerRepairPanelProps {
  loading: boolean;
  status: PaperLedgerRepairResponse | null;
  onRefresh: () => void;
  onApply: () => void;
}

export function PaperLedgerRepairPanel({
  loading,
  status,
  onRefresh,
  onApply,
}: PaperLedgerRepairPanelProps) {
  const issueCount = status?.issue_count ?? 0;
  const beforeGap = status?.reconciliation_gap_before ?? 0;
  const afterGap = status?.reconciliation_gap_after ?? 0;
  const gapTone = toneFromChange(beforeGap);
  const actionDisabled = loading || issueCount <= 0;

  return (
    <section className="panel paper-ledger-repair">
      <div className="panel-title">
        <h2>账户对账修复</h2>
        <span className="hint">仅管理员可见。检查历史成交是否存在异常多卖、现金漂移或账本不平。</span>
      </div>
      <div className="paper-ledger-repair-summary">
        <div className={`paper-ledger-repair-item ${gapTone}`}>
          <span>当前差额</span>
          <strong>{formatSignedMoney(beforeGap)}</strong>
        </div>
        <div className="paper-ledger-repair-item">
          <span>异常成交</span>
          <strong>{issueCount} 条</strong>
        </div>
        <div className="paper-ledger-repair-item">
          <span>修复后差额</span>
          <strong>{formatSignedMoney(afterGap)}</strong>
        </div>
        <div className="paper-ledger-repair-item">
          <span>重算总资产</span>
          <strong>{formatMoneyWithYuan(status?.corrected_total_assets)}</strong>
        </div>
      </div>
      {status?.issues?.length ? (
        <div className="paper-ledger-repair-issues">
          {status.issues.slice(0, 5).map((item) => (
            <article className="paper-ledger-repair-issue" key={`${item.trade_id}-${item.order_id}`}>
              <strong>{item.symbol} {item.side === "buy" ? "买入" : "卖出"}异常</strong>
              <span>
                原数量 {item.original_quantity} 股，保留 {item.valid_quantity} 股，剔除 {item.invalid_quantity} 股
              </span>
              <small>{plainTradingText(item.reason)}</small>
            </article>
          ))}
        </div>
      ) : (
        <p className="paper-ledger-repair-empty">
          当前未发现异常成交记录。若顶部总盈亏与个股累计盈亏仍不一致，可点击“重新检查”再次校验。
        </p>
      )}
      <div className="paper-ledger-repair-actions">
        <button type="button" className="secondary" onClick={onRefresh} disabled={loading}>
          {loading ? "检查中..." : "重新检查"}
        </button>
        <button type="button" className="primary" onClick={onApply} disabled={actionDisabled}>
          {loading ? "重算中..." : issueCount > 0 ? "一键重算并修复" : "账本已平，无需修复"}
        </button>
      </div>
    </section>
  );
}

function formatSignedMoney(value: number | null | undefined) {
  const amount = value ?? 0;
  const prefix = amount > 0 ? "+" : "";
  return `${prefix}${formatMoneyPlain(amount)}`;
}

function formatMoneyWithYuan(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "--";
  }
  return `¥${formatMoneyPlain(value)}`;
}
