import { useEffect, useMemo, type CSSProperties } from "react";
import { Alert, Button, Collapse, Col, Modal, Row, Typography } from "antd";
import { api } from "../../api/client";
import { strategiesApi, type SymbolSearchItem } from "../../api/strategies";
import { STRATEGY_OPTIONS } from "../../constants/strategies";
import { NumberField, SearchField, SelectField, TextField } from "../../components/shared/FormFields";
import type { LowBuyPriorityBoardItem, PaperPosition } from "../../types";
import { estimateOrderFeeWarning } from "../../utils/orderFeePreview";
import type { PaperOrderDraft } from "../workspace-shared/workspaceTypes";
import { usePaperUiStore } from "../../stores/paperUiStore";

const MODAL_BODY_STYLE: CSSProperties = {
  padding: 16,
};

const ROOT_STYLE: CSSProperties = {
  display: "grid",
  gap: 12,
};

const KICKER_STYLE: CSSProperties = {
  color: "rgba(100, 116, 139, 0.9)",
  fontFamily: '"IBM Plex Mono", "SFMono-Regular", monospace',
  fontSize: 10,
  fontWeight: 900,
  letterSpacing: "0.14em",
};

const INTRO_ROW_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  flexWrap: "wrap",
};

const RECOMMEND_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 8,
  padding: 12,
  border: "1px solid rgba(214, 165, 92, 0.22)",
  borderRadius: 12,
  background: "#f8fafc",
};

const RECOMMEND_ITEM_STYLE: CSSProperties = {
  display: "grid",
  gap: 2,
  width: "100%",
  height: "auto",
  padding: "8px 10px",
  textAlign: "left",
  justifyItems: "start",
  borderRadius: 10,
  border: "1px solid rgba(100, 116, 139, 0.18)",
  background: "#fff",
  whiteSpace: "normal",
};

const SWITCH_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 7,
};

const QUANTITY_BLOCK_STYLE: CSSProperties = {
  display: "grid",
  gap: 7,
};

const QUANTITY_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
  gap: 6,
};

const ACTIONS_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  gap: 8,
  flexWrap: "wrap",
};

