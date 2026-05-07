import type { AnalysisResponse } from "../../types";
import { NumberField, SearchField, SelectField } from "../../components/shared/FormFields";
import { InfoPill, LineList, MetricGrid, MiniKline, PanelTitle, StockIdentity } from "./WorkspaceComponents";
import { actionStatusText, actionText, formatAmount, formatNumber, formatPct, formatPrice, plainTradingText, riskText, toneFromChange } from "./workspaceFormatters";
import type { AnalysisDraft } from "./workspaceTypes";

export function AnalysisPage({
  draft,
  setDraft,
  result,
  loading,
  onRun,
  onOpenPaperOrder,
}: {
  draft: AnalysisDraft;
  setDraft: (draft: AnalysisDraft) => void;
  result: AnalysisResponse | null;
  loading: string;
  onRun: () => void;
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
  return (
    <section className="page-grid analysis-grid">
      <div className="panel analysis-hero">
        <PanelTitle title="个股量化分析" />
        <p className="hint">先判断现在能不能动手，再给出买卖价、止损、仓位和不能操作的原因。AI 只负责解释，不改变规则。</p>
        <div className="context-row">
          <InfoPill label="操作建议" value={actionHeadline} />
          <InfoPill label="持仓限制" value={`底仓 ${draft.base_position} / 可卖 ${draft.available_position}`} />
          <InfoPill label="风险等级" value={suggestion ? riskText(suggestion.risk_level) : "--"} />
        </div>
      </div>
      <div className="panel analysis-identity">
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
        />
      </div>
      <aside className="panel analysis-control">
        <PanelTitle title="输入控制" />
        <div className="compact-form-grid">
          <SearchField label="证券代码" value={draft.symbol} placeholder="输入代码或名称" onChange={(value) => setDraft({ ...draft, symbol: value })} />
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
        <button className="primary full" onClick={onRun} disabled={loading === "analysis"}>开始分析</button>
      </aside>
      <div className="panel decision analysis-decision">
        <PanelTitle
          title={`当前建议 / ${actionHeadline}`}
          actions={
            <button
              type="button"
              onClick={() => onOpenPaperOrder({ symbol: draft.symbol, name: result?.instrument.name, price: quote?.last_price })}
              disabled={!canOpenPaperOrder}
            >
              {suggestion?.is_actionable === false ? "不建议下单" : "模拟下单"}
            </button>
          }
        />
        <p>{actionReason || "输入证券代码并点击开始分析，系统会先检查能不能做T，再给出明确的执行边界。"}</p>
        <InfoPill label="现在怎么做" value={executionText} />
        <InfoPill label="错了怎么办" value={invalidText} />
        <InfoPill label="当前能否操作" value={`${statusText}${suggestion?.why_not_execute ? ` / ${plainTradingText(suggestion.why_not_execute)}` : ""}`} />
        <InfoPill label="建议仓位" value={`${formatPct(suggestion?.position_pct, 0)} 仓位 / 预计价差 ${formatPct(suggestion?.expected_profit_pct)}`} />
        <InfoPill label="扣手续费后" value={`${formatPct(suggestion?.net_profit_pct)} / 费用约 ${formatAmount(suggestion?.estimated_fee)}`} />
        <InfoPill label="先卖后接回条件" value={plainTradingText(suggestion?.buyback_trigger) || "没有先卖后接回信号时，不需要考虑接回。"} />
        {suggestion?.fee_warning || suggestion?.liquidity_warning ? (
          <LineList title="交易成本提示" items={[suggestion.fee_warning, suggestion.liquidity_warning].filter(Boolean).map(plainTradingText)} />
        ) : null}
        {suggestion?.reasons.length ? <LineList title="主要依据" items={suggestion.reasons.slice(0, 4).map(plainTradingText)} /> : null}
      </div>
      <div className="panel chart-panel analysis-chart">
        <PanelTitle title="K线与指标" />
        <div className="chart-meta">
          <span>开 {formatPrice(quote?.open_price)}</span>
          <span>高 {formatPrice(quote?.high_price)}</span>
          <span>低 {formatPrice(quote?.low_price)}</span>
          <span>额 {formatAmount(quote?.amount)}</span>
          <span>振幅 {formatPct(result?.metrics.amplitude_pct as number | undefined)}</span>
        </div>
        <MiniKline bars={result?.bars?.slice(-60) ?? []} />
        <div className="context-row">
          <InfoPill label="买卖盘情况" value={plainTradingText(result?.microstructure.notes) || "--"} />
          <InfoPill label="成交量" value={String(result?.metrics.volume_ratio ?? "--")} />
          <InfoPill label="成交额" value={formatAmount(quote?.amount)} />
        </div>
      </div>
      <div className="panel split analysis-plan">
        <div>
          <PanelTitle title="执行计划" />
          <p>{executionText}</p>
          <p className="hint">{invalidText}</p>
          <p className="hint">
            {plainTradingText(suggestion?.strategy_notes) ||
              "先买后卖只等回落后重新走强；先卖后接回只在冲高乏力且有接回空间时执行；AI 只解释，不放宽底线规则。"}
          </p>
        </div>
        <div>
          <PanelTitle title="AI 补充说明" />
          <p>{plainTradingText(result?.ai.summary) || "默认不自动调用 AI，避免延迟和额度消耗；需要时可在榜单或复盘入口触发解读。"}</p>
          {result?.compliance_notes.length ? <LineList title="合规与假设" items={[...result.compliance_notes, ...result.assumptions].slice(0, 4)} /> : null}
        </div>
      </div>
      <div className="panel log-strip analysis-log">
        <InfoPill label="分析日志" value={result?.analysis_log_id ? `日志 #${result.analysis_log_id}` : "等待分析"} />
        <InfoPill label="不能操作原因" value={suggestion?.blocking_rules.length ? `${suggestion.blocking_rules.length} 条` : "暂无硬性原因"} />
        <InfoPill label="风险事件/盘口" value={result ? `${result.events.length} 条事件 / ${plainTradingText(result.microstructure.notes) || "盘口已检查"}` : "--"} />
        <InfoPill label="复盘记录" value={result ? "分析结果已写入研究复盘" : "--"} />
      </div>
    </section>
  );
}
