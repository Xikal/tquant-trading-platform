import { Button, Input } from "antd";
import { useMemo } from "react";
import { backtestsApi, type EtfT0BacktestTrade, type EtfT0HeatmapCell, type EtfT0RegimeValidation } from "../../api/backtests";
import { useBacktestResearchUiStore } from "../../stores/backtestResearchUiStore";
import { DataTable } from "../../ui/table/DataTable";
import { formatInteger, formatMoney, formatNumber, formatPct, formatPrice, toneFromNumber } from "./backtestDisplay";
import { Empty, Metric, PanelTitle, TextField } from "./BacktestResearchShared";
import {
  BACKTEST_MINI_METRICS_STYLE,
  BACKTEST_RESEARCH_CARD_STYLE,
  BACKTEST_RESEARCH_CARD_WIDE_STYLE,
  BACKTEST_RESEARCH_FORM_STYLE,
  BACKTEST_RESEARCH_NOTE_STYLE,
  BACKTEST_RESULT_BLOCK_STYLE,
  backtestToneTextStyle,
} from "./backtestResearchStyles";
import { BACKTEST_ERROR_STYLE } from "./backtestPageLayoutStyles";
import { combineBacktestStyles } from "./backtestStyles";
import { EtfT0OosPanel } from "./EtfT0OosPanel";

const SAMPLE_BARS = JSON.stringify([
  ...Array.from({ length: 17 }, (_item, index) => _bar(index, 10.0)),
  _bar(17, 9.95),
  _bar(18, 9.9),
  _bar(19, 9.85),
  _bar(20, 9.86),
  _bar(21, 9.88),
  _bar(22, 9.92),
  _bar(23, 9.96),
  _bar(24, 10.0),
  _bar(25, 10.02),
], null, 2);

const REGIME_VALIDATION_ROWS = [
  ["牛市", "趋势过滤必须避免把顺势上涨误判为均值回归。"],
  ["震荡", "重点观察 VWAP/布林回归后的期望收益和日内次数。"],
  ["熊市", "必须验证连续止损、单日亏损暂停和轻仓约束。"],
  ["退潮", "市场宽度弱或龙头断层时应降为观察/禁止执行。"],
  ["强反弹", "避免在急反弹里过早做反T，需跟踪指数联动确认。"],
] as const;

