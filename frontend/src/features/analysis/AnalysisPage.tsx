import type { AnalysisResponse, IntradayAnomalyResponse } from "../../types";
import { Button, Collapse } from "antd";
import { NumberField, SearchField, SelectField, TextField } from "../../components/shared/FormFields";
import { Callout, ContextRow, InfoPill, LineList, MetricGrid, MiniKline, PanelTitle, StockIdentity } from "../workspace-shared/WorkspaceComponents";
import { WorkspacePageIntro } from "../workspace-shared/WorkspacePageIntro";
import { actionStatusText, actionText, formatAmount, formatNumber, formatPct, formatPrice, plainTradingText, riskText, toneFromChange } from "../workspace-shared/workspaceFormatters";
import type { AnalysisDraft } from "../workspace-shared/workspaceTypes";

export function AnalysisPage({
  draft,
  setDraft,
  result,
  anomaly,
  batchSymbols,
  setBatchSymbols,
  batchResults,
  loading,
  onRun,
  onBatchRun,
  onOpenPaperOrder,
}: {
  draft: AnalysisDraft;
  setDraft: (draft: AnalysisDraft) => void;
  result: AnalysisResponse | null;
  anomaly: IntradayAnomalyResponse | null;
  batchSymbols: string;
  setBatchSymbols: (value: string) => void;
  batchResults: AnalysisResponse[];
  loading: string;
  onRun: () => void;
  onBatchRun: () => void;
  onOpenPaperOrder: (payload: { symbol: string; name?: string; price?: number | null }) => void;
}) {
  const suggestion = result?.suggestion;
  const quote = result?.quote;
  const actionHeadline = suggestion?.plain_action_text || (suggestion ? actionText(suggestion.action) : "等待分析");
  const canOpenPaperOrder = Boolean(draft.symbol.trim() && suggestion?.is_actionable);
  const statusText = actionStatusText(suggestion?.signal_layer, suggestion?.signal_layer_text);
  const actionReason = suggestion?.plain_action_reason || plainTradingText(suggestion?.trade_scene_text) || "--";
  const executionText =
    suggestion?.plain_execution_text ||
    `入场 ${formatPrice(suggestion?.entry_price)} · 卖出 ${formatPrice(suggestion?.exit_price)} · 止损 ${formatPrice(suggestion?.stop_loss)} · 止盈 ${formatPrice(suggestion?.take_profit)}。`;
  const invalidText =
    suggestion?.plain_invalid_condition ||
    (suggestion?.blocking_rules.length ? suggestion.blocking_rules.map(plainTradingText).join("；") : "没有硬性阻止条件");
  const uniqueReasons = (suggestion?.reasons ?? [])
    .map(plainTradingText)
    .filter((reason) => reason && reason !== actionReason);
  const decisionTone = suggestion?.is_actionable ? "up" : suggestion?.signal_layer === "watch_prepare" ? "warn" : "neutral";
  const decisionTitle = suggestion?.is_actionable
    ? `当前可以：${actionHeadline}`
    : suggestion
      ? `当前先不下单：${statusText}`
      : "输入股票后先看能不能操作";
  return (
    <section className="tq-analysis-page">
      <div className="panel tq-analysis-page__hero">
        <WorkspacePageIntro
          title="量化分析"
          summary={decisionTitle}
          tone={decisionTone}
          actions={<Button type="primary" onClick={onRun} loading={loading === "analysis"}>开始分析</Button>}
          pills={[
            { label: "证券", value: draft.symbol || "--" },
            { label: "操作建议", value: actionHeadline, tone: decisionTone },
            { label: "风险等级", value: suggestion ? riskText(suggestion.risk_level) : "--", tone: suggestion?.risk_level === "high" ? "down" : "neutral" },
            { label: "批量结果", value: String(batchResults.length) },
          ]}
        />
        {!suggestion ? (
          <Callout
            label="判断原因"
            title="系统会先检查价格、持仓、手续费、风险和失效条件。"
            tone={decisionTone}
          />
        ) : null}
      </div>
      <div className="panel tq-analysis-page__identity">
        <StockIdentity name={result?.instrument.name ?? draft.symbol} symbol={draft.symbol} />
        <MetricGrid
          items={[
            { label: "当前价", value: formatPrice(quote?.last_price), tone: "neutral" },
            { label: "涨跌", value: formatPct(quote?.change_pct), tone: toneFromChange(quote?.change_pct) },
            { label: "交易条件", value: formatNumber(suggestion?.tradability_score), tone: "neutral" },
            { label: "机会强度", value: formatNumber(suggestion?.signal_score), tone: "warn" },
            { label: "当前状态", value: statusText, tone: suggestion?.signal_layer === "strong_execute" ? "up" : suggestion?.signal_layer === "light_execute" ? "warn" : "neutral" },
            { label: "风险", value: suggestion ? riskText(suggestion.risk_level) : "--", tone: suggestion?.risk_level === "high" ? "down" : "up" },
            { label: "预计价差", value: formatPct(suggestion?.expected_profit_pct), tone: toneFromChange(suggestion?.expected_profit_pct) },
          ]}
          compact
        />
      </div>
      <aside className="panel tq-analysis-page__control">
        <PanelTitle title="输入控制" />
        <div className="tq-analysis-page__control-grid">
          <div className="tq-analysis-page__control-search">
            <SearchField label="证券代码" value={draft.symbol} placeholder="代码/名称，例 600000" onChange={(value) => setDraft({ ...draft, symbol: value })} />
          </div>
          <NumberField label="底仓" value={draft.base_position} onChange={(event) => setDraft({ ...draft, base_position: event.target.value })} />
          <NumberField label="可卖" value={draft.available_position} onChange={(event) => setDraft({ ...draft, available_position: event.target.value })} />
          <NumberField label="成本价" value={draft.cost_basis} onChange={(event) => setDraft({ ...draft, cost_basis: event.target.value })} />
        </div>
        <SelectField
          label="偏好策略"
          value={draft.prefer_strategy}
          options={[
            { value: "auto", label: "自动" },
            { value: "positive_t", label: "先买后卖" },
            { value: "negative_t", label: "先卖后接回" },
          ]}
          onChange={(event) => setDraft({ ...draft, prefer_strategy: event.target.value as AnalysisDraft["prefer_strategy"] })}
        />
        <Button type="primary" block onClick={onRun} loading={loading === "analysis"}>开始分析</Button>
      </aside>
      <div className="panel tq-analysis-page__batch">
        <PanelTitle
          title="批量分析：今日最值得关注"
          actions={<Button type="default" onClick={onBatchRun} loading={loading === "analysis-batch"}>{loading === "analysis-batch" ? "分析中..." : "批量排序"}</Button>}
        />
        <TextField
          label="多个证券代码"
          value={batchSymbols}
          placeholder="例：601288, 510300, 002594"
          onChange={(event) => setBatchSymbols(event.target.value)}
        />
        <div className="tq-analysis-page__batch-list">
          {batchResults.length ? batchResults.slice(0, 3).map((item, index) => (
            <article key={item.symbol} className="tq-analysis-page__batch-item">
              <strong>{index === 0 ? "今日最佳机会：" : `第 ${index + 1} 位：`}{item.instrument.name} {item.symbol}</strong>
              <span className="tq-analysis-page__batch-meta">{item.suggestion.plain_action_text || actionText(item.suggestion.action)} · 分数 {formatNumber(item.suggestion.signal_score)} · 风险 {riskText(item.suggestion.risk_level)}</span>
              <small className="tq-analysis-page__batch-meta">{item.suggestion.plain_action_reason || item.suggestion.reasons[0] || "等待进一步确认。"}</small>
            </article>
          )) : <p className="hint">输入 2-8 个代码，系统会按可操作性和机会强度排序。</p>}
        </div>
      </div>
      <div className="panel decision tq-analysis-page__decision">
        <PanelTitle
          title={`当前建议 / ${actionHeadline}`}
          actions={
            <Button
              type="primary"
              onClick={() => onOpenPaperOrder({ symbol: draft.symbol, name: result?.instrument.name, price: quote?.last_price })}
              disabled={!canOpenPaperOrder}
            >
              {suggestion?.is_actionable === false ? "不建议下单" : "模拟下单"}
            </Button>
          }
        />
        <InfoPill compact label="现在怎么做" value={executionText} />
        <InfoPill compact label="错了怎么办" value={invalidText} />
        <InfoPill compact label="当前能否操作" value={`${statusText}${suggestion?.why_not_execute ? ` / ${plainTradingText(suggestion.why_not_execute)}` : ""}`} />
        <InfoPill compact label="建议仓位" value={`${formatPct(suggestion?.position_pct, 0)} 仓位 / 预计价差 ${formatPct(suggestion?.expected_profit_pct)}`} />
        {suggestion?.fee_warning || suggestion?.liquidity_warning ? (
          <LineList title="交易成本提示" items={[suggestion.fee_warning, suggestion.liquidity_warning].filter(Boolean).map(plainTradingText)} />
        ) : null}
        {uniqueReasons.length ? <LineList title="主要依据" items={uniqueReasons.slice(0, 3)} /> : null}
      </div>
      {anomaly ? <div className="panel tq-analysis-page__anomaly">
        <PanelTitle title="盘中异常提醒" />
        <ContextRow>
          <InfoPill compact label="异常等级" value={anomaly.anomaly_text} tone={anomaly.anomaly_level === "high" ? "down" : anomaly.anomaly_level === "medium" ? "warn" : "neutral"} />
          <InfoPill compact label="风险分" value={formatNumber(anomaly.score)} tone={anomaly.score >= 70 ? "down" : anomaly.score >= 45 ? "warn" : "neutral"} />
          <InfoPill compact label="类型" value={plainTradingText(anomaly.pattern) || "--"} />
        </ContextRow>
        <InfoPill compact label="处理建议" value={plainTradingText(anomaly.action_hint)} />
        {anomaly.reasons.length ? <LineList title="触发原因" items={anomaly.reasons.slice(0, 3).map(plainTradingText)} /> : null}
      </div> : null}
      <div className="panel tq-analysis-page__chart">
        <PanelTitle title="K线与指标" />
        <div className="tq-analysis-page__chart-meta">
          <span>开 {formatPrice(quote?.open_price)}</span>
          <span>高 {formatPrice(quote?.high_price)}</span>
          <span>低 {formatPrice(quote?.low_price)}</span>
          <span>额 {formatAmount(quote?.amount)}</span>
          <span>振幅 {formatPct(result?.metrics.amplitude_pct as number | undefined)}</span>
        </div>
        <MiniKline bars={result?.bars?.slice(-60) ?? []} />
        <ContextRow>
          <InfoPill compact label="买卖盘情况" value={plainTradingText(result?.microstructure.notes) || "--"} />
          <InfoPill compact label="成交量" value={String(result?.metrics.volume_ratio ?? "--")} />
          <InfoPill compact label="成交额" value={formatAmount(quote?.amount)} />
        </ContextRow>
      </div>
      <div className="panel tq-analysis-page__plan">
        <Collapse
          size="small"
          items={[
            {
              key: "plan",
              label: "执行计划、AI 补充与合规假设",
              children: (
                <div className="tq-analysis-page__plan-grid">
                  <div>
                    <PanelTitle title="执行计划" />
                    <p className="hint">
                      具体入场、失效和仓位口径已在上方“当前建议”区展示；这里仅保留策略补充和合规假设，避免重复同一执行句。
                    </p>
                    <p className="hint">
                      {plainTradingText(suggestion?.strategy_notes) ||
                        "先买后卖只等回落后重新走强；先卖后接回只在冲高乏力且有接回空间时执行；AI 只解释，不放宽底线规则。"}
                    </p>
                  </div>
                  {result?.ai.summary ? <div>
                    <PanelTitle title="AI 补充说明" />
                    <p>{plainTradingText(result.ai.summary)}</p>
                    {result?.compliance_notes.length ? <LineList title="合规与假设" items={[...result.compliance_notes, ...result.assumptions].slice(0, 4)} /> : null}
                  </div> : null}
                </div>
              ),
            },
          ]}
        />
      </div>
    </section>
  );
}
