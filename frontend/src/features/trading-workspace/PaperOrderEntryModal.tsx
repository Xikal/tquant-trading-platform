import type { PaperOrderDraft } from "./workspaceTypes";

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
          <OrderInput label="代码" value={draft.symbol} disabled={locked} onChange={(value) => setDraft({ ...draft, symbol: value })} />
          <OrderInput label="名称" value={draft.name} disabled={locked} onChange={(value) => setDraft({ ...draft, name: value })} />
          <label>
            <span>方向</span>
            <select value={draft.side} disabled={locked} onChange={(event) => setDraft({ ...draft, side: event.target.value as "buy" | "sell" })}>
              <option value="buy">买入</option>
              <option value="sell">卖出</option>
            </select>
          </label>
          <label>
            <span>委托类型</span>
            <select value={draft.order_type} disabled={locked} onChange={(event) => setDraft({ ...draft, order_type: event.target.value as "market" | "limit" })}>
              <option value="market">市价</option>
              <option value="limit">限价</option>
            </select>
          </label>
          <OrderInput label="数量" value={draft.quantity} placeholder="100 股整数倍" inputMode="numeric" disabled={locked} onChange={(value) => setDraft({ ...draft, quantity: value })} />
          <OrderInput label="限价" value={draft.price} placeholder="限价单必填" inputMode="decimal" disabled={locked} onChange={(value) => setDraft({ ...draft, price: value })} />
          <OrderInput label="撮合现价" value={draft.current_price} inputMode="decimal" disabled={locked} onChange={(value) => setDraft({ ...draft, current_price: value })} />
          <OrderInput label="策略来源" value={draft.strategy_key} placeholder="如 first_board" disabled={locked} onChange={(value) => setDraft({ ...draft, strategy_key: value })} />
        </div>
        <label className="select-field paper-reason">
          <span>执行理由</span>
          <input value={draft.reason} disabled={locked} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} />
        </label>
        <label className="select-field paper-reason">
          <span>盘中确认</span>
          <select
            value={draft.require_intraday_confirmation ? "yes" : "no"}
            disabled={locked}
            onChange={(event) => setDraft({ ...draft, require_intraday_confirmation: event.target.value === "yes" })}
          >
            <option value="no">不强制确认</option>
            <option value="yes">买入前必须承接确认</option>
          </select>
        </label>
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

function OrderInput({
  label,
  value,
  placeholder,
  inputMode,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  inputMode?: "numeric" | "decimal";
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input
        value={value}
        placeholder={placeholder}
        inputMode={inputMode}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
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
