export const STRATEGY_OPTIONS = [
  ["first_board", "首板回调"],
  ["volume_shrink", "量能低吸"],
  ["late_session_strong_support", "收盘强势承接"],
  ["core_midcap_vwap_ma5_retrace", "中军回踩"],
  ["sector_mainline_first_divergence_low_buy", "主线首分歧"],
] as const;

export type StrategyOption = readonly [string, string];
