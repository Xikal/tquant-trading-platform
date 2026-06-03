import { Alert, Button, Drawer, Segmented, Tabs } from "antd";
import type { StrategyMeta } from "../../api/strategies";
import type { StrategyTrackingAnalysisTab } from "../../stores/strategyTrackingStore";
import { useStrategyTrackingStore } from "../../stores/strategyTrackingStore";
import { TqEmpty, TqErrorResult } from "../../ui/feedback/StateViews";
import type { StrategyTrackingListResponse, StrategyTrackingParams, StrategyTrackingSnapshotResponse } from "../../types";
import { useRelativeStrengthBoard, useStrategyPromotionReview, useStrategyTrackingDetail, useStrategyTrackingHoldingAnalysis, useStrategyTrackingItems, useStrategyTrackingReport, useTrackRecordDrift, useTradeJournal, useTradeReviewSuite, useTradingExperienceReadiness } from "./queries";
import { DriftMonitorPanel } from "./DriftMonitorPanel";
import { PromotionReviewPanel } from "./PromotionReviewPanel";
import { RelativeStrengthBoard } from "./RelativeStrengthBoard";
import { StrategyTrackingDetailDrawer } from "./StrategyTrackingDetailDrawer";
import { StrategyTrackingDiagnosticsPanel } from "./StrategyTrackingDiagnosticsPanel";
import { StrategyTrackingFilters } from "./StrategyTrackingFilters";
import { StrategyTrackingConclusionBar } from "./StrategyTrackingConclusionBar";
import { StrategyTrackingHoldingAnalysisPanel } from "./StrategyTrackingHoldingAnalysisPanel";
import { StrategyTrackingModeToggle } from "./StrategyTrackingModeToggle";
import { StrategyTrackingPerformanceTable } from "./StrategyTrackingPerformanceTable";
import { StrategyTrackingReviewPanel } from "./StrategyTrackingReviewPanel";
import { StrategyTrackingTable } from "./StrategyTrackingTable";
import { TradeJournalPanel } from "./TradeJournalPanel";
import { TradeReviewPanel } from "./TradeReviewPanel";
import { boolParam, tabParams } from "./strategyTrackingFormatters";

type StrategyTrackingStoreState = ReturnType<typeof useStrategyTrackingStore.getState>;

