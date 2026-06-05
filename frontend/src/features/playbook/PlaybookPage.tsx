import type { LowBuyScreenerResult } from "../../types";
import { Button, Collapse, Flex, Tabs, Typography } from "antd";
import { playbookActionLabel } from "../../utils/uxClarity";
import { Callout, EmptyState, InfoPill, MetricGrid, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import { RitualFortuneStrip, RitualLuckyDraw, RitualSignalSeal } from "../ritual-ui";
import { WEB_PLAYBOOK_TABS } from "../workspace-shared/workspaceConstants";
import { candidateToCard } from "../workspace-shared/workspaceViewModels";
import { filterTodayConfirmedCandidates, isBeijingTodayTradeDate } from "../workspace-shared/todayRecommendations";
import { formatNumber, formatPct, strategyLabel, toneFromChange } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView } from "../workspace-shared/workspaceTypes";
import { VirtualCardList } from "../../ui/list/VirtualCardList";

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
  const todayCandidates = isBeijingTodayTradeDate(playbook?.latest_trade_date)
    ? allCandidates
    : [];
  const buyNow = filterTodayConfirmedCandidates(playbook).map(candidateToCard);
  const observeConfirmed = todayCandidates.filter((item) => item.buy_signal_state === "observe_confirmed").map(candidateToCard);
  const nearEntry = todayCandidates.filter((item) => item.buy_signal_state === "near_entry").map(candidateToCard);
  const watch = todayCandidates.filter((item) => item.buy_signal_state === "watch").map(candidateToCard);
  const avoid = todayCandidates.filter((item) => item.buy_signal_state === "avoid").map(candidateToCard);
  const passiveCandidates = [...watch, ...avoid];
  const confirmedCount = buyNow.length;
  const hasHiddenCandidates = allCandidates.length > 0;
  const focus = buyNow[0] ?? null;
  const strategyName = tabLabel(strategy, tabs) || strategyLabel(strategy);
  const loadedStrategyName = playbook?.strategy_title || tabLabel(playbook?.strategy_key || strategy, tabs) || strategyLabel(playbook?.strategy_key || strategy);
  const switchingText = playbook && playbook.strategy_key !== strategy ? "，正在切换数据" : "";
  const hasInsufficientData = playbook?.performance?.data_insufficient || (playbook?.performance?.filled_signals ?? 0) <= 0;
  const hitRateDisplay = hasInsufficientData ? "样本不足" : formatPct(playbook?.performance?.hit_rate);
  const hitRateTone: MetricItem["tone"] = hasInsufficientData ? "neutral" : "up";
  const sampleReason = sampleInsufficientReason(playbook?.strategy_key || strategy, playbook);
  const marketAttributionText = summarizeMarketAttribution(playbook?.performance?.market_state_attribution ?? []);
  return (
    <section className="tq-playbook-page">
      <div className="panel tq-playbook-page__hero">
        <WorkspacePageIntro
          title="选股宝典"
          summary={`${strategyName}：${strategyPurpose(strategy)}`}
          tone={confirmedCount ? "up" : "neutral"}
          actions={<Button onClick={onRefresh} loading={loading === "playbook"}>刷新全量结果</Button>}
          pills={[
            { label: "可执行", value: String(confirmedCount), tone: confirmedCount ? "up" : "neutral" },
            { label: "全量深筛", value: String(playbook?.scanned_count ?? "--") },
            { label: "数据状态", value: playbook?.data_quality_text ?? "--", tone: dataQualityTone(playbook?.data_quality) },
            { label: "交易日", value: playbook?.latest_trade_date ?? "--" },
          ]}
        />
        <Flex wrap gap={6} align="center" className="tq-playbook-page__hero-actions">
          <RitualFortuneStrip marketTone={confirmedCount ? "strong" : "unknown"} compact />
          <RitualLuckyDraw compact />
        </Flex>
        <Flex wrap gap={6} className="tq-playbook-page__strategy-tabs">
          {tabs.map((tab) => (
            <Button
              key={tab.key}
              type={strategy === tab.key ? "primary" : "default"}
              size="small"
              onClick={() => setStrategy(tab.key)}
            >
              {tab.label}
            </Button>
          ))}
        </Flex>
      </div>
      <MetricGrid
        compact
        className="tq-playbook-page__metrics"
        items={[
          { label: "真实成交样本", value: String(playbook?.performance?.filled_signals ?? 0), tone: hasInsufficientData ? "warn" : "up" },
          { label: "5日达标率", value: hitRateDisplay, tone: hitRateTone },
          { label: "平均收益", value: formatPct(playbook?.performance?.avg_return_5d), tone: toneFromChange(playbook?.performance?.avg_return_5d) },
          { label: "最大回撤", value: formatPct(playbook?.performance?.avg_max_drawdown_5d), tone: toneFromChange(playbook?.performance?.avg_max_drawdown_5d) },
        ]}
      />
      <div className="panel tq-playbook-page__performance">
        <PanelTitle title="最近表现" className="tq-playbook-page__panel-title" />
        <p>当前策略：{strategyName}；已加载：{loadedStrategyName}{switchingText}</p>
        <p>近5日 达标率 {hitRateDisplay}　平均收益 {formatPct(playbook?.performance?.avg_return_5d)}　回撤 {formatPct(playbook?.performance?.avg_max_drawdown_5d)}　赚亏比 {formatNumber(playbook?.performance?.profit_factor)}</p>
        {hasInsufficientData ? <p>样本说明：{sampleReason}</p> : null}
        <Collapse
          ghost
          size="small"
          items={[{
            key: "perf-detail",
            label: "样本、胜率、收益与归因明细",
            children: (
              <>
                <p>样本规模：信号 {playbook?.performance?.signal_count ?? 0}　已评估 {playbook?.performance?.evaluated_signals ?? 0}　真实成交 {playbook?.performance?.filled_signals ?? 0}　未成交 {playbook?.performance?.not_filled_signals ?? 0}</p>
                <p>1/2/3/4/5日胜率：{formatPct(playbook?.performance?.win_rate_1d, 0)} / {formatPct(playbook?.performance?.win_rate_2d, 0)} / {formatPct(playbook?.performance?.win_rate_3d, 0)} / {formatPct(playbook?.performance?.win_rate_4d, 0)} / {formatPct(playbook?.performance?.win_rate_5d, 0)}</p>
                <p>1/2/3/4/5日收益：{formatPct(playbook?.performance?.avg_return_1d)} / {formatPct(playbook?.performance?.avg_return_2d)} / {formatPct(playbook?.performance?.avg_return_3d)} / {formatPct(playbook?.performance?.avg_return_4d)} / {formatPct(playbook?.performance?.avg_return_5d)}</p>
                <p>尾部风险 CVaR {formatPct(playbook?.performance?.cvar_5pct)}　半凯利参考 {formatPct(playbook?.performance?.kelly_half_position_pct, 1)}　平均盈利/亏损 {formatPct(playbook?.performance?.avg_win_pct)} / {formatPct(playbook?.performance?.avg_loss_pct)}</p>
                <p>板块归因：{playbook?.hot_industries?.slice(0, 3).join("、") || "--"}；市场状态：{playbook?.market_state_category_text || playbook?.market_state_text || "--"}；分市场表现：{marketAttributionText}</p>
              </>
            ),
          }]}
        />
      </div>
      <aside className="panel tq-playbook-page__focus">
        <PanelTitle title="今日主看" />
        {focus ? (
          <>
            <p>主看：{focus.name} {focus.symbol}，{focus.actionText}，{focus.details}</p>
            <RitualSignalSeal signalState={ritualStateFromAction(focus.actionText)} riskLevel={focus.riskText} />
            <InfoPill label="主线轮动" value={playbook?.hot_industries?.slice(0, 4).join(" / ") || "--"} />
          </>
        ) : hasHiddenCandidates ? (
          <Callout
            title="今日暂无确认推荐"
            detail="当前不展示旧交易日或观察层股票；若后台刷新后出现当日确认票，会自动进入对应榜单。"
            tone="neutral"
            compact
          />
        ) : <EmptyState text="当前策略暂无主看标的。" />}
      </aside>
      <CandidateTabs
        buyNow={buyNow}
        observeConfirmed={observeConfirmed}
        nearEntry={nearEntry}
        passiveCandidates={passiveCandidates}
        onAnalyze={onAnalyze}
        onSelect={onSelect}
      />
    </section>
  );
}

