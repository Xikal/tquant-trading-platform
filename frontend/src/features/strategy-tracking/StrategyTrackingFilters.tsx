import { Checkbox, Select, Space } from "antd";
import type { StrategyMeta } from "../../api/strategies";

interface StrategyTrackingFiltersProps {
  range: number;
  strategyKey: string;
  strategyVariant: string;
  strategyFamily: string;
  signalState: string;
  lifecycleStatus: string;
  dataQuality: string;
  hitEntry: string;
  stopped: string;
  userStatus: string;
  excludeChinext: boolean;
  excludeStar: boolean;
  boardFilter: "include_all" | "main_only";
  onRangeChange: (value: number) => void;
  onStrategyKeyChange: (value: string) => void;
  onStrategyVariantChange: (value: "" | "baseline" | "front_row_weighted" | "front_row_only") => void;
  onStrategyFamilyChange: (value: string) => void;
  onSignalStateChange: (value: string) => void;
  onLifecycleStatusChange: (value: string) => void;
  onDataQualityChange: (value: string) => void;
  onHitEntryChange: (value: string) => void;
  onStoppedChange: (value: string) => void;
  onUserStatusChange: (value: string) => void;
  onExcludeChinextChange: (value: boolean) => void;
  onExcludeStarChange: (value: boolean) => void;
  onBoardFilterChange: (value: "include_all" | "main_only") => void;
  strategyMeta: StrategyMeta[];
}

export function StrategyTrackingFilters({
  range,
  strategyKey,
  strategyVariant,
  strategyFamily,
  signalState,
  lifecycleStatus,
  dataQuality,
  hitEntry,
  stopped,
  userStatus,
  excludeChinext,
  excludeStar,
  boardFilter,
  onRangeChange,
  onStrategyKeyChange,
  onStrategyVariantChange,
  onStrategyFamilyChange,
  onSignalStateChange,
  onLifecycleStatusChange,
  onDataQualityChange,
  onHitEntryChange,
  onStoppedChange,
  onUserStatusChange,
  onExcludeChinextChange,
  onExcludeStarChange,
  onBoardFilterChange,
  strategyMeta,
}: StrategyTrackingFiltersProps) {
  const strategyOptions = strategyMeta
    .filter((item) => item.enabled !== false && item.visibility === "full" && (item.tier === "core" || item.tier === "auxiliary"))
    .map((item) => ({ label: item.display_name || item.name || item.key, value: item.key }));
  return (
    <Space wrap size={8} className="strategy-tracking-filters">
      <Select size="small" value={range} onChange={onRangeChange} style={{ width: 110 }} options={[
        { label: "今日", value: 1 },
        { label: "近 7 日", value: 7 },
        { label: "近 30 日", value: 30 },
        { label: "近 60 日", value: 60 },
      ]} />
      <Select
        size="small"
        value={strategyVariant}
        onChange={(value) => onStrategyVariantChange(value as "" | "baseline" | "front_row_weighted" | "front_row_only")}
        style={{ width: 140 }}
        options={[
        { label: "全部策略线", value: "" },
        { label: "原低吸", value: "baseline" },
        { label: "前排加权", value: "front_row_weighted" },
        { label: "前排极精选", value: "front_row_only" },
      ]} />
      <Select size="small" value={strategyFamily} onChange={onStrategyFamilyChange} style={{ width: 120 }} options={[
        { label: "全部策略族", value: "" },
        { label: "核心", value: "core" },
        { label: "辅助", value: "auxiliary" },
      ]} />
      <Select size="small" value={strategyKey} onChange={onStrategyKeyChange} style={{ width: 160 }} options={[
        { label: "全部策略", value: "" },
        ...strategyOptions,
      ]} />
      <Select size="small" value={userStatus} onChange={onUserStatusChange} style={{ width: 130 }} options={[
        { label: "全部结论", value: "" },
        { label: "可以重点看", value: "focus" },
        { label: "等计划买点", value: "wait_entry" },
        { label: "已经走弱", value: "weakening" },
        { label: "冲高后观察", value: "take_profit_watch" },
        { label: "需要复核", value: "review_needed" },
        { label: "数据不足", value: "data_missing" },
      ]} />
      <Select size="small" value={signalState} onChange={onSignalStateChange} style={{ width: 120 }} options={[
        { label: "全部信号", value: "" },
        { label: "可买入", value: "buy_now" },
        { label: "小仓试买", value: "soft_buy_now" },
        { label: "接近买点", value: "near_entry" },
        { label: "观察确认", value: "observe_confirmed" },
      ]} />
      <Select size="small" value={lifecycleStatus} onChange={onLifecycleStatusChange} style={{ width: 130 }} options={[
        { label: "全部状态", value: "" },
        { label: "仍在跟踪", value: "active" },
        { label: "止盈观察", value: "completed_profit" },
        { label: "跌破止损", value: "stopped" },
        { label: "超过周期", value: "expired" },
        { label: "数据不足", value: "data_unavailable" },
      ]} />
      <Select size="small" value={dataQuality} onChange={onDataQualityChange} style={{ width: 120 }} options={[
        { label: "全部质量", value: "" },
        { label: "完整", value: "ok" },
        { label: "部分", value: "partial" },
        { label: "不足", value: "unavailable" },
      ]} />
      <Select size="small" value={hitEntry} onChange={onHitEntryChange} style={{ width: 120 }} options={[
        { label: "全部买点", value: "" },
        { label: "已触达买点", value: "true" },
        { label: "未触达买点", value: "false" },
      ]} />
      <Select size="small" value={stopped} onChange={onStoppedChange} style={{ width: 120 }} options={[
        { label: "全部止损", value: "" },
        { label: "已跌破止损", value: "true" },
        { label: "未跌破止损", value: "false" },
      ]} />
      <Select size="small" value={boardFilter} onChange={onBoardFilterChange} style={{ width: 120 }} options={[
        { label: "全部市场板", value: "include_all" },
        { label: "只看主板", value: "main_only" },
      ]} />
      <Checkbox checked={excludeChinext} onChange={(event) => onExcludeChinextChange(event.target.checked)}>屏蔽创业板</Checkbox>
      <Checkbox checked={excludeStar} onChange={(event) => onExcludeStarChange(event.target.checked)}>屏蔽科创板</Checkbox>
    </Space>
  );
}