export function StrategyTrackingPage({ strategyMeta }: { strategyMeta: StrategyMeta[] }) {
  const store = useStrategyTrackingStore();
  const params = buildParams(store);
  const query = useStrategyTrackingItems(params);
  const detailQuery = useStrategyTrackingDetail(store.selectedItemId);
  const weeklyReportQuery = useStrategyTrackingReport("weekly", { range: store.range }, store.analysisTab === "diagnostics");
  const holdingQuery = useStrategyTrackingHoldingAnalysis(holdingParams(store), store.analysisTab === "holding");
  const driftQuery = useTrackRecordDrift(60, store.analysisTab === "drift");
  const promotionReviewQuery = useStrategyPromotionReview(store.strategyKey || "n_pattern_long_wash", true);
  const tradingExperienceReadiness = useTradingExperienceReadiness();
  const tradingExperienceFlags = tradingExperienceReadiness.data?.flags ?? {};
  const reviewEnabled = Boolean(tradingExperienceFlags.trading_experience_suite_enabled && tradingExperienceFlags.trade_review_suite_enabled);
  const rsEnabled = Boolean(tradingExperienceFlags.trading_experience_suite_enabled && tradingExperienceFlags.relative_strength_board_enabled);
  const activeAnalysisTab = visibleAnalysisTab(store.analysisTab, { reviewEnabled, rsEnabled });
  const reviewQuery = useTradeReviewSuite(activeAnalysisTab === "trade-review" && reviewEnabled);
  const journalQuery = useTradeJournal(null, activeAnalysisTab === "trade-journal" && reviewEnabled);
  const rsQuery = useRelativeStrengthBoard(activeAnalysisTab === "relative-strength" && rsEnabled);
  const snapshot = query.data;
  const result = snapshot ? snapshotToListResponse(snapshot) : undefined;
  const errorText = query.error instanceof Error ? query.error.message : "";

  return (
    <section className="strategy-tracking-page">
      {result ? (
        <StrategyTrackingConclusionBar
          result={result}
          range={store.range}
          activeStatus={store.userStatus}
          snapshotMeta={snapshotMetaText(snapshot)}
          onSelectStatus={store.setUserStatus}
        />
      ) : (
        <div className="panel strategy-tracking-hero">
          <div className="strategy-tracking-title">
            <h1>策略跟踪</h1>
            <p>买入类和观察类分开看；观察信号只用于提醒和复盘。</p>
          </div>
          <div className="strategy-tracking-hero-meta">
            <span>{snapshotMetaText(snapshot)}</span>
            <span>只读观察</span>
          </div>
        </div>
      )}
      <div className="panel strategy-tracking-filter-panel">
        <div className="strategy-tracking-filter-toolbar">
          <StrategyTrackingModeToggle viewMode={store.viewMode} onChange={store.setViewMode} />
          <Button onClick={() => store.setFiltersDrawerOpen(true)}>筛选条件</Button>
        </div>
        <div className="strategy-tracking-active-filters">{activeFilterText(store)}</div>
      </div>
      {snapshot?.stale ? <Alert type="warning" showIcon title="策略跟踪快照数据刷新中" description="当前先展示上一版快照，后台会在策略任务完成后重建。" /> : null}
      {snapshot?.status === "missing" ? <Alert type="info" showIcon title="策略跟踪快照尚未生成" description="请先等待后台快照任务或由管理员手动刷新。" /> : null}
      {store.excludeChinext || store.excludeStar || store.boardFilter === "main_only" ? (
        <Alert type="info" showIcon title={filterNotice(store)} />
      ) : null}
      {result?.partial_errors.length ? (
        <Alert type="warning" showIcon title={result.partial_errors.slice(0, 2).join("；")} />
      ) : null}
      {errorText ? <TqErrorResult title="策略跟踪加载失败" description={errorText} onRetry={() => void query.refetch()} /> : null}
      {!errorText ? (
        <div className="panel strategy-tracking-main-panel">
          <div className="strategy-tracking-section-head">
            <div>
              <strong>主区：信号列表</strong>
              <span>先看当前跟踪、涨幅和风险，观察信号不等于买入动作。</span>
            </div>
            <Segmented
              size="small"
              value={store.overviewTab}
              onChange={(value) => store.setOverviewTab(value as typeof store.overviewTab)}
              options={[
                { label: "跟踪复盘", value: "active" },
                { label: "涨幅", value: "gain" },
                { label: "风险", value: "risk" },
              ]}
            />
          </div>
          {tableContent(result, query.isFetching, store)}
        </div>
      ) : null}
      {!errorText ? (
        <div className="panel strategy-tracking-secondary-panel">
          <Tabs
            size="small"
            activeKey={activeAnalysisTab}
            onChange={(key) => store.setAnalysisTab(key as typeof store.analysisTab)}
            items={analysisTabs(result, store, holdingQuery, driftQuery, weeklyReportQuery, promotionReviewQuery, {
              reviewEnabled,
              rsEnabled,
              reviewQuery,
              journalQuery,
              rsQuery,
            })}
          />
        </div>
      ) : null}
      <StrategyTrackingDetailDrawer
        open={Boolean(store.selectedItemId)}
        loading={detailQuery.isFetching}
        detail={detailQuery.data}
        errorText={detailQuery.error instanceof Error ? detailQuery.error.message : ""}
        viewMode={store.viewMode}
        onClose={() => store.setSelectedItemId(null)}
      />
      <Drawer
        title="策略跟踪筛选"
        open={store.filtersDrawerOpen}
        onClose={() => store.setFiltersDrawerOpen(false)}
      >
        <StrategyTrackingFilters
          range={store.range}
          strategyKey={store.strategyKey}
          strategyVariant={store.strategyVariant}
          strategyFamily={store.strategyFamily}
          signalState={store.signalState}
          lifecycleStatus={store.lifecycleStatus}
          dataQuality={store.dataQuality}
          hitEntry={store.hitEntry}
          stopped={store.stopped}
          userStatus={store.userStatus}
          excludeChinext={store.excludeChinext}
          excludeStar={store.excludeStar}
          boardFilter={store.boardFilter}
          strategyMeta={strategyMeta}
          onRangeChange={store.setRange}
          onStrategyKeyChange={store.setStrategyKey}
          onStrategyVariantChange={store.setStrategyVariant}
          onStrategyFamilyChange={store.setStrategyFamily}
          onSignalStateChange={store.setSignalState}
          onLifecycleStatusChange={store.setLifecycleStatus}
          onDataQualityChange={store.setDataQuality}
          onHitEntryChange={store.setHitEntry}
          onStoppedChange={store.setStopped}
          onUserStatusChange={store.setUserStatus}
          onExcludeChinextChange={store.setExcludeChinext}
          onExcludeStarChange={store.setExcludeStar}
          onBoardFilterChange={store.setBoardFilter}
        />
      </Drawer>
    </section>
  );
}

