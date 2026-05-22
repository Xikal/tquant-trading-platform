import type { LowBuyScreenerResult } from "../../types";
import { Button, Tabs } from "antd";
import { playbookActionLabel } from "../../utils/uxClarity";
import { EmptyState, InfoPill, MetricGrid, PanelTitle, StockCard } from "../workspace-shared/WorkspaceComponents";
import { WEB_PLAYBOOK_TABS } from "../workspace-shared/workspaceConstants";
import { candidateToCard } from "../workspace-shared/workspaceViewModels";
import { formatNumber, formatPct, strategyLabel, toneFromChange } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView } from "../workspace-shared/workspaceTypes";

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
    WEB_PLAYBOOK_TABS.map((tab) => ({ key: tab.key, label: tab.label }))
  );
  const allCandidates = uniqueCandidates([
    ...(playbook?.confirmed_candidates ?? []),
    ...(playbook?.candidates ?? []),
  ]);
  const buyNow = allCandidates.filter((item) => item.buy_signal_state === "buy_now" || item.buy_signal_state === "soft_buy_now").map(candidateToCard);
  const observeConfirmed = allCandidates.filter((item) => item.buy_signal_state === "observe_confirmed").map(candidateToCard);
  const nearEntry = allCandidates.filter((item) => item.buy_signal_state === "near_entry").map(candidateToCard);
  const watch = allCandidates.filter((item) => item.buy_signal_state === "watch").map(candidateToCard);
  const avoid = allCandidates.filter((item) => item.buy_signal_state === "avoid").map(candidateToCard);
  const passiveCandidates = [...watch, ...avoid].slice(0, 12);
  const executableCount = buyNow.length + observeConfirmed.length + nearEntry.length;
  const focus = buyNow[0] ?? observeConfirmed[0] ?? nearEntry[0] ?? watch[0];
  const strategyName = tabLabel(strategy, tabs) || strategyLabel(strategy);
  const loadedStrategyName = playbook?.strategy_title || tabLabel(playbook?.strategy_key || strategy, tabs) || strategyLabel(playbook?.strategy_key || strategy);
  const switchingText = playbook && playbook.strategy_key !== strategy ? "，正在切换数据" : "";
  const hasInsufficientData = playbook?.performance?.data_insufficient || (playbook?.performance?.filled_signals ?? 0) <= 0;
  const hitRateDisplay = hasInsufficientData ? "样本不足" : formatPct(playbook?.performance?.hit_rate);
  const hitRateTone: MetricItem["tone"] = hasInsufficientData ? "neutral" : "up";
  const sampleReason = sampleInsufficientReason(playbook?.strategy_key || strategy, playbook);
  const marketAttributionText = summarizeMarketAttribution(playbook?.performance?.market_state_attribution ?? []);
  return (
    <section className="page-grid playbook-grid">
      <div className="panel playbook-hero">
        <PanelTitle
          title="选股宝典"
          actions={<Button onClick={onRefresh} loading={loading === "playbook"}>刷新全量结果</Button>}
        />
        <p className="hint">全量深筛 + 策略归因 + 买点执行。候选分层展示，避免把所有机会做成同等权重。</p>
        <div className="strategy-purpose-strip">
          <strong>{strategyName}</strong>
          <span>{strategyPurpose(strategy)}</span>
        </div>
        <Tabs
          className="playbook-strategy-tabs"
          activeKey={strategy}
          onChange={setStrategy}
          tabBarGutter={6}
          items={tabs.map((tab) => ({
            key: tab.key,
            label: (
              <span className="playbook-tab-label">
                <strong>{tab.label}</strong>
              </span>
            ),
          }))}
        />
      </div>
      <MetricGrid
        className="summary-panel playbook-metrics"
        items={[
          { label: playbookActionLabel("buy_now"), value: String(buyNow.length), tone: buyNow.length ? "up" : "neutral" },
          { label: playbookActionLabel("observe_confirmed"), value: String(observeConfirmed.length), tone: observeConfirmed.length ? "warn" : "neutral" },
          { label: playbookActionLabel("near_entry"), value: String(nearEntry.length), tone: nearEntry.length ? "warn" : "neutral" },
          { label: playbookActionLabel("watch"), value: String(watch.length), tone: "neutral" },
          { label: playbookActionLabel("avoid"), value: String(avoid.length), tone: avoid.length ? "down" : "neutral" },
          { label: "全量深筛", value: String(playbook?.scanned_count ?? "--"), tone: "neutral" },
          { label: "真实成交样本", value: String(playbook?.performance?.filled_signals ?? 0), tone: hasInsufficientData ? "warn" : "up" },
          { label: "数据状态", value: playbook?.data_quality_text ?? "--", tone: dataQualityTone(playbook?.data_quality) },
          { label: "5日达标率", value: hitRateDisplay, tone: hitRateTone },
        ]}
      />
      <div className="panel playbook-performance">
        <PanelTitle title="最近表现" />
        <p>当前策略：{strategyName}；已加载：{loadedStrategyName}{switchingText}</p>
        <p>近5日 达标率 {hitRateDisplay}　平均收益 {formatPct(playbook?.performance?.avg_return_5d)}　回撤 {formatPct(playbook?.performance?.avg_max_drawdown_5d)}　赚亏比 {formatNumber(playbook?.performance?.profit_factor)}</p>
        {hasInsufficientData ? <p>样本说明：{sampleReason}</p> : null}
        <p>样本规模：信号 {playbook?.performance?.signal_count ?? 0}　已评估 {playbook?.performance?.evaluated_signals ?? 0}　真实成交 {playbook?.performance?.filled_signals ?? 0}　未成交 {playbook?.performance?.not_filled_signals ?? 0}</p>
        <p>1/2/3/4/5日胜率：{formatPct(playbook?.performance?.win_rate_1d, 0)} / {formatPct(playbook?.performance?.win_rate_2d, 0)} / {formatPct(playbook?.performance?.win_rate_3d, 0)} / {formatPct(playbook?.performance?.win_rate_4d, 0)} / {formatPct(playbook?.performance?.win_rate_5d, 0)}</p>
        <p>1/2/3/4/5日收益：{formatPct(playbook?.performance?.avg_return_1d)} / {formatPct(playbook?.performance?.avg_return_2d)} / {formatPct(playbook?.performance?.avg_return_3d)} / {formatPct(playbook?.performance?.avg_return_4d)} / {formatPct(playbook?.performance?.avg_return_5d)}</p>
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
            {executableCount <= 0 ? (
              <div className="board-warning">
                <strong>今日无可执行买点</strong>
                <span>当前只有继续观察样本，不能当作确认买入；等待价格进入买点区并完成承接确认。</span>
              </div>
            ) : null}
            <p>{executableCount > 0 ? "主看" : "观察"}：{focus.name} {focus.symbol}，{focus.actionText}，{focus.details}</p>
            <InfoPill label="主线轮动" value={playbook?.hot_industries?.slice(0, 4).join(" / ") || "--"} />
            <InfoPill label="执行顺序" value="先确定买入，再看观察确认和接近买点，失效立即降级" />
            <InfoPill label="盘后复盘入口" value="自动归档触发价、失效价和执行结果" />
          </>
        ) : avoid.length ? (
          <div className="board-warning danger">
            <strong>今日全部放弃</strong>
            <span>当前策略有样本但都未通过买点、承接或风控过滤，不展示为主看标的。</span>
          </div>
        ) : <EmptyState text="当前策略暂无主看标的。" />}
      </aside>
      <CandidateSection className="playbook-buy" title="现在可买 / 小仓试买" items={buyNow} empty="当前没有可以直接执行的股票" onAnalyze={onAnalyze} onSelect={onSelect} />
      <CandidateSection className="playbook-observe-confirmed" title="观察确认" items={observeConfirmed} empty="当前没有观察确认的股票" onAnalyze={onAnalyze} onSelect={onSelect} />
      <CandidateSection className="playbook-near" title="等确认" items={nearEntry} empty="当前没有接近买点的股票" onAnalyze={onAnalyze} onSelect={onSelect} />
      <div className="panel playbook-watch">
        <PanelTitle title="继续观察 / 今天放弃" />
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