function strategyPurpose(strategyKey: string): string {
  if (strategyKey.includes("first_board")) return "首板回调，只看启动后第一次承接。";
  if (strategyKey.includes("volume_shrink")) return "缩量回踩，等价格接近支撑再看。";
  if (strategyKey.includes("late_session")) return "收盘承接，主要看次日冲高兑现。";
  if (strategyKey.includes("core_midcap")) return "板块中军回踩，当前只做研究观察。";
  if (strategyKey.includes("mainline") || strategyKey.includes("divergence")) return "主线分歧研究，确认修复前不追。";
  if (strategyKey.includes("n_pattern_long")) return "长洗 N 字研究策略，因 24M 回撤过高不进生产榜。";
  if (strategyKey.includes("n_pattern_short")) return "短洗 N 字研究归档，因 24M 结果弱不进生产榜。";
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

function CandidateTabs({
  buyNow,
  observeConfirmed,
  nearEntry,
  passiveCandidates,
  onAnalyze,
  onSelect,
}: {
  buyNow: StockCardView[];
  observeConfirmed: StockCardView[];
  nearEntry: StockCardView[];
  passiveCandidates: StockCardView[];
  onAnalyze: (stock: StockCardView) => void;
  onSelect: (stock: StockCardView) => void;
}) {
  const sections = [
    { key: "buy", title: "今日确认推荐", short: "可买", items: buyNow, empty: "今日暂无确认推荐，榜单保持空状态。" },
    { key: "observe", title: "今日观察确认（非推荐）", short: "观察", items: observeConfirmed, empty: "今日暂无观察确认股票。" },
    { key: "near", title: "今日等确认（非推荐）", short: "等确认", items: nearEntry, empty: "今日暂无接近买点股票。" },
    { key: "watch", title: "今日继续观察 / 放弃", short: "观察/放弃", items: passiveCandidates, empty: "今日暂无继续观察或放弃股票。" },
  ];
  return (
    <div className="panel tq-playbook-page__candidate-tabs tq-playbook-candidate-tabs">
      <Tabs
        size="small"
        items={sections.map((section) => ({
          key: section.key,
          label: <span className="tq-playbook-page__tab-label">{section.short}<Typography.Text type="secondary" className="tq-playbook-page__tab-count">{section.items.length}</Typography.Text></span>,
          children: (
            <div className="tq-playbook-page__tab-body">
              <PanelTitle title={section.title} />
              <DenseCandidateList items={section.items} empty={section.empty} onAnalyze={onAnalyze} onSelect={onSelect} />
            </div>
          ),
        }))}
      />
    </div>
  );
}

function DenseCandidateList({
  items,
  empty,
  onAnalyze,
  onSelect,
}: {
  items: StockCardView[];
  empty: string;
  onAnalyze: (stock: StockCardView) => void;
  onSelect: (stock: StockCardView) => void;
}) {
  if (!items.length) {
    if (!empty) {
      return null;
    }
    return <EmptyState text={empty} />;
  }
  return (
    <VirtualCardList
      items={items}
      estimateSize={54}
      maxHeight={520}
      className="tq-playbook-page__dense-list tq-playbook-dense-list"
      getItemKey={(stock) => `${stock.symbol}-${stock.actionText}`}
      renderItem={(stock) => (
        <article key={`${stock.symbol}-${stock.actionText}`} className="tq-playbook-page__dense-row tq-playbook-dense-row">
          <div className="tq-playbook-page__dense-name">
            <strong className="tq-playbook-page__dense-text">{stock.name}</strong>
            <span className="tq-playbook-page__dense-meta tq-playbook-dense-row__meta">{stock.symbol}</span>
          </div>
          <span className="tq-playbook-page__dense-text" title={stock.details}>
            {stock.actionText} · {stock.details}
          </span>
          <span className="tq-playbook-page__dense-meta tq-playbook-dense-row__meta">{stock.scoreText ? `质量 ${stock.scoreText}` : stock.riskText}</span>
          <RitualSignalSeal signalState={ritualStateFromAction(stock.actionText)} riskLevel={stock.riskText} compact />
          <Flex gap={4} justify="flex-end">
            <Button size="small" onClick={() => onSelect(stock)}>详情</Button>
            <Button size="small" type="primary" onClick={() => onAnalyze(stock)}>分析</Button>
          </Flex>
        </article>
      )}
    />
  );
}

function ritualStateFromAction(actionText: string): string {
  if (actionText.includes("确定") || actionText.includes("可买")) return "buy_now";
  if (actionText.includes("小仓")) return "soft_buy_now";
  if (actionText.includes("接近") || actionText.includes("等确认")) return "near_entry";
  if (actionText.includes("观察")) return "observe_confirmed";
  if (actionText.includes("放弃") || actionText.includes("风险")) return "avoid";
  return "watch";
}
