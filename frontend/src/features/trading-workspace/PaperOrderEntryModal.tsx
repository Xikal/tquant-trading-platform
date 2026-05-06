import type { PaperOrderDraft } from "./workspaceTypes";
import { useEffect, useMemo, useState } from "react";
import { strategiesApi, type StrategyMeta, type SymbolSearchItem } from "../../api/strategies";
import type { PaperPosition } from "../../types";
import { STRATEGY_OPTIONS } from "../../constants/strategies";
import { NumberField, SearchField, SelectField, TextField } from "../../components/shared/FormFields";

export function OrderEntryModal({
  draft,
  setDraft,
  paused,
  autoTradingRunning,
  loading,
  positions,
  onClose,
  onSubmitOrder,
}: {
  draft: PaperOrderDraft;
  setDraft: (draft: PaperOrderDraft) => void;
  paused: boolean;
  autoTradingRunning: boolean;
  loading: boolean;
  positions: PaperPosition[];
  onClose: () => void;
  onSubmitOrder: () => void | Promise<void>;
}) {
  const locked = autoTradingRunning || paused;
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const feeWarning = estimateCommissionWarning(draft);
  const currentPosition = useMemo(() => (
    positions.find((item) => item.symbol.toUpperCase() === draft.symbol.trim().toUpperCase()) ?? null
  ), [draft.symbol, positions]);
  const quickQuantity = resolveQuickQuantity(draft.side, currentPosition);
  const strategyOptions = useMemo(() => {
    if (strategies.length) {
      return [
        { value: "", label: "不绑定策略" },
        ...strategies.map((item) => ({ value: item.key, label: item.display_name || item.name || item.key })),
      ];
    }
    return [
      { value: "", label: "不绑定策略" },
      ...STRATEGY_OPTIONS.map(([value, label]) => ({ value, label })),
    ];
  }, [strategies]);

  useEffect(() => {
    let cancelled = false;
    strategiesApi.getStrategyMeta()
      .then((result) => {
        if (!cancelled) {
          setStrategies(result.strategies ?? []);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  function selectSymbol(item: SymbolSearchItem) {
    const latestPrice = item.latest_price == null ? "" : String(item.latest_price);
    setDraft({
      ...draft,
      symbol: item.symbol,
      name: item.name || draft.name,
      price: draft.price || latestPrice,
      current_price: latestPrice || draft.current_price,
    });
  }

  function setQuickQuantity(ratio: number) {
    const next = roundLot(quickQuantity * ratio);
    if (next > 0) {
      setDraft({ ...draft, quantity: String(next) });
    }
  }

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
        <div className="order-modal-primary">
          <SearchField
            label="标的"
            value={draft.symbol}
            placeholder="输入代码/名称"
            disabled={locked}
            onChange={(value) => setDraft({ ...draft, symbol: value })}
            onSelect={selectSymbol}
          />
          <div className="order-side-switch" aria-label="买卖方向">
            <button
              type="button"
              className={draft.side === "buy" ? "active buy" : "buy"}
              disabled={locked}
              onClick={() => setDraft({ ...draft, side: "buy" })}
            >
              买入
            </button>
            <button
              type="button"
              className={draft.side === "sell" ? "active sell" : "sell"}
              disabled={locked}
              onClick={() => setDraft({ ...draft, side: "sell" })}
            >
              卖出
            </button>
          </div>
          <div className="order-quantity-block">
            <NumberField label="数量" value={draft.quantity} suffix="股" placeholder="100 股整数倍" disabled={locked} onChange={(event) => setDraft({ ...draft, quantity: event.target.value })} />
            <div className="order-quantity-actions" aria-label="数量快捷按钮">
              <button type="button" disabled={locked} onClick={() => setQuickQuantity(1)}>全部</button>
              <button type="button" disabled={locked} onClick={() => setQuickQuantity(0.5)}>半仓</button>
              <button type="button" disabled={locked} onClick={() => setQuickQuantity(0.25)}>1/4仓</button>
            </div>
          </div>
        </div>
        {draft.name ? <p className="hint order-symbol-hint">已选标的：{draft.name} {draft.current_price ? `· 参考价 ${draft.current_price}` : ""}</p> : null}
        <details className="order-modal-extra">
          <summary>更多设置</summary>
          <div className="form-grid order-modal-grid">
            <SelectField
              label="价格类型"
              value={draft.order_type}
              disabled={locked}
              options={[
                { value: "market", label: "市价" },
                { value: "limit", label: "限价" },
              ]}
              onChange={(event) => setDraft({ ...draft, order_type: event.target.value as "market" | "limit" })}
            />
            <NumberField label="委托价" value={draft.price} placeholder="限价单必填" disabled={locked} onChange={(event) => setDraft({ ...draft, price: event.target.value, current_price: event.target.value || draft.current_price })} />
            <SelectField label="策略归属" value={draft.strategy_key} disabled={locked} options={strategyOptions} onChange={(event) => setDraft({ ...draft, strategy_key: event.target.value })} />
            <TextField label="名称" value={draft.name} disabled={locked} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
          </div>
          <TextField fieldClassName="paper-reason" label="备注" value={draft.reason} disabled={locked} onChange={(event) => setDraft({ ...draft, reason: event.target.value })} />
        </details>
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

function resolveQuickQuantity(side: "buy" | "sell", position: PaperPosition | null): number {
  if (side === "sell") {
    return roundLot(position?.available_quantity ?? position?.quantity ?? 0);
  }
  return roundLot(Math.max(position?.quantity ?? 0, 1000));
}

function roundLot(value: number): number {
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }
  return Math.max(100, Math.floor(value / 100) * 100);
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