function strategyPurpose(strategyKey: string): string {
  if (strategyKey.includes("first_board")) return "首板回调，只看启动后第一次承接。";
  if (strategyKey.includes("volume_shrink")) return "缩量回踩，等价格接近支撑再看。";
  if (strategyKey.includes("late_session")) return "收盘承接，主要看次日冲高兑现。";
  if (strategyKey.includes("core_midcap")) return "板块中军回踩，只做主线核心。";
  if (strategyKey.includes("mainline") || strategyKey.includes("divergence")) return "主线首分歧，确认修复前不追。";
  if (strategyKey.includes("n_pattern_long")) return "长洗 N 字核心生产策略，主要看 3-5 日冲高止盈。";
  if (strategyKey.includes("n_pattern_short")) return "短洗 N 字核心生产策略，主要看 T+1/T+2 冲高止盈。";
  return "按当前策略规则分层筛选，先看买点和止损。";
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

function sampleInsufficientReason(strategyKey: string, playbook: LowBuyScreenerResult | null): string {
  const backendNote = playbook?.performance?.attribution_notes?.find(Boolean);
  if (backendNote) return backendNote;
  if (strategyKey === "late_session_strong_support") {
    return "收盘强势承接只统计确定买入后的真实成交绩效；当前多数样本停留在观察/接近买点层，需要次日冲高或分时承接确认后才进入胜率样本。";
  }
  if (strategyKey === "sector_mainline_first_divergence_low_buy") {
    return "主线首分歧要求主线板块、第一次分歧、龙头/强跟随和次日确认同时成立；未触发确定买入时不会计入胜率收益样本。";
  }
  if (strategyKey === "mainline_limitup_shrink_retrace_reclaim") {
    return "主线涨停回调只统计主线板块、缩量回调、均线合一和重新站回 5 日线同时成立后的样本；未完成二次确认不会计入胜率收益样本。";
  }
  return "当前统计口径只计算确定买入且完成后续行情归因的样本；观察票和接近买点票不会计入胜率。";
}

function dataQualityTone(value?: string | null): "up" | "warn" | "down" | "neutral" {
  if (value === "ok") return "up";
  if (value === "partial" || value === "stale" || value === "degraded") return "warn";
  if (value === "limited" || value === "unavailable") return "down";
  return "neutral";
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
