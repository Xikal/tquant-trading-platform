import type { LowBuyScreenerResult } from "../../types";
import { EmptyState, InfoPill, MetricGrid, PanelTitle, StockCard } from "./WorkspaceComponents";
import { PRODUCTION_PLAYBOOK_TABS } from "./workspaceConstants";
import { candidateToCard } from "./workspaceViewModels";
import { formatNumber, formatPct, strategyLabel, toneFromChange } from "./workspaceFormatters";
import type { MetricItem, StockCardView } from "./workspaceTypes";

export function PlaybookPage({
  strategy,
  setStrategy,
  playbook,
  loading,
  onRefresh,
  onAnalyze,
  onSelect,
  strategyTabs,
}: {
  strategy: string;
  setStrategy: (strategy: string) => void;
  playbook: LowBuyScreenerResult | null;
  loading: string;
  onRefresh: () => void;
  onAnalyze: (stock: StockCardView) => void;
  onSelect: (stock: StockCardView) => void;
  strategyTabs?: Array<{ key: string; label: string }>;
}) {
  const tabs = strategyTabs?.length ? strategyTabs : (
    PRODUCTION_PLAYBOOK_TABS.map((tab) => ({ key: tab.key, label: tab.label }))
  );
  const allCandidates = uniqueCandidates([
    ...(playbook?.confirmed_candidates ?? []),
    ...(playbook?.candidates ?? []),
  ]);
  const buyNow = allCandidates.filter((item) => item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now").map(candidateToCard);
  const nearEntry = allCandidates.filter((item) => item.buy_signal_state === "near_entry").map(candidateToCard);
  const watch = allCandidates.filter((item) => item.buy_signal_state === "watch").map(candidateToCard);
  const avoid = allCandidates.filter((item) => item.buy_signal_state === "avoid").map(candidateToCard);
  const passiveCandidates = [...watch, ...avoid].slice(0, 12);
  const focus = buyNow[0] ?? nearEntry[0] ?? watch[0] ?? avoid[0];
  const strategyName = tabLabel(strategy, tabs) || strategyLabel(strategy);
  const loadedStrategyName = playbook?.strategy_title || tabLabel(playbook?.strategy_key || strategy, tabs) || strategyLabel(playbook?.strategy_key || strategy);
  const switchingText = playbook && playbook.strategy_key !== strategy ? "，正在切换数据" : "";
  const hasInsufficientData = playbook?.performance?.data_insufficient || (playbook?.performance?.filled_signals ?? 0) <= 0;
  const hitRateDisplay = hasInsufficientData ? "样本不足" : formatPct(playbook?.performance?.hit_rate);
  const hitRateTone: MetricItem["tone"] = hasInsufficientData ? "neutral" : "up";
  const marketAttributionText = summarizeMarketAttribution(playbook?.performance?.market_state_attribution ?? []);
  return (
    <section className="page-grid playbook-grid">
      <div className="panel playbook-hero">
        <PanelTitle
          title="选股宝典"
          actions={<button onClick={onRefresh} disabled={loading === "playbook"}>刷新全量结果</button>}
        />
        <p className="hint">全量深筛 + 策略归因 + 买点执行。候选分层展示，避免把所有机会做成同等权重。</p>
        <div className="tabs">
          {tabs.map((tab) => (
            <button key={tab.key} className={strategy === tab.key ? "active" : ""} onClick={() => setStrategy(tab.key)}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <MetricGrid
        className="summary-panel playbook-metrics"
        items={[
          { label: "立即处理", value: String(buyNow.length), tone: buyNow.length ? "up" : "neutral" },
          { label: "重点观察", value: String(nearEntry.length), tone: nearEntry.length ? "warn" : "neutral" },
          { label: "仅跟踪", value: String(watch.length), tone: "neutral" },
          { label: "今日放弃", value: String(avoid.length), tone: avoid.length ? "down" : "neutral" },
          { label: "全量深筛", value: String(playbook?.scanned_count ?? "--"), tone: "neutral" },
          { label: "5日达标率", value: hitRateDisplay, tone: hitRateTone },
        ]}
      />
      <div className="panel playbook-performance">
        <PanelTitle title="最近表现" />
        <p>当前策略：{strategyName}；已加载：{loadedStrategyName}{switchingText}</p>
        <p>近5日 达标率 {hitRateDisplay}　平均收益 {formatPct(playbook?.performance?.avg_return_5d)}　回撤 {formatPct(playbook?.performance?.avg_max_drawdown_5d)}　盈亏比 {formatNumber(playbook?.performance?.profit_factor)}</p>
        <p>尾部风险 CVaR {formatPct(playbook?.performance?.cvar_5pct)}　半凯利参考 {formatPct(playbook?.performance?.kelly_half_position_pct, 1)}　平均盈利/亏损 {formatPct(playbook?.performance?.avg_win_pct)} / {formatPct(playbook?.performance?.avg_loss_pct)}</p>
        <p>板块归因：{playbook?.hot_industries?.slice(0, 3).join("、") || "--"}</p>
        <p>市场状态：{playbook?.market_state_category_text || playbook?.market_state_text || "--"}</p>
        <p>分市场表现：{marketAttributionText}</p>
        <p>执行口径：只展示当前策略命中的股票，确定买入必须同时满足价格区间、承接确认和风控条件。</p>
      </div>
      <aside className="panel dark playbook-focus">
        <PanelTitle title="今日主看" />
        {focus ? (
          <>
            <p>主看：{focus.name} {focus.symbol}，{focus.actionText}，{focus.details}</p>
            <InfoPill label="主线轮动" value={playbook?.hot_industries?.slice(0, 4).join(" / ") || "--"} />
            <InfoPill label="执行顺序" value="先确定买入，再看接近买点，失效立即降级" />
            <InfoPill label="盘后复盘入口" value="自动归档触发价、失效价和执行结果" />
          </>
        ) : <EmptyState text="当前策略暂无主看标的。" />}
      </aside>
      <CandidateSection className="playbook-buy" title="确定买入" items={buyNow} empty="当前没有确定买入的股票" onAnalyze={onAnalyze} onSelect={onSelect} />
      <CandidateSection className="playbook-near" title="接近买点" items={nearEntry} empty="当前没有接近买点的股票" onAnalyze={onAnalyze} onSelect={onSelect} />
      <div className="panel playbook-watch">
        <PanelTitle title="继续观察 / 历史复盘 / 弹窗" />
        <InfoPill label="收盘复盘" value={`样本交易日 ${playbook?.latest_trade_date ?? "--"} / 缓存 ${playbook?.full_scan_ready ? "已就绪" : "生成中"}`} />
        <div className="stock-list compact">
          {passiveCandidates.length ? passiveCandidates.map((stock) => (
            <StockCard
              key={stock.symbol}
              stock={stock}
              actions={["详情", "分析"]}
              onAction={(action) => (action === "分析" ? onAnalyze(stock) : onSelect(stock))}
            />
          )) : <EmptyState text="这一档为空，说明当前结构要么未到位，要么质量不足。" />}
        </div>
      </div>
    </section>
  );
}

function tabLabel(strategyKey: string | undefined, tabs: Array<{ key: string; label: string }>) {
  if (!strategyKey) {
    return "";
  }
  return tabs.find((tab) => tab.key === strategyKey)?.label || "";
}

function uniqueCandidates(items: LowBuyScreenerResult["candidates"]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (!item.symbol || seen.has(item.symbol)) {
      return false;
    }
    seen.add(item.symbol);
    return true;
  });
}

function summarizeMarketAttribution(buckets: NonNullable<LowBuyScreenerResult["performance"]>["market_state_attribution"]) {
  if (!buckets.length) {
    return "--";
  }
  return buckets
    .slice(0, 4)
    .map((bucket) => `${bucket.label} 样本${bucket.sample_count} / 3日${formatPct(bucket.avg_return_3d)} / 胜率${formatPct(bucket.hit_rate, 0)}`)
    .join(" ｜ ");
}

function CandidateSection({
  title,
  items,
  empty,
  onAnalyze,
  onSelect,
  className = "",
}: {
  title: string;
  items: StockCardView[];
  empty: string;
  onAnalyze: (stock: StockCardView) => void;
  onSelect: (stock: StockCardView) => void;
  className?: string;
}) {
  return (
    <div className={`panel ${className}`}>
      <PanelTitle title={title} />
      <div className="stock-list compact">
        {items.length ? items.map((stock) => (
          <StockCard
            key={`${title}-${stock.symbol}`}
            stock={stock}
            actions={["详情", "已买入", "分析"]}
            onAction={(action) => (action === "分析" ? onAnalyze(stock) : onSelect(stock))}
          />
        )) : <EmptyState text={empty} />}
      </div>
    </div>
  );
}
