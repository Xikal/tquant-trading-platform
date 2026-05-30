import { Alert, Tabs } from "antd";
import type { StrategyMeta } from "../../api/strategies";
import { useStrategyTrackingStore } from "../../stores/strategyTrackingStore";
import { TqEmpty, TqErrorResult } from "../../ui/feedback/StateViews";
import type { StrategyTrackingListResponse, StrategyTrackingParams, StrategyTrackingSnapshotResponse } from "../../types";
import { useStrategyTrackingDetail, useStrategyTrackingHoldingAnalysis, useStrategyTrackingItems, useStrategyTrackingReport } from "./queries";
import { StrategyTrackingDetailDrawer } from "./StrategyTrackingDetailDrawer";
import { StrategyTrackingDiagnosticsPanel } from "./StrategyTrackingDiagnosticsPanel";
import { StrategyTrackingFilters } from "./StrategyTrackingFilters";
import { StrategyTrackingFriendlySummary } from "./StrategyTrackingFriendlySummary";
import { StrategyTrackingHoldingAnalysisPanel } from "./StrategyTrackingHoldingAnalysisPanel";
import { StrategyTrackingModeToggle } from "./StrategyTrackingModeToggle";
import { StrategyTrackingPerformanceTable } from "./StrategyTrackingPerformanceTable";
import { StrategyTrackingReviewPanel } from "./StrategyTrackingReviewPanel";
import { StrategyTrackingStatusCards } from "./StrategyTrackingStatusCards";
import { StrategyTrackingSummaryBar } from "./StrategyTrackingSummaryBar";
import { StrategyTrackingTable } from "./StrategyTrackingTable";
import { boolParam, tabParams } from "./strategyTrackingFormatters";
import { RitualFortuneStrip, RitualLuckyDraw } from "../ritual-ui";

type StrategyTrackingStoreState = ReturnType<typeof useStrategyTrackingStore.getState>;

export function StrategyTrackingPage({ strategyMeta }: { strategyMeta: StrategyMeta[] }) {
  const store = useStrategyTrackingStore();
  const params = buildParams(store);
  const query = useStrategyTrackingItems(params);
  const detailQuery = useStrategyTrackingDetail(store.selectedItemId);
  const weeklyReportQuery = useStrategyTrackingReport("weekly", { range: store.range }, store.tab === "diagnostics");
  const holdingQuery = useStrategyTrackingHoldingAnalysis(holdingParams(store), store.tab === "holding");
  const snapshot = query.data;
  const result = snapshot ? snapshotToListResponse(snapshot) : undefined;
  const errorText = query.error instanceof Error ? query.error.message : "";

  return (
    <section className="strategy-tracking-page">
      <div className="panel strategy-tracking-hero">
        <div className="strategy-tracking-title">
          <h1>策略跟踪</h1>
          <p>生产策略推荐后的买点、涨幅、回撤和生命周期复盘。</p>
        </div>
        <div className="strategy-tracking-hero-meta">
          <RitualFortuneStrip marketTone={(result?.summary.in_entry_zone_count ?? 0) > 0 ? "strong" : (result?.summary.stopped_count ?? 0) > 0 ? "weak" : "neutral"} compact />
          <RitualLuckyDraw compact />
          <span>区间 {store.range === 1 ? "今日" : `${store.range}日`}</span>
          <span>样本 {result?.total ?? "--"}</span>
          <span>{snapshotMetaText(snapshot)}</span>
          <span>只读观察</span>
        </div>
      </div>
      <div className="panel strategy-tracking-filter-panel">
        <StrategyTrackingModeToggle viewMode={store.viewMode} onChange={store.setViewMode} />
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
      </div>
      {result ? <StrategyTrackingFriendlySummary result={result} range={store.range} /> : null}
      {snapshot?.stale ? <Alert type="warning" showIcon title="策略跟踪快照数据刷新中" description="当前先展示上一版快照，后台会在策略任务完成后重建。" /> : null}
      {snapshot?.status === "missing" ? <Alert type="info" showIcon title="策略跟踪快照尚未生成" description="请先等待后台快照任务或由管理员手动刷新。" /> : null}
      {store.excludeChinext || store.excludeStar || store.boardFilter === "main_only" ? (
        <Alert type="info" showIcon title={filterNotice(store)} />
      ) : null}
      {result ? (
        <div className="strategy-tracking-top-grid">
          <StrategyTrackingSummaryBar summary={result.summary} />
          <StrategyTrackingReviewPanel summary={result.summary} performance={result.performance} />
        </div>
      ) : null}
      {result ? (
        <StrategyTrackingStatusCards items={result.items} activeStatus={store.userStatus} onSelectStatus={store.setUserStatus} />
      ) : null}
      {result?.partial_errors.length ? (
        <Alert type="warning" showIcon title={result.partial_errors.slice(0, 2).join("；")} />
      ) : null}
      {errorText ? <TqErrorResult title="策略跟踪加载失败" description={errorText} onRetry={() => void query.refetch()} /> : null}
      {!errorText ? (
        <div className="panel strategy-tracking-main-panel">
          <Tabs
            activeKey={store.tab}
            onChange={(key) => store.setTab(key as typeof store.tab)}
            items={[
              {
                key: "active",
                label: "重点跟踪",
                children: tableContent(result, query.isFetching, store),
              },
              {
                key: "gain",
                label: "涨幅榜",
                children: tableContent(result, query.isFetching, store),
              },
              {
                key: "risk",
                label: "风险榜",
                children: tableContent(result, query.isFetching, store),
              },
              {
                key: "performance",
                label: "策略表现",
                children: result?.performance.length ? (
                  <StrategyTrackingPerformanceTable items={result.performance} />
                ) : (
                  <TqEmpty title="暂无策略表现" description="当前筛选条件下还没有可聚合的推荐样本。" />
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
                key: "diagnostics",
                label: "复盘诊断",
                children: result ? (
                  <StrategyTrackingDiagnosticsPanel result={result} weeklyReport={weeklyReportQuery} viewMode={store.viewMode} />
                ) : (
                  <TqEmpty title="暂无复盘诊断" description="当前筛选条件下没有可诊断样本。" />
                ),
              },
            ]}
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
    </section>
  );
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
  const preset = tabParams(store.tab);
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

function filterNotice(store: StrategyTrackingStoreState): string {
  if (store.boardFilter === "main_only") return "已隐藏创业板、科创板等非主板股票，仅展示主板样本。";
  const hidden = [store.excludeChinext ? "创业板" : "", store.excludeStar ? "科创板" : ""].filter(Boolean).join("、");
  return `已隐藏${hidden}股票，仅影响当前页面展示。`;
}
