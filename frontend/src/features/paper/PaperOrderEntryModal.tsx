import { useEffect, useMemo, useState } from "react";
import { Button, Modal } from "antd";

import { api } from "../../api/client";
import { strategiesApi, type StrategyMeta, type SymbolSearchItem } from "../../api/strategies";
import { STRATEGY_OPTIONS } from "../../constants/strategies";
import { NumberField, SearchField, SelectField, TextField } from "../../components/shared/FormFields";
import type { LowBuyPriorityBoardItem, PaperPosition } from "../../types";
import { estimateOrderFeeWarning } from "../../utils/orderFeePreview";
import type { PaperOrderDraft } from "../workspace-shared/workspaceTypes";

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
  const [recommended, setRecommended] = useState<LowBuyPriorityBoardItem[]>([]);
  const [recommendedOpen, setRecommendedOpen] = useState(false);
  const [recommendedLoading, setRecommendedLoading] = useState(false);
  const [recommendedError, setRecommendedError] = useState("");
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

  async function loadRecommendedOrders() {
    const nextOpen = !recommendedOpen;
    setRecommendedOpen(nextOpen);
    if (!nextOpen || recommended.length || recommendedLoading) return;
    try {
      setRecommendedLoading(true);
      setRecommendedError("");
      const payload = await api.getLowBuyPriorityBoard(10);
      setRecommended(payload.items.filter((item) => item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now"));
    } catch (error) {
      setRecommendedError(error instanceof Error ? error.message : "今日推荐加载失败");
    } finally {
      setRecommendedLoading(false);
    }
  }

  function importRecommended(item: LowBuyPriorityBoardItem) {
    const price = midpoint(item.entry_zone_low, item.entry_zone_high) ?? item.latest_price;
    setDraft({
      ...draft,
      symbol: item.symbol,
      name: item.name,
      side: "buy",
      order_type: "limit",
      price: price ? String(price.toFixed(3)) : draft.price,
      current_price: item.latest_price ? String(item.latest_price.toFixed(3)) : draft.current_price,
      quantity: draft.quantity || "100",
      strategy_key: item.strategy_key,
      reason: `${item.strategy_title || "今日推荐"}：${item.buy_signal_text || item.action_summary || "优先级榜导入"}`,
    });
    setRecommendedOpen(false);
  }

  function setQuickQuantity(ratio: number) {
    const next = roundLot(quickQuantity * ratio);
    if (next > 0) {
      setDraft({ ...draft, quantity: String(next) });
    }
  }

  return (
    <Modal
      open
      centered
      width={760}
      title="录入模拟委托"
      footer={null}
      onCancel={onClose}
      className={`paper-order-antd-modal${paused ? " paused" : ""}${autoTradingRunning ? " auto-running" : ""}`}
    >
      <section className={`order-modal${paused ? " paused" : ""}${autoTradingRunning ? " auto-running" : ""}`}>
        <div className="order-modal-title">
          <div>
            <span>MECHA ORDER</span>
            <h2>录入模拟委托</h2>
          </div>
        </div>
        {autoTradingRunning ? <p className="muted">自动交易正在运行，手动委托已临时锁定。停止自动交易后可继续录入。</p> : null}
        {paused ? <p className="muted">模拟账户已暂停，恢复后可继续提交。</p> : null}
        <div className="order-import-recommend">
          <Button type="default" disabled={locked} loading={recommendedLoading} onClick={() => void loadRecommendedOrders()}>
            {recommendedLoading ? "读取今日推荐..." : "从今日推荐导入"}
          </Button>
          <span>自动填入代码、限价、策略来源和备注，提交前仍可微调。</span>
        </div>
        {recommendedOpen ? (
          <div className="order-recommend-list">
            {recommendedError ? <p className="warn">{recommendedError}</p> : null}
            {!recommendedError && !recommended.length && !recommendedLoading ? <p className="hint">当前优先榜没有确定买入/小仓试买标的。</p> : null}
            {recommended.map((item) => (
              <Button type="text" key={item.symbol} disabled={locked} onClick={() => importRecommended(item)}>
                <strong>{item.name} {item.symbol}</strong>
                <span>{item.buy_signal_text} · {item.strategy_title}</span>
                <small>买入区间 {formatRange(item.entry_zone_low, item.entry_zone_high)}，止损 {formatPrice(item.stop_loss)}</small>
              </Button>
            ))}
          </div>
        ) : null}
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
            <Button type={draft.side === "buy" ? "primary" : "default"} className={draft.side === "buy" ? "active buy" : "buy"} disabled={locked} onClick={() => setDraft({ ...draft, side: "buy" })}>
              买入
            </Button>
            <Button type={draft.side === "sell" ? "primary" : "default"} className={draft.side === "sell" ? "active sell" : "sell"} disabled={locked} onClick={() => setDraft({ ...draft, side: "sell" })}>
              卖出
            </Button>
          </div>
          <div className="order-quantity-block">
            <NumberField label="数量" value={draft.quantity} suffix="股" placeholder="100 股整数倍" disabled={locked} onChange={(event) => setDraft({ ...draft, quantity: event.target.value })} />
            <div className="order-quantity-actions" aria-label="数量快捷按钮">
              <Button size="small" disabled={locked} onClick={() => setQuickQuantity(1)}>全部</Button>
              <Button size="small" disabled={locked} onClick={() => setQuickQuantity(0.5)}>半仓</Button>
              <Button size="small" disabled={locked} onClick={() => setQuickQuantity(0.25)}>1/4仓</Button>
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
          <Button type="default" onClick={onClose}>取消</Button>
          <Button type="primary" onClick={onSubmitOrder} loading={loading} disabled={locked}>
            {autoTradingRunning ? "自动交易中" : loading ? "提交中..." : "提交模拟委托"}
          </Button>
        </div>
      </section>
    </Modal>
  );
}

function midpoint(low?: number | null, high?: number | null): number | null {
  if (typeof low === "number" && Number.isFinite(low) && typeof high === "number" && Number.isFinite(high)) {
    return (low + high) / 2;
  }
  return null;
}

function formatRange(low?: number | null, high?: number | null): string {
  if (typeof low !== "number" || !Number.isFinite(low) || typeof high !== "number" || !Number.isFinite(high)) {
    return "--";
  }
  return `¥${low.toFixed(3)} - ¥${high.toFixed(3)}`;
}

function formatPrice(value?: number | null): string {
  return typeof value === "number" && Number.isFinite(value) ? `¥${value.toFixed(3)}` : "--";
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
  return estimateOrderFeeWarning({
    symbol: draft.symbol,
    side: draft.side,
    quantity: draft.quantity || "0",
    price: draft.price || draft.current_price || "0",
  });
}
