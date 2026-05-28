import { useEffect, useMemo } from "react";
import { Button } from "antd";
import { api } from "../../api/client";
import { etfT0OosApi } from "../../api/etfT0Oos";
import { useStrategyHubUiStore } from "../../stores/strategyHubStore";
import { DataTable } from "../../ui/table/DataTable";
import { formatAmount, formatInteger, formatPct } from "../workspace-shared/workspaceFormatters";
import { Empty, Metric, PanelTitle } from "../backtest/BacktestResearchShared";
import {
  BACKTEST_MINI_METRICS_STYLE,
  BACKTEST_RESEARCH_CARD_STYLE,
  BACKTEST_RESEARCH_CARD_WIDE_STYLE,
  BACKTEST_RESEARCH_FORM_STYLE,
  BACKTEST_RESEARCH_NOTE_STYLE,
  BACKTEST_RESULT_BLOCK_STYLE,
} from "../backtest/backtestResearchStyles";
import { BACKTEST_ERROR_STYLE } from "../backtest/backtestPageLayoutStyles";
import { combineBacktestStyles } from "../backtest/backtestStyles";

export function EtfT0StrategyStatusPanel() {
  const { universe, snapshots, oosLatest, loading, error } = useStrategyHubUiStore((store) => store.etfT0);
  const setState = useStrategyHubUiStore((store) => store.setEtfT0);
  const symbols = useMemo(() => (universe?.items ?? []).filter((item) => item.same_day_sell_allowed).slice(0, 6).map((item) => item.symbol), [universe]);

  useEffect(() => {
    void loadUniverse();
  }, []);

  async function loadUniverse() {
    setState({ loading: true, error: "" });
    try {
      const [response, oos] = await Promise.all([
        api.getEtfUniverse("", false),
        etfT0OosApi.latest().catch(() => null),
      ]);
      setState({ universe: response, oosLatest: oos });
    } catch (err) {
      setState({ error: err instanceof Error ? err.message : "ETF universe 加载失败。" });
    } finally {
      setState({ loading: false });
    }
  }

  async function loadSnapshots() {
    if (!symbols.length) return;
    setState({ loading: true, error: "" });
    try {
      setState({ snapshots: await api.getEtfMinuteSnapshots(symbols, "1m", 30) });
    } catch (err) {
      setState({ error: err instanceof Error ? err.message : "ETF 分钟快照加载失败。" });
    } finally {
      setState({ loading: false });
    }
  }

  return (
    <section style={combineBacktestStyles(BACKTEST_RESEARCH_CARD_STYLE, BACKTEST_RESEARCH_CARD_WIDE_STYLE)}>
      <PanelTitle
        title="ETF T0 策略状态"
        meta={universe ? `${universe.t0_enabled_count}/${universe.total} 可T+0` : "待加载"}
        action={<Button size="small" onClick={loadSnapshots} loading={loading} disabled={!symbols.length}>刷新分钟质量</Button>}
      />
      <p style={BACKTEST_RESEARCH_NOTE_STYLE}>研究/生产边界：ETF universe 只定义 eligibility 与交易约束；Go 只读分钟快照；Python 继续生成 ETF 做T信号和模拟盘执行门禁。</p>
      {error ? <div style={BACKTEST_ERROR_STYLE}>{error}</div> : null}
      <div style={BACKTEST_MINI_METRICS_STYLE}>
        <Metric label="Universe版本" value={universe?.version || "--"} />
        <Metric label="审计路径" value={universe?.audit_scope || "--"} />
        <Metric label="快照质量" value={snapshots?.data_quality || "未刷新"} />
        <Metric label="缺失标的" value={formatInteger(snapshots?.missing?.length ?? 0)} />
        <Metric label="OOS阶段" value={oosLatest?.available ? stageText(oosLatest.stage) : "未验证"} />
        <Metric label="OOS版本" value={oosLatest?.dataset_version || "--"} />
      </div>
      <DataTable
        rowKey="symbol"
        loading={loading && !universe}
        dataSource={(universe?.items ?? []).slice(0, 12)}
        locale={{ emptyText: <Empty text="暂无 ETF universe 数据，检查研究权限或后端 /market/etf-universe。" /> }}
        scroll={{ x: 960 }}
        columns={[
          { title: "ETF", render: (_value, item) => <strong>{item.symbol} {item.name}</strong> },
          { title: "分类", dataIndex: "category" },
          { title: "T+0", render: (_value, item) => item.same_day_sell_allowed ? "允许" : "禁止" },
          { title: "跟踪指数", dataIndex: "tracking_index" },
          { title: "最低成交额", dataIndex: "min_amount", align: "right", render: (value) => formatAmount(value) },
          { title: "最大价差", dataIndex: "max_spread_bps", align: "right", render: (value) => `${value} bps` },
          { title: "说明", dataIndex: "notes" },
        ]}
      />
      <div style={BACKTEST_RESULT_BLOCK_STYLE}>
        <PanelTitle title="Go 分钟快照诊断" meta={snapshots ? `${snapshots.items.length} 只` : "未刷新"} />
        {snapshots ? (
          <DataTable
            rowKey="symbol"
            dataSource={snapshots.items}
            scroll={{ x: 840 }}
            columns={[
              { title: "ETF", dataIndex: "symbol" },
              { title: "分钟线", dataIndex: "bar_count", align: "right", render: (value) => formatInteger(value) },
              { title: "最新价", dataIndex: "latest_price", align: "right" },
              { title: "成交额", dataIndex: "total_amount", align: "right", render: (value) => formatAmount(value) },
              { title: "质量", dataIndex: "data_quality" },
              { title: "策略决策", dataIndex: "strategy_decision" },
              { title: "说明", dataIndex: "note" },
            ]}
          />
        ) : (
          <div style={BACKTEST_RESEARCH_FORM_STYLE}>
            <span style={BACKTEST_RESEARCH_NOTE_STYLE}>点击“刷新分钟质量”后展示 Go 只读数据质量；该结果不会替代 Python ETF 做T信号。</span>
          </div>
        )}
        {snapshots?.notes?.length ? <p style={BACKTEST_RESEARCH_NOTE_STYLE}>{snapshots.notes[0]}</p> : null}
        <p style={BACKTEST_RESEARCH_NOTE_STYLE}>上线门槛：分钟快照 fresh、无缺失、模拟盘连续观察、ETF T0 回测与基线/样本外验证通过后，才允许从研究进入候选生产状态。</p>
        <p style={BACKTEST_RESEARCH_NOTE_STYLE}>OOS 门槛：{oosLatest?.available ? `${oosLatest.verdict} / ${oosLatest.gate_reasons[0] || "无阻断原因"}` : "尚未完成真实 OOS 验证，ETF T0 维持研究观察。"}</p>
        <p style={BACKTEST_RESEARCH_NOTE_STYLE}>验收指标：胜率、期望收益、Profit Factor、最大回撤、Calmar、Sharpe、换手率、容量、滑点敏感性，且至少覆盖牛市、震荡、熊市、退潮、强反弹五类市场。</p>
        {universe ? <p style={BACKTEST_RESEARCH_NOTE_STYLE}>{universe.notes[0]}</p> : null}
        {snapshots ? <p style={BACKTEST_RESEARCH_NOTE_STYLE}>分钟快照缺失率：{formatPct(snapshots.missing.length / Math.max(symbols.length, 1) * 100)}</p> : null}
      </div>
    </section>
  );
}

function stageText(stage: string): string {
  if (stage === "paper_small") return "小仓模拟";
  if (stage === "candidate_production") return "生产候选";
  return "研究观察";
}