const HINT_STYLE: CSSProperties = {
  margin: 0,
};

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
  const strategies = usePaperUiStore((state) => state.orderStrategies);
  const recommended = usePaperUiStore((state) => state.recommendedOrders);
  const recommendedOpen = usePaperUiStore((state) => state.recommendedOrdersOpen);
  const recommendedLoading = usePaperUiStore((state) => state.recommendedOrdersLoading);
  const recommendedError = usePaperUiStore((state) => state.recommendedOrdersError);
  const setStrategies = usePaperUiStore((state) => state.setOrderStrategies);
  const setRecommended = usePaperUiStore((state) => state.setRecommendedOrders);
  const setRecommendedOpen = usePaperUiStore((state) => state.setRecommendedOrdersOpen);
  const setRecommendedLoading = usePaperUiStore((state) => state.setRecommendedOrdersLoading);
  const setRecommendedError = usePaperUiStore((state) => state.setRecommendedOrdersError);
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
      styles={{ body: MODAL_BODY_STYLE }}
      destroyOnHidden
    >
      <section style={ROOT_STYLE}>
        <Typography.Text style={KICKER_STYLE}>MECHA ORDER</Typography.Text>

        {autoTradingRunning ? (
          <Alert type="warning" showIcon message="自动交易正在运行，手动委托已临时锁定。停止自动交易后可继续录入。" />
        ) : null}
        {paused ? <Alert type="info" showIcon message="模拟账户已暂停，恢复后可继续提交。" /> : null}

        <div style={INTRO_ROW_STYLE}>
          <Button type="default" disabled={locked} loading={recommendedLoading} onClick={() => void loadRecommendedOrders()}>
            {recommendedLoading ? "读取今日推荐..." : "从今日推荐导入"}
          </Button>
          <Typography.Text type="secondary">自动填入代码、限价、策略来源和备注，提交前仍可微调。</Typography.Text>
        </div>

        {recommendedOpen ? (
          <div style={RECOMMEND_LIST_STYLE}>
            {recommendedError ? <Alert type="error" showIcon message={recommendedError} /> : null}
            {!recommendedError && !recommended.length && !recommendedLoading ? (
              <Typography.Text type="secondary">当前优先榜没有确定买入/小仓试买标的。</Typography.Text>
            ) : null}
            {recommended.map((item) => (
              <Button
                type="text"
                key={item.symbol}
                disabled={locked}
                onClick={() => importRecommended(item)}
                style={RECOMMEND_ITEM_STYLE}
              >
                <Typography.Text strong style={{ lineHeight: 1.2 }}>
                  {item.name} {item.symbol}
                </Typography.Text>
                <Typography.Text type="secondary">
                  {item.buy_signal_text} · {item.strategy_title}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  买入区间 {formatRange(item.entry_zone_low, item.entry_zone_high)}，止损 {formatPrice(item.stop_loss)}
                </Typography.Text>
              </Button>
            ))}
          </div>
        ) : null}

        <Row gutter={[12, 12]} align="top">
          <Col xs={24} lg={10}>
            <SearchField
              label="标的"
              value={draft.symbol}
              placeholder="输入代码/名称"
              disabled={locked}
              onChange={(value) => setDraft({ ...draft, symbol: value })}
              onSelect={selectSymbol}
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <div style={SWITCH_GRID_STYLE} aria-label="买卖方向">
              <Button
                type={draft.side === "buy" ? "primary" : "default"}
                disabled={locked}
                onClick={() => setDraft({ ...draft, side: "buy" })}
                style={{ minHeight: 32, borderRadius: 8, fontWeight: 900 }}
              >
                买入
              </Button>
              <Button
                type={draft.side === "sell" ? "primary" : "default"}
                disabled={locked}
                onClick={() => setDraft({ ...draft, side: "sell" })}
                style={{ minHeight: 32, borderRadius: 8, fontWeight: 900 }}
              >
                卖出
              </Button>
            </div>
          </Col>
          <Col xs={24} sm={12} lg={8}>
            <div style={QUANTITY_BLOCK_STYLE}>
              <NumberField
                label="数量"
                value={draft.quantity}
                suffix="股"
                placeholder="100 股整数倍"
                disabled={locked}
                onChange={(event) => setDraft({ ...draft, quantity: event.target.value })}
              />
              <div style={QUANTITY_GRID_STYLE} aria-label="数量快捷按钮">
                <Button size="small" disabled={locked} onClick={() => setQuickQuantity(1)}>
                  全部
                </Button>
                <Button size="small" disabled={locked} onClick={() => setQuickQuantity(0.5)}>
                  半仓
                </Button>
                <Button size="small" disabled={locked} onClick={() => setQuickQuantity(0.25)}>
                  1/4仓
                </Button>
              </div>
            </div>
          </Col>
        </Row>

        {draft.name ? (
          <Typography.Text type="secondary" style={HINT_STYLE}>
            已选标的：{draft.name} {draft.current_price ? `· 参考价 ${draft.current_price}` : ""}
          </Typography.Text>
        ) : null}

        <Collapse
          ghost
          defaultActiveKey={[]}
          items={[
            {
              key: "advanced",
              label: "更多设置",
              children: (
                <div style={{ display: "grid", gap: 12 }}>
                  <Row gutter={[12, 12]}>
                    <Col xs={24} sm={12}>
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
                    </Col>
                    <Col xs={24} sm={12}>
                      <NumberField
                        label="委托价"
                        value={draft.price}
                        placeholder="限价单必填"
                        disabled={locked}
                        onChange={(event) => setDraft({ ...draft, price: event.target.value, current_price: event.target.value || draft.current_price })}
                      />
                    </Col>
                    <Col xs={24} sm={12}>
                      <SelectField
                        label="策略归属"
                        value={draft.strategy_key}
                        disabled={locked}
                        options={strategyOptions}
                        onChange={(event) => setDraft({ ...draft, strategy_key: event.target.value })}
                      />
                    </Col>
                    <Col xs={24} sm={12}>
                      <TextField
                        label="名称"
                        value={draft.name}
                        disabled={locked}
                        onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                      />
                    </Col>
                  </Row>
                  <TextField
                    label="备注"
                    value={draft.reason}
                    disabled={locked}
                    onChange={(event) => setDraft({ ...draft, reason: event.target.value })}
                  />
                </div>
              ),
            },
          ]}
        />

        {feeWarning ? <Alert type="warning" showIcon message={feeWarning} /> : null}

        <div style={ACTIONS_STYLE}>
          <Button type="default" onClick={onClose}>
            取消
          </Button>
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
