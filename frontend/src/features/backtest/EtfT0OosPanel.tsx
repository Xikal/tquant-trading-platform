import { Button, Tag } from "antd";
import { useEffect } from "react";

import { etfT0OosApi } from "../../api/etfT0Oos";
import { SelectField } from "../../components/shared/FormFields";
import { useEtfT0OosStore } from "../../stores/etfT0OosStore";
import { useServerState } from "../../state/serverState";
import type {
  EtfT0OosDataset,
  EtfT0OosLatestResponse,
  EtfT0OosRegimeSegment,
  EtfT0OosValidationResponse,
} from "../../types/etfT0Oos";
import { VirtualGrid } from "../../ui/grid/VirtualGrid";
import { formatInteger, formatNumber, formatPct } from "./backtestDisplay";
import { Empty, Metric, PanelTitle } from "./BacktestResearchShared";
import {
  BACKTEST_MINI_METRICS_STYLE,
  BACKTEST_RESEARCH_FORM_STYLE,
  BACKTEST_RESEARCH_NOTE_STYLE,
  BACKTEST_RESULT_BLOCK_STYLE,
} from "./backtestResearchStyles";
import { BACKTEST_ERROR_STYLE } from "./backtestPageLayoutStyles";

interface EtfT0OosPanelProps {
  symbol: string;
  name: string;
  quantity: number;
  maxTradesPerDay: number;
  minSignalBars: number;
  bars: Array<{ timestamp: string; open: number; high: number; low: number; close: number; volume: number; amount: number }>;
}

const ETF_T0_OOS_SERVER_KEYS = {
  datasets: ["backtest", "etf-t0-oos", "datasets"] as const,
  latest: ["backtest", "etf-t0-oos", "latest"] as const,
  validation: ["backtest", "etf-t0-oos", "validation"] as const,
};