export function EtfT0BacktestPanel() {
  const state = useBacktestResearchUiStore((store) => store.etfT0);
  const setState = useBacktestResearchUiStore((store) => store.setEtfT0);
  const barsText = state.barsText || SAMPLE_BARS;
  const bars = useMemo(() => parseBars(barsText), [barsText]);

  async function runBacktest() {
    setState({ error: "" });
    if (!bars.length) {
      setState({ error: "分钟线 JSON 为空或格式不正确。" });
      return;
    }
    setState({ loading: true });
    try {
      const response = await backtestsApi.runEtfT0MinuteBacktest({
        symbol: state.symbol,
        name: state.name,
        quantity: Math.max(100, Number(state.quantity) || 10000),
        max_trades_per_day: Math.max(0, Number(state.maxTrades) || 0),
        min_signal_bars: Math.max(5, Number(state.minBars) || 20),
        params: {
          signal_max_trend_slope_abs_pct: 5,
          signal_min_net_edge_pct: 0.05,
        },
        bars,
      });
      setState({ result: response });
    } catch (err) {
      setState({ error: err instanceof Error ? err.message : "ETF T0 回测请求失败。" });
    } finally {
      setState({ loading: false });
    }
  }

  async function runResearch() {
    setState({ error: "" });
    if (!bars.length) {
      setState({ error: "分钟线 JSON 为空或格式不正确。" });
      return;
    }
    setState({ researchLoading: true });
    try {
      const response = await backtestsApi.runEtfT0Research({
        symbol: state.symbol,
        name: state.name,
        quantity: Math.max(100, Number(state.quantity) || 10000),
        max_trades_per_day: Math.max(0, Number(state.maxTrades) || 0),
        min_signal_bars: Math.max(5, Number(state.minBars) || 20),
        params: {
          signal_max_trend_slope_abs_pct: 5,
          signal_min_net_edge_pct: 0.05,
        },
        vwap_deviation_values: [0.25, 0.35, 0.45],
        oversold_rsi_values: [34, 38, 42],
        bars,
      });
      setState({ researchResult: response, result: response.base_report });
    } catch (err) {
      setState({ error: err instanceof Error ? err.message : "ETF T0 参数热力图请求失败。" });
    } finally {
      setState({ researchLoading: false });
    }
  }

  const result = state.result;
  const research = state.researchResult;
  const hasRegimeValidation = Boolean(research?.regime_validations?.length);
  return (
    <section style={combineBacktestStyles(BACKTEST_RESEARCH_CARD_STYLE, BACKTEST_RESEARCH_CARD_WIDE_STYLE)}>
      <PanelTitle title="ETF T0 分钟回测" meta={result ? `${result.trade_count} 笔` : `${bars.length} 根分钟线`} />
      <p style={BACKTEST_RESEARCH_NOTE_STYLE}>研究工具：只重放传入分钟线，不写模拟盘账本。上线前继续看样本外、参数稳定性、手续费和滑点敏感性。</p>
      <div style={BACKTEST_RESEARCH_FORM_STYLE}>
        <TextField label="ETF代码" value={state.symbol} onChange={(symbol) => setState({ symbol })} />
        <TextField label="名称" value={state.name} onChange={(name) => setState({ name })} />
        <TextField label="数量" type="number" value={state.quantity} onChange={(quantity) => setState({ quantity })} />
        <TextField label="日内次数" type="number" value={state.maxTrades} onChange={(maxTrades) => setState({ maxTrades })} />
        <TextField label="最少分钟线" type="number" value={state.minBars} onChange={(minBars) => setState({ minBars })} />
        <Button type="primary" onClick={runBacktest} loading={state.loading}>运行 ETF T0 回测</Button>
        <Button onClick={runResearch} loading={state.researchLoading}>运行参数热力图</Button>
      </div>
      <Input.TextArea
        value={barsText}
        onChange={(event) => setState({ barsText: event.target.value })}
        autoSize={{ minRows: 5, maxRows: 10 }}
        spellCheck={false}
      />
      {state.error ? <div style={BACKTEST_ERROR_STYLE}>{state.error}</div> : null}
      <div style={BACKTEST_RESULT_BLOCK_STYLE}>
        <PanelTitle title="分钟回测结果" meta={result?.version || "等待运行"} />
        {result ? (
          <>
            <div style={BACKTEST_MINI_METRICS_STYLE}>
              <Metric label="交易数" value={formatInteger(result.trade_count)} />
              <Metric label="胜率" value={formatPct(result.win_rate_pct)} />
              <Metric label="净收益" value={formatMoney(result.net_pnl)} />
              <Metric label="平均净收益" value={formatPct(result.avg_net_return_pct)} />
              <Metric label="利润因子" value={formatNumber(result.profit_factor)} />
              <Metric label="MaxDD" value={formatPct(result.max_drawdown_pct)} />
              <Metric label="持有基线" value={formatPct(result.baseline_hold_return_pct)} />
              <Metric label="拒绝信号" value={formatInteger(result.rejected_signal_count)} />
            </div>
            <DataTable<EtfT0BacktestTrade>
              rowKey={(trade, index) => `${trade.entry_time}-${trade.side}-${index}`}
              dataSource={result.trades}
              locale={{ emptyText: <Empty text="未产生 ETF T0 交易，检查 eligibility、分钟信号和风控阻断。" /> }}
              scroll={{ x: 960 }}
              columns={[
                { title: "方向", dataIndex: "side", render: (side) => side === "positive_t" ? "正T" : "反T" },
                { title: "入场", dataIndex: "entry_time" },
                { title: "退出", dataIndex: "exit_time" },
                { title: "入场价", dataIndex: "entry_price", align: "right", render: (value) => formatPrice(value) },
                { title: "退出价", dataIndex: "exit_price", align: "right", render: (value) => formatPrice(value) },
                { title: "数量", dataIndex: "quantity", align: "right", render: (value) => formatInteger(value) },
                { title: "费用", dataIndex: "total_fee", align: "right", render: (value) => formatMoney(value) },
                { title: "净收益", dataIndex: "net_pnl", align: "right", render: (value) => <span style={backtestToneTextStyle(toneFromNumber(value))}>{formatMoney(value)}</span> },
                { title: "退出原因", dataIndex: "exit_reason" },
              ]}
            />
            {result.notes?.length ? <p style={BACKTEST_RESEARCH_NOTE_STYLE}>{result.notes[0]}</p> : null}
          </>
        ) : <Empty text="粘贴 ETF 分钟线后运行，结果会显示费用、净收益、基线和逐笔成交。" />}
      </div>
      <div style={BACKTEST_RESULT_BLOCK_STYLE}>
        <PanelTitle title="参数热力图" meta={research?.version || "等待运行"} />
        <DataTable<EtfT0HeatmapCell>
          rowKey={(item) => `${item.buy_vwap_deviation_pct}-${item.oversold_rsi}`}
          dataSource={research?.heatmap ?? []}
          locale={{ emptyText: <Empty text="运行参数热力图后显示 VWAP 偏离、RSI、PF、回撤和基础门槛。" /> }}
          scroll={{ x: 960 }}
          columns={[
            { title: "VWAP阈值", dataIndex: "buy_vwap_deviation_pct", render: (value) => formatPct(value) },
            { title: "低RSI", dataIndex: "oversold_rsi", align: "right", render: (value) => formatNumber(value) },
            { title: "交易", dataIndex: "trade_count", align: "right", render: (value) => formatInteger(value) },
            { title: "胜率", dataIndex: "win_rate_pct", align: "right", render: (value) => formatPct(value) },
            { title: "净收益", dataIndex: "net_pnl", align: "right", render: (value) => <span style={backtestToneTextStyle(toneFromNumber(value))}>{formatMoney(value)}</span> },
            { title: "PF", dataIndex: "profit_factor", align: "right", render: (value) => formatNumber(value) },
            { title: "MaxDD", dataIndex: "max_drawdown_pct", align: "right", render: (value) => formatPct(value) },
            { title: "评分", dataIndex: "score", align: "right", render: (value) => formatNumber(value) },
            { title: "门槛", dataIndex: "pass_gate", render: (value) => value ? "通过" : "观察" },
          ]}
        />
      </div>
      <div style={BACKTEST_RESULT_BLOCK_STYLE}>
        <PanelTitle title="五类市场验证" meta={research ? `${research.regime_validations.length} 类` : "自动分段"} />
        {hasRegimeValidation ? (
          <DataTable<EtfT0RegimeValidation>
            rowKey={(item) => item.regime}
            dataSource={research?.regime_validations ?? []}
            scroll={{ x: 860 }}
            columns={[
              { title: "市场状态", render: (_value, item) => <strong>{item.regime}</strong> },
              { title: "样本", dataIndex: "bar_count", render: (value) => formatInteger(value) },
              { title: "交易", dataIndex: "trade_count", render: (value) => formatInteger(value) },
              { title: "净收益", dataIndex: "net_pnl", render: (value) => <span style={backtestToneTextStyle(toneFromNumber(value))}>{formatMoney(value)}</span> },
              { title: "PF", dataIndex: "profit_factor", render: (value) => formatNumber(value) },
              { title: "MaxDD", dataIndex: "max_drawdown_pct", render: (value) => formatPct(value) },
              { title: "结论", dataIndex: "verdict", render: (value) => regimeVerdictText(String(value || "")) },
            ]}
          />
        ) : (
          <DataTable
            rowKey={(item) => item[0]}
            dataSource={[...REGIME_VALIDATION_ROWS]}
            scroll={{ x: 640 }}
            columns={[
              { title: "市场状态", render: (_value, item) => <strong>{item[0]}</strong> },
              { title: "必须验收", render: (_value, item) => item[1] },
            ]}
          />
        )}
        {research?.notes?.length ? <p style={BACKTEST_RESEARCH_NOTE_STYLE}>{research.notes[0]}</p> : null}
      </div>
      <EtfT0OosPanel
        symbol={state.symbol}
        name={state.name}
        quantity={Math.max(100, Number(state.quantity) || 10000)}
        maxTradesPerDay={Math.max(0, Number(state.maxTrades) || 0)}
        minSignalBars={Math.max(5, Number(state.minBars) || 20)}
        bars={bars}
      />
    </section>
  );
}

function parseBars(raw: string) {
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => ({
        timestamp: String(item.timestamp || ""),
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
        volume: Number(item.volume || 0),
        amount: Number(item.amount || 0),
      }))
      .filter((item) => item.timestamp && item.open > 0 && item.high > 0 && item.low > 0 && item.close > 0);
  } catch {
    return [];
  }
}

function _bar(index: number, close: number) {
  const minute = 30 + index;
  const hour = 9 + Math.floor(minute / 60);
  const minuteInHour = minute % 60;
  return {
    timestamp: `2026-05-27 ${String(hour).padStart(2, "0")}:${String(minuteInHour).padStart(2, "0")}`,
    open: close,
    high: Number((close * 1.001).toFixed(4)),
    low: Number((close * 0.999).toFixed(4)),
    close,
    volume: 1000000,
    amount: close * 1000000,
  };
}

function regimeVerdictText(value: string): string {
  if (value === "pass") return "通过";
  if (value === "fail") return "失败";
  if (value === "caution") return "谨慎";
  if (value === "needs_data") return "缺数据";
  return "观察";
}