export function visibleAnalysisTab(
  tab: StrategyTrackingAnalysisTab,
  flags: { reviewEnabled: boolean; rsEnabled: boolean },
): StrategyTrackingAnalysisTab {
  if ((tab === "trade-review" || tab === "trade-journal") && !flags.reviewEnabled) return "diagnostics";
  if (tab === "relative-strength" && !flags.rsEnabled) return "diagnostics";
  return tab;
}

function tableContent(result: StrategyTrackingListResponse | undefined, loading: boolean, store: StrategyTrackingStoreState) {
  if (!result?.items.length && !loading) {
    return <TqEmpty title="今天还没有生产策略给出可跟踪买点" description="当前筛选条件下没有有效策略跟踪记录。" />;
  }
  return (
    <StrategyTrackingTable
      items={result?.items ?? []}
      total={result?.total ?? 0}
      page={store.page}
      pageSize={store.pageSize}
      loading={loading}
      viewMode={store.viewMode}
      onPageChange={store.setPagination}
      onOpenDetail={store.setSelectedItemId}
    />
  );
}

function snapshotToListResponse(snapshot: StrategyTrackingSnapshotResponse): StrategyTrackingListResponse {
  return {
    items: snapshot.payload.items,
    total: snapshot.total,
    limit: snapshot.limit,
    offset: snapshot.offset,
    sort: snapshot.sort,
    summary: snapshot.payload.summary,
    performance: snapshot.payload.performance,
    market_segments: snapshot.payload.market_segments,
    shadow_observations: snapshot.payload.shadow_observations,
    partial_errors: snapshot.partial_errors,
    production_writeable: snapshot.production_writeable,
    read_path: snapshot.read_path,
    rust_math_used: true,
    notes: snapshot.notes,
  };
}

function snapshotMetaText(snapshot?: StrategyTrackingSnapshotResponse): string {
  if (!snapshot) return "快照加载中";
  if (snapshot.status === "missing") return "快照未生成";
  const generated = snapshot.generated_at || snapshot.payload.summary.generated_at || "--";
  const cutoff = snapshot.source_data_cutoff ? ` / 截止 ${snapshot.source_data_cutoff}` : "";
  return `${snapshot.stale ? "刷新中" : "已生成"} ${generated}${cutoff}`;
}

export function buildParams(store: StrategyTrackingStoreState): StrategyTrackingParams {
  const preset = tabParams(store.overviewTab);
  return {
    range: store.range,
    strategy_key: store.strategyKey || undefined,
    strategy_variant: store.strategyVariant || undefined,
    strategy_family: store.strategyFamily || undefined,
    signal_state: store.signalState || undefined,
    status: store.lifecycleStatus || preset.status,
    data_quality: store.dataQuality || undefined,
    hit_entry: boolParam(store.hitEntry),
    stopped: boolParam(store.stopped) ?? preset.stopped,
    user_status: store.userStatus || undefined,
    exclude_chinext: store.excludeChinext,
    exclude_star: store.excludeStar,
    board_filter: store.boardFilter === "main_only" ? "main_only" : undefined,
    sort: store.sort,
    limit: store.pageSize,
    offset: (store.page - 1) * store.pageSize,
  };
}

function holdingParams(store: StrategyTrackingStoreState): StrategyTrackingParams {
  return {
    range: store.range,
    strategy_variant: store.strategyVariant || undefined,
    strategy_family: store.strategyFamily || undefined,
    exclude_chinext: store.excludeChinext,
    exclude_star: store.excludeStar,
    board_filter: store.boardFilter === "main_only" ? "main_only" : undefined,
  };
}