export function EtfT0OosPanel({
  symbol,
  name,
  quantity,
  maxTradesPerDay,
  minSignalBars,
  bars,
}: EtfT0OosPanelProps) {
  const [datasets, setDatasets] = useServerState<EtfT0OosDataset[]>(ETF_T0_OOS_SERVER_KEYS.datasets, []);
  const selectedDatasetKey = useEtfT0OosStore((state) => state.selectedDatasetKey);
  const [latest, setLatest] = useServerState<EtfT0OosLatestResponse | null>(ETF_T0_OOS_SERVER_KEYS.latest, null);
  const [validation, setValidation] = useServerState<EtfT0OosValidationResponse | null>(ETF_T0_OOS_SERVER_KEYS.validation, null);
  const loading = useEtfT0OosStore((state) => state.loading);
  const error = useEtfT0OosStore((state) => state.error);
  const setSelectedDatasetKey = useEtfT0OosStore((state) => state.setSelectedDatasetKey);
  const setLoading = useEtfT0OosStore((state) => state.setLoading);
  const setError = useEtfT0OosStore((state) => state.setError);
  const selectedDataset = datasets.find((item) => item.dataset_key === selectedDatasetKey) ?? datasets[0] ?? null;

  useEffect(() => {
    void loadDatasets();
  }, []);

  async function loadDatasets() {
    setLoading(true);
    setError("");
    try {
      const [datasetResponse, latestResponse] = await Promise.all([
        etfT0OosApi.listDatasets(),
        etfT0OosApi.latest(),
      ]);
      const nextDatasets = datasetResponse.items ?? [];
      setDatasets(nextDatasets);
      if (!selectedDatasetKey && nextDatasets[0]?.dataset_key) {
        setSelectedDatasetKey(nextDatasets[0].dataset_key);
      }
      setLatest(latestResponse);
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "OOS 数据集加载失败。");
    } finally {
      setLoading(false);
    }
  }

  async function validateOos() {
    if (!selectedDatasetKey || !bars.length) {
      setError("请选择 OOS 数据集并提供分钟线。");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await etfT0OosApi.validate({
        dataset_key: selectedDatasetKey,
        symbol,
        name,
        quantity,
        max_trades_per_day: maxTradesPerDay,
        min_signal_bars: minSignalBars,
        params: {
          signal_max_trend_slope_abs_pct: 5,
          signal_min_net_edge_pct: 0.05,
        },
        vwap_deviation_values: [0.25, 0.35, 0.45],
        oversold_rsi_values: [34, 38, 42],
        bars,
      });
      setValidation(response);
      setLatest({
        available: true,
        run_id: response.run_id,
        created_at: "",
        dataset_key: response.dataset.dataset_key,
        dataset_version: response.dataset.version,
        checksum: response.dataset.checksum,
        symbol: response.research_report.symbol,
        name: response.research_report.name,
        stage: response.stage,
        verdict: response.verdict,
        passed: response.passed,
        gate_reasons: response.gate_reasons,
        missing_regimes: response.missing_regimes,
        quality: response.dataset.quality as unknown as Record<string, unknown>,
      });
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "OOS 验证失败。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={BACKTEST_RESULT_BLOCK_STYLE}>
      <PanelTitle title="真实 OOS 验证" meta={validation ? stageText(validation.stage) : selectedDataset?.version || "待选择"} />
      <p style={BACKTEST_RESEARCH_NOTE_STYLE}>OOS 使用 manifest 中真实标注市场状态，不使用自动等分；结果只作为 research_only / paper_small / candidate_production 的只读阶段门槛。</p>
      {error ? <div style={BACKTEST_ERROR_STYLE}>{error}</div> : null}
      <div style={BACKTEST_RESEARCH_FORM_STYLE}>
        <SelectField
          label="OOS 数据集"
          value={selectedDatasetKey}
          options={datasets.map((dataset) => ({ value: dataset.dataset_key, label: `${dataset.version} / ${dataset.dataset_key}` }))}
          onChange={(event) => setSelectedDatasetKey(event.target.value)}
        />
        <Button onClick={() => void loadDatasets()} loading={loading}>刷新数据集</Button>
        <Button type="primary" onClick={() => void validateOos()} loading={loading} disabled={!selectedDatasetKey || !bars.length}>运行真实 OOS</Button>
      </div>
      <div style={BACKTEST_MINI_METRICS_STYLE}>
        <Metric label="质量" value={selectedDataset?.quality_ok ? "通过" : selectedDataset ? "未通过" : "--"} />
        <Metric label="覆盖状态" value={selectedDataset ? `${selectedDataset.covered_regimes.length}/5` : "--"} />
        <Metric label="缺失率" value={selectedDataset ? formatPct(selectedDataset.quality.missing_bar_ratio * 100) : "--"} />
        <Metric label="标的覆盖" value={selectedDataset ? formatPct(selectedDataset.quality.symbol_coverage_ratio * 100) : "--"} />
        <Metric label="最近阶段" value={latest?.available ? stageText(latest.stage) : "未验证"} />
        <Metric label="最近结论" value={latest?.verdict || "--"} />
      </div>
      <VirtualGrid<EtfT0OosRegimeSegment>
        rowKey={(item) => `${item.regime}-${item.start_time}`}
        dataSource={selectedDataset?.regime_segments ?? []}
        locale={{ emptyText: <Empty text="暂无 OOS 数据集；检查后端 manifest 或研究权限。" /> }}
        scroll={{ x: 940 }}
        columns={[
          { title: "状态", render: (_value, item) => <strong>{item.label || item.regime}</strong> },
          { title: "区间", render: (_value, item) => `${item.start_time} ~ ${item.end_time}` },
          { title: "置信度", dataIndex: "confidence", align: "right", render: (value) => formatNumber(value) },
          { title: "来源", dataIndex: "source" },
          { title: "说明", dataIndex: "notes" },
        ]}
      />
      {validation ? (
        <>
          <div style={BACKTEST_MINI_METRICS_STYLE}>
            <Metric label="阶段" value={stageText(validation.stage)} />
            <Metric label="结论" value={validation.verdict} />
            <Metric label="通过" value={validation.passed ? "是" : "否"} />
            <Metric label="交易数" value={formatInteger(validation.research_report.base_report.trade_count)} />
            <Metric label="热力图通过点" value={formatInteger(validation.research_report.heatmap.filter((item) => item.pass_gate).length)} />
          </div>
          <VirtualGrid
            rowKey={(item) => item.regime}
            dataSource={validation.research_report.regime_validations}
            scroll={{ x: 860 }}
            columns={[
              { title: "市场", dataIndex: "regime", render: (value) => <strong>{value}</strong> },
              { title: "样本", dataIndex: "bar_count", render: (value) => formatInteger(value) },
              { title: "交易", dataIndex: "trade_count", render: (value) => formatInteger(value) },
              { title: "净收益", dataIndex: "net_pnl" },
              { title: "PF", dataIndex: "profit_factor", render: (value) => formatNumber(value) },
              { title: "结论", dataIndex: "verdict", render: (value) => <Tag color={verdictColor(String(value))}>{String(value)}</Tag> },
            ]}
          />
          {validation.gate_reasons.length ? <p style={BACKTEST_RESEARCH_NOTE_STYLE}>门槛原因：{validation.gate_reasons.join("；")}</p> : null}
        </>
      ) : null}
    </div>
  );
}

export function stageText(stage: string): string {
  if (stage === "paper_small") return "小仓模拟";
  if (stage === "candidate_production") return "生产候选";
  return "研究观察";
}

function verdictColor(value: string): string {
  if (value === "pass") return "green";
  if (value === "fail" || value === "blocked") return "red";
  if (value === "needs_data") return "orange";
  return "default";
}
