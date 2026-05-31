import type { CSSProperties } from "react";
import type { LowBuyScreenerResult } from "../../types";
import { Button, Collapse, Flex, Tabs, Typography } from "antd";
import { playbookActionLabel } from "../../utils/uxClarity";
import { Callout, EmptyState, InfoPill, MetricGrid, PanelTitle } from "../workspace-shared/WorkspaceComponents";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import { RitualFortuneStrip, RitualLuckyDraw, RitualSignalSeal } from "../ritual-ui";
import { WEB_PLAYBOOK_TABS } from "../workspace-shared/workspaceConstants";
import { candidateToCard } from "../workspace-shared/workspaceViewModels";
import { formatNumber, formatPct, strategyLabel } from "../workspace-shared/workspaceFormatters";
import type { MetricItem, StockCardView } from "../workspace-shared/workspaceTypes";
import { VirtualCardList } from "../../ui/list/VirtualCardList";

const PLAYBOOK_PAGE_STYLE: CSSProperties = {
  display: "grid",
  gap: 6,
  gridTemplateColumns: "minmax(300px, 380px) minmax(0, 1fr)",
  gridTemplateAreas: '"hero hero" "performance candidates" "focus candidates"',
  fontSize: 12,
  lineHeight: 1.32,
};

const PLAYBOOK_HERO_STYLE: CSSProperties = { gridArea: "hero" };
const PLAYBOOK_METRICS_STYLE: CSSProperties = { alignContent: "stretch", gridTemplateColumns: "repeat(3, minmax(72px, 1fr))", gap: 4 };
const PLAYBOOK_PERFORMANCE_STYLE: CSSProperties = { gridArea: "performance", outline: "2px solid rgba(64, 149, 255, 0.12)" };
const PLAYBOOK_FOCUS_STYLE: CSSProperties = { gridArea: "focus", outline: "2px solid rgba(64, 149, 255, 0.12)" };
const PLAYBOOK_DARK_FOCUS_STYLE: CSSProperties = {
  ...PLAYBOOK_FOCUS_STYLE,
  borderColor: "rgba(255, 255, 255, 0.1)",
  background: "linear-gradient(180deg, var(--panel), var(--deep))",
  color: "#dde3ec",
};
const PLAYBOOK_CANDIDATE_TABS_STYLE: CSSProperties = { gridArea: "candidates", minHeight: 0 };
const PLAYBOOK_TAB_BODY_STYLE: CSSProperties = {
  maxHeight: "min(52vh, 520px)",
  overflowY: "auto",
  paddingRight: 2,
};
const PLAYBOOK_DENSE_LIST_STYLE: CSSProperties = {
  display: "grid",
  gap: 4,
};
const PLAYBOOK_DENSE_ROW_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(78px, 0.85fr) minmax(0, 1.7fr) minmax(54px, 0.45fr) auto auto",
  gap: 6,
  alignItems: "center",
  border: "1px solid rgba(148, 163, 184, 0.2)",
  borderRadius: 7,
  background: "#fff",
  padding: "5px 6px",
  minWidth: 0,
};
const PLAYBOOK_DENSE_NAME_STYLE: CSSProperties = {
  display: "grid",
  gap: 1,
  minWidth: 0,
};
const PLAYBOOK_DENSE_TEXT_STYLE: CSSProperties = {
  minWidth: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
  fontSize: 12,
};
const PLAYBOOK_DENSE_META_STYLE: CSSProperties = {
  color: "#64748b",
  fontSize: 12,
};
const PLAYBOOK_TAB_LABEL_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  fontSize: 12,
  fontWeight: 700,
};

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
  const passiveCandidates = [...watch, ...avoid];
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
    <section style={PLAYBOOK_PAGE_STYLE}>
      <div className="panel" style={PLAYBOOK_HERO_STYLE}>
        <WorkspacePageIntro
          title="选股宝典"
          summary={`${strategyName}：${strategyPurpose(strategy)}`}
          tone={buyNow.length ? "up" : executableCount > 0 ? "warn" : "neutral"}
          actions={<Button onClick={onRefresh} loading={loading === "playbook"}>刷新全量结果</Button>}
          pills={[
            { label: "可执行", value: String(executableCount), tone: executableCount ? "up" : "neutral" },
            { label: "全量深筛", value: String(playbook?.scanned_count ?? "--") },
            { label: "数据状态", value: playbook?.data_quality_text ?? "--", tone: dataQualityTone(playbook?.data_quality) },
            { label: "交易日", value: playbook?.latest_trade_date ?? "--" },
          ]}
        />
        <Flex wrap gap={6} align="center" style={{ marginTop: 6 }}>
          <RitualFortuneStrip marketTone={buyNow.length ? "strong" : executableCount ? "neutral" : "unknown"} compact />
          <RitualLuckyDraw compact />
        </Flex>
        <Flex wrap gap={6} style={{ marginTop: 8 }}>
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
        style={PLAYBOOK_METRICS_STYLE}
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
      <div className="panel" style={PLAYBOOK_PERFORMANCE_STYLE}>
        <PanelTitle title="最近表现" style={{ marginBottom: 4 }} />
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
      <aside className="panel" style={PLAYBOOK_DARK_FOCUS_STYLE}>
        <PanelTitle title="今日主看" />
        {focus ? (
          <>
            {executableCount <= 0 ? (
              <Callout
                title="今日无可执行买点"
                detail="当前只有继续观察样本，不能当作确认买入；等待价格进入买点区并完成承接确认。"
                tone="warn"
                compact
              />
            ) : null}
            <p>{executableCount > 0 ? "主看" : "观察"}：{focus.name} {focus.symbol}，{focus.actionText}，{focus.details}</p>
            <RitualSignalSeal signalState={ritualStateFromAction(focus.actionText)} riskLevel={focus.riskText} />
            <InfoPill label="主线轮动" value={playbook?.hot_industries?.slice(0, 4).join(" / ") || "--"} />
          </>
        ) : avoid.length ? (
          <Callout
            title="今日全部放弃"
            detail="当前策略有样本但都未通过买点、承接或风控过滤，不展示为主看标的。"
            tone="down"
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
    { key: "buy", title: "现在可买 / 小仓试买", short: "可买", items: buyNow, empty: "当前没有可以直接执行的股票" },
    { key: "observe", title: "观察确认", short: "观察", items: observeConfirmed, empty: "当前没有观察确认的股票" },
    { key: "near", title: "等确认", short: "等确认", items: nearEntry, empty: "当前没有接近买点的股票" },
    { key: "watch", title: "继续观察 / 今天放弃", short: "观察/放弃", items: passiveCandidates, empty: "这一档为空，说明当前结构要么未到位，要么质量不足。" },
  ];
  return (
    <div className="panel" style={PLAYBOOK_CANDIDATE_TABS_STYLE}>
      <Tabs
        size="small"
        tabBarStyle={{ marginBottom: 6 }}
        items={sections.map((section) => ({
          key: section.key,
          label: <span style={PLAYBOOK_TAB_LABEL_STYLE}>{section.short}<Typography.Text type="secondary" style={{ fontSize: 12 }}>{section.items.length}</Typography.Text></span>,
          children: (
            <div style={PLAYBOOK_TAB_BODY_STYLE}>
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
    return <EmptyState text={empty} />;
  }
  return (
    <VirtualCardList
      items={items}
      estimateSize={54}
      maxHeight={520}
      style={PLAYBOOK_DENSE_LIST_STYLE}
      getItemKey={(stock) => `${stock.symbol}-${stock.actionText}`}
      renderItem={(stock) => (
        <article key={`${stock.symbol}-${stock.actionText}`} style={PLAYBOOK_DENSE_ROW_STYLE}>
          <div style={PLAYBOOK_DENSE_NAME_STYLE}>
            <strong style={PLAYBOOK_DENSE_TEXT_STYLE}>{stock.name}</strong>
            <span style={PLAYBOOK_DENSE_META_STYLE}>{stock.symbol}</span>
          </div>
          <span style={PLAYBOOK_DENSE_TEXT_STYLE} title={stock.details}>
            {stock.actionText} · {stock.details}
          </span>
          <span style={PLAYBOOK_DENSE_META_STYLE}>{stock.scoreText ? `质量 ${stock.scoreText}` : stock.riskText}</span>
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