function analysisTabs(
  result: StrategyTrackingListResponse | undefined,
  store: StrategyTrackingStoreState,
  holdingQuery: ReturnType<typeof useStrategyTrackingHoldingAnalysis>,
  driftQuery: ReturnType<typeof useTrackRecordDrift>,
  weeklyReportQuery: ReturnType<typeof useStrategyTrackingReport>,
  promotionReviewQuery: ReturnType<typeof useStrategyPromotionReview>,
  tradingExperience: {
    reviewEnabled: boolean;
    rsEnabled: boolean;
    reviewQuery: ReturnType<typeof useTradeReviewSuite>;
    journalQuery: ReturnType<typeof useTradeJournal>;
    rsQuery: ReturnType<typeof useRelativeStrengthBoard>;
  },
) {
  const items = [
    {
      key: "performance",
      label: "策略表现",
      children: result?.performance.length ? (
        <StrategyTrackingPerformanceTable items={result.performance} />
      ) : (
        <TqEmpty title="暂无策略表现" description="当前筛选条件下还没有可聚合的跟踪信号样本。" />
      ),
    },
    {
      key: "holding",
      label: "持有分析",
      children: (
        <StrategyTrackingHoldingAnalysisPanel
          items={holdingQuery.data?.items ?? []}
          loading={holdingQuery.isFetching}
        />
      ),
    },
    {
      key: "drift",
      label: "战绩漂移",
      children: (
        <DriftMonitorPanel
          items={driftQuery.data?.items ?? []}
          total={driftQuery.data?.total ?? 0}
          loading={driftQuery.isFetching}
        />
      ),
    },
    {
      key: "diagnostics",
      label: "复盘诊断",
      children: result ? (
        <div className="strategy-tracking-analysis-stack">
          <StrategyTrackingReviewPanel summary={result.summary} performance={result.performance} />
          <StrategyTrackingDiagnosticsPanel result={result} weeklyReport={weeklyReportQuery} viewMode={store.viewMode} />
          <PromotionReviewPanel review={promotionReviewQuery.data} loading={promotionReviewQuery.isFetching} />
        </div>
      ) : (
        <TqEmpty title="暂无复盘诊断" description="当前筛选条件下没有可诊断样本。" />
      ),
    },
  ];
  if (tradingExperience.reviewEnabled) {
    items.push(
      {
        key: "trade-review",
        label: "复盘",
        children: <TradeReviewPanel data={tradingExperience.reviewQuery.data} loading={tradingExperience.reviewQuery.isFetching} />,
      },
      {
        key: "trade-journal",
        label: "纪律日志",
        children: <TradeJournalPanel accountId={null} data={tradingExperience.journalQuery.data} loading={tradingExperience.journalQuery.isFetching} />,
      },
    );
  }
  if (tradingExperience.rsEnabled) {
    items.push({
      key: "relative-strength",
      label: "抗跌事实",
      children: <RelativeStrengthBoard data={tradingExperience.rsQuery.data} loading={tradingExperience.rsQuery.isFetching} />,
    });
  }
  return items;
}

function activeFilterText(store: StrategyTrackingStoreState): string {
  const rangeText = store.range === 1 ? "今日" : `近 ${store.range} 日`;
  const boardText = store.boardFilter === "main_only" ? "只看主板" : "全部市场板";
  const hiddenBoards = [store.excludeChinext ? "屏蔽创业板" : "", store.excludeStar ? "屏蔽科创板" : ""].filter(Boolean);
  const signalText = `信号 ${signalStateLabel(store.signalState)}`;
  return [rangeText, boardText, signalText, ...hiddenBoards].join(" · ");
}

function signalStateLabel(signalState: string): string {
  if (signalState === "buy_now") return "确定可买";
  if (signalState === "soft_buy_now") return "小仓试买";
  if (signalState === "near_entry") return "接近买点（观察）";
  if (signalState === "observe_confirmed") return "观察确认（非买入）";
  return "全部";
}

function filterNotice(store: StrategyTrackingStoreState): string {
  if (store.boardFilter === "main_only") return "已隐藏创业板、科创板等非主板股票，仅展示主板样本。";
  const hidden = [store.excludeChinext ? "创业板" : "", store.excludeStar ? "科创板" : ""].filter(Boolean).join("、");
  return `已隐藏${hidden}股票，仅影响当前页面展示。`;
}
