import { Alert, Tabs } from "antd";
import type { StrategyMeta } from "../../api/strategies";
import { useStrategyTrackingStore } from "../../stores/strategyTrackingStore";
import { TqEmpty, TqErrorResult } from "../../ui/feedback/StateViews";
import type { StrategyTrackingParams } from "../../types";
import { useStrategyTrackingDetail, useStrategyTrackingItems } from "./queries";
import { StrategyTrackingDetailDrawer } from "./StrategyTrackingDetailDrawer";
import { StrategyTrackingFilters } from "./StrategyTrackingFilters";
import { StrategyTrackingPerformanceTable } from "./StrategyTrackingPerformanceTable";
import { StrategyTrackingReviewPanel } from "./StrategyTrackingReviewPanel";
import { StrategyTrackingSummaryBar } from "./StrategyTrackingSummaryBar";
import { StrategyTrackingTable } from "./StrategyTrackingTable";
import { boolParam, tabParams } from "./strategyTrackingFormatters";

type StrategyTrackingStoreState = ReturnType<typeof useStrategyTrackingStore.getState>;

export function StrategyTrackingPage({ strategyMeta }: { strategyMeta: StrategyMeta[] }) {
  const store = useStrategyTrackingStore();
  const params = buildParams(store);
  const query = useStrategyTrackingItems(params);
  const detailQuery = useStrategyTrackingDetail(store.selectedItemId);
  const result = query.data;
  const errorText = query.error instanceof Error ? query.error.message : "";

  return (
    <section className="workspace-page strategy-tracking-page">
      <div className="workspace-page-heading">
        <div>
          <h1>策略跟踪</h1>
          <p>生产策略推荐后的买点、涨幅、回撤和生命周期复盘。</p>
        </div>
      </div>
      <StrategyTrackingFilters
        range={store.range}
        strategyKey={store.strategyKey}
        strategyFamily={store.strategyFamily}
        signalState={store.signalState}
        lifecycleStatus={store.lifecycleStatus}
        dataQuality={store.dataQuality}
        hitEntry={store.hitEntry}
        stopped={store.stopped}
        strategyMeta={strategyMeta}
        onRangeChange={store.setRange}
        onStrategyKeyChange={store.setStrategyKey}
        onStrategyFamilyChange={store.setStrategyFamily}
        onSignalStateChange={store.setSignalState}
        onLifecycleStatusChange={store.setLifecycleStatus}
        onDataQualityChange={store.setDataQuality}
        onHitEntryChange={store.setHitEntry}
        onStoppedChange={store.setStopped}
      />
      {result ? <StrategyTrackingSummaryBar summary={result.summary} /> : null}
      {result ? <StrategyTrackingReviewPanel summary={result.summary} performance={result.performance} /> : null}
      {result?.partial_errors.length ? (
        <Alert type="warning" showIcon title={result.partial_errors.slice(0, 2).join("；")} />
      ) : null}
      {errorText ? <TqErrorResult title="策略跟踪加载失败" description={errorText} onRetry={() => void query.refetch()} /> : null}
      {!errorText ? (
        <Tabs
          activeKey={store.tab}
          onChange={(key) => store.setTab(key as typeof store.tab)}
          items={[
            {
              key: "active",
              label: "今日有效",
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
          ]}
        />
      ) : null}
      <StrategyTrackingDetailDrawer
        open={Boolean(store.selectedItemId)}
        loading={detailQuery.isFetching}
        detail={detailQuery.data}
        errorText={detailQuery.error instanceof Error ? detailQuery.error.message : ""}
        onClose={() => store.setSelectedItemId(null)}
      />
    </section>
  );
}

function tableContent(result: ReturnType<typeof useStrategyTrackingItems>["data"], loading: boolean, store: StrategyTrackingStoreState) {
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
      onPageChange={store.setPagination}
      onOpenDetail={store.setSelectedItemId}
    />
  );
}

function buildParams(store: StrategyTrackingStoreState): StrategyTrackingParams {
  const preset = tabParams(store.tab);
  return {
    range: store.range,
    strategy_key: store.strategyKey || undefined,
    strategy_family: store.strategyFamily || undefined,
    signal_state: store.signalState || undefined,
    status: store.lifecycleStatus || preset.status,
    data_quality: store.dataQuality || undefined,
    hit_entry: boolParam(store.hitEntry),
    stopped: boolParam(store.stopped) ?? preset.stopped,
    sort: store.sort,
    limit: store.pageSize,
    offset: (store.page - 1) * store.pageSize,
  };
}
