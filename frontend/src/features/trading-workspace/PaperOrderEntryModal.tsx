import type { PaperOrderDraft } from "./workspaceTypes";
import { NumberField, SelectField, TextField } from "../../components/shared/FormFields";

export function OrderEntryModal({
  draft,
  setDraft,
  paused,
  autoTradingRunning,
  loading,
  onClose,
  onSubmitOrder,
}: {
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  paused: boolean;
  autoTradingRunning: boolean;
  loading: boolean;
  onClose: () => void;
  onSubmitOrder: () => void | Promise<void>;
}) {
  const locked = autoTradingRunning || paused;
  const feeWarning = estimateCommissionWarning(draft);
  return (
    <div className="order-modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className={`order-modal${paused ? " paused" : ""}${autoTradingRunning ? " auto-running" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="paper-order-modal-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="order-modal-title">
          <div>
            <span>MECHA ORDER</span>
            <h2 id="paper-order-modal-title">录入模拟委托</h2>
          </div>
          <button type="button" className="order-modal-close" onClick={onClose} aria-label="关闭委托弹窗">×</button>
        </div>
        {autoTradingRunning ? <p className="muted">自动交易正在运行，手动委托已临时锁定。停止自动交易后可继续录入。</p> : null}
        {paused ? <p className="muted">模拟账户已暂停，恢复后可继续提交。</p> : null}
        <div className="form-grid order-modal-grid">
          <TextField label="代码" value={draft.symbol} disabled={locked} onChange={(event) => setDraft({ ...draft, symbol: event.target.value })} />
          <TextField label="名称" value={draft.name} disabled={locked} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
          <SelectField
            label="方向"
            value={draft.side}
            disabled={locked}
            options={[
              { value: "buy", label: "买入" },
              { value: "sell", label: "卖出" },
            ]}
            onChange={(event) => setDraft({ ...draft, side: event.target.value as "buy" | "sell" })}
          />
          <SelectField
            label="委托类型"
            value={draft.order_type}
            disabled={locked}
            options={[
              { value: "market", label: "市价" },
              { value: "limit", label: "限价" },
            ]}
            onChange={(event) => setDraft({ ...draft, order_type: event.target.value as "market" | "limit" })}
          />
          <NumberField label="数量" value={draft.quantity} placeholder="100 股整数倍" disabled={locked} onChange={(event) => setDraft({ ...draft, quantity: event.target.value })} />
          <NumberField label="限价" value={draft.price} placeholder="限价单必填" disabled={locked} onChange={(event) => setDraft({ ...draft, price: event.target.value })} />
          <NumberField label="撮合现价" value={draft.current_price} disabled={locked} onChange={(event) => setDraft({ ...draft, current_price: event.target.value })} />
          <TextField label="策略来源" value={draft.strategy_key} placeholder="如 first_board" disabled={locked} onChange={(event) => setDraft({ ...draft, strategy_key: event.target.value })} />
        </div>
        <TextField fieldClassName="paper-reason" label="执行理由" value={draft.reason} disabled={locked} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} />
        <SelectField
          fieldClassName="paper-reason"
          label="盘中确认"
          value={draft.require_intraday_confirmation ? "yes" : "no"}
          disabled={locked}
          options={[
            { value: "no", label: "不强制确认" },
            { value: "yes", label: "买入前必须承接确认" },
          ]}
          onChange={(event) => setDraft({ ...draft, require_intraday_confirmation: event.target.value === "yes" })}
        />
        {feeWarning ? <p className="warn paper-fee-warning">{feeWarning}</p> : null}
        <div className="order-modal-actions">
          <button type="button" className="ghost-button" onClick={onClose}>取消</button>
          <button type="button" className="primary-button primary" onClick={onSubmitOrder} disabled={loading || locked}>
            {autoTradingRunning ? "自动交易中" : loading ? "提交中..." : "提交模拟委托"}
          </button>
        </div>
      </section>
    </div>
  );
}

function estimateCommissionWarning(draft: PaperOrderDraft): string {
  const quantity = Number(draft.quantity || 0);
  const price = Number(draft.price || draft.current_price || 0);
  const amount = quantity * price;
  if (!Number.isFinite(amount) || amount <= 0) return "";
  const commission = Math.max(amount * 0.00025, 5);
  const stampTax = draft.side === "sell" ? amount * 0.0005 : 0;
  const transferFee = amount * 0.00001;
  const rate = (commission + stampTax + transferFee) / amount;
  if (rate >= 0.01) return "手续费占比超过 1%，单笔金额偏小，容易吞噬收益。";
  if (rate >= 0.005) return "手续费占比超过 0.5%，建议合并小额委托。";
  return "";
}
