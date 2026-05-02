import { lazy, Suspense, type ReactNode } from "react";
import type { AiDecisionSupportResponse, AnalysisResponse, LowBuyPriorityBoardResult } from "../../types";
import { formatPct, normalizeLines, plainTradingText } from "./workspaceFormatters";
import type { MetricItem, StockCardView } from "./workspaceTypes";

const LazyKlineChart = lazy(() => import("./LazyKlineChart"));

export function PanelTitle({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      {actions ? <div className="actions">{actions}</div> : null}
    </div>
  );
}

export function MetricGrid({ items, className = "" }: { items: MetricItem[]; className?: string }) {
  return (
    <div className={`metric-grid ${className}`}>
      {items.map((item) => (
        <div className={`metric ${item.tone}`} key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function EditableGrid({
  fields,
}: {
  fields: Array<[string, string, (value: string) => void]>;
}) {
  return (
    <div className="form-grid">
      {fields.map(([label, value, onChange]) => (
        <label key={label}>
          <span>{label}</span>
          <input value={value} onChange={(event) => onChange(event.target.value)} />
        </label>
      ))}
    </div>
  );
}

export function StockIdentity({
  name,
  symbol,
  note,
  tags = [],
}: {
  name: string;
  symbol: string;
  note?: string;
  tags?: string[];
}) {
  return (
    <div className="stock-identity">
      <div className="identity-main">
        <strong>{name}</strong>
        <span>{symbol}</span>
      </div>
      {note ? <span className="identity-note">{note}</span> : null}
      {tags.length ? (
        <div className="identity-tags">
          {tags.map((tag) => <span key={tag}>{tag}</span>)}
        </div>
      ) : null}
    </div>
  );
}

export function StockCard({
  stock,
  actions,
  onAction,
}: {
  stock: StockCardView;
  actions?: string[];
  onAction?: (action: string) => void;
}) {
  return (
    <article className={`stock-card ${stock.tone} ${stock.highlight ? "highlight" : ""}`}>
      <StockIdentity name={stock.name} symbol={stock.symbol} note={stock.identityNote} tags={stock.identityTags} />
      <div className="stock-meta">
        <span>当前价 {stock.priceText}</span>
        <span className={stock.tone}>涨跌 {stock.changeText}</span>
        {stock.scoreText ? <span>信号分 {stock.scoreText}</span> : null}
        <span>风险 {stock.riskText}</span>
        {stock.expectedText ? <span>预期 {stock.expectedText}</span> : null}
      </div>
      {stock.badges?.length ? (
        <div className="badge-row">
          {stock.badges.map((badge) => <span key={badge}>{badge}</span>)}
        </div>
      ) : null}
      {stock.subBadges?.length ? (
        <div className="badge-row sub-badge-row">
          {stock.subBadges.map((badge) => <span key={badge}>{badge}</span>)}
        </div>
      ) : null}
      <p>{stock.actionText} · {stock.details}</p>
      {actions?.length ? (
        <div className="card-actions">
          {actions.map((action) => (
            <button type="button" className={action === "移除" ? "danger" : ""} onClick={() => onAction?.(action)} key={action}>
              {action}
            </button>
          ))}
        </div>
      ) : null}
      {stock.executionHint ? <div className="stock-execution-hint">{stock.executionHint}</div> : null}
    </article>
  );
}

export function SettingCard({
  title,
  children,
  button,
  loading,
  onSave,
}: {
  title: string;
  children: ReactNode;
  button: string;
  loading: boolean;
  onSave: () => void;
}) {
  return (
    <div className="panel setting-card">
      <PanelTitle title={title} />
      <div className="setting-fields">{children}</div>
      <button className="primary" onClick={onSave} disabled={loading}>{loading ? "保存中..." : button}</button>
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

export function StatusStrip({ loading: _loading, notice }: { loading: string; notice: string }) {
  if (!notice) {
    return null;
  }
  return (
    <div className="status-strip">
      {notice ? <span>{notice}</span> : null}
    </div>
  );
}

export function ErrorDialog({ message, onClose }: { message: string; onClose: () => void }) {
  if (!message) {
    return null;
  }
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card error-modal" role="alertdialog" aria-modal="true" aria-label="错误提示" onClick={(event) => event.stopPropagation()}>
        <div className="modal-title">
          <strong>操作失败</strong>
          <button type="button" onClick={onClose}>关闭</button>
        </div>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function StockDetailDialog({ stock, onClose, onAnalyze }: { stock: StockCardView | null; onClose: () => void; onAnalyze: (stock: StockCardView) => void }) {
  if (!stock) {
    return null;
  }
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card detail-modal" role="dialog" aria-modal="true" aria-label="信号详情" onClick={(event) => event.stopPropagation()}>
        <div className="modal-title">
          <strong>{stock.name} {stock.symbol}</strong>
          <button type="button" onClick={onClose}>关闭</button>
        </div>
        <div className="modal-metrics">
          <InfoPill label="当前价" value={stock.priceText} />
          <InfoPill label="涨跌" value={stock.changeText} />
          <InfoPill label="风险" value={stock.riskText} />
          <InfoPill label="板块" value={stock.sectorText || "--"} />
        </div>
        <p><strong>{stock.actionText}</strong></p>
        <p>{stock.details}</p>
        {stock.executionHint ? <div className="stock-execution-hint">{stock.executionHint}</div> : null}
        {stock.badges?.length ? (
          <div className="badge-row">
            {stock.badges.map((badge) => <span key={badge}>{badge}</span>)}
          </div>
        ) : null}
        {stock.subBadges?.length ? (
          <div className="badge-row sub-badge-row">
            {stock.subBadges.map((badge) => <span key={badge}>{badge}</span>)}
          </div>
        ) : null}
        <div className="card-actions modal-actions">
          <button type="button" onClick={() => onAnalyze(stock)}>分析</button>
          <button type="button" onClick={onClose}>知道了</button>
        </div>
      </div>
    </div>
  );
}

export function FamilyStrip({ priorityBoard }: { priorityBoard: LowBuyPriorityBoardResult | null }) {
  const sections = priorityBoard?.family_sections ?? [];
  if (!sections.length) {
    return null;
  }
  return (
    <div className="family-strip">
      {sections.slice(0, 4).map((section) => (
        <InfoPill
          key={section.family_key}
          label={section.family_text}
          value={`${section.total_candidates} 只 / 净胜优势 ${formatPct(section.performance?.net_win_rate, 0)}`}
        />
      ))}
    </div>
  );
}

export function AiInsightPanel({ response }: { response: AiDecisionSupportResponse }) {
  const suggestions = normalizeLines(response.insight.suggestions).map(plainTradingText);
  const warnings = normalizeLines(response.insight.warnings).map(plainTradingText);
  return (
    <div className="ai-result">
      <strong>{response.title}</strong>
      <p>{plainTradingText(response.insight.summary)}</p>
      <div className="report-pill-row">
        <span>模型 {response.model || "未配置"}</span>
        <span>置信度 {formatPct(response.insight.confidence * 100, 0)}</span>
        <span>{response.insight.enabled ? "AI 已启用" : "量化降级"}</span>
      </div>
      {response.fixed_sections ? (
        <div className="ai-fixed-grid">
          <InfoPill label="能不能买" value={response.fixed_sections.can_buy} />
          <InfoPill label="为什么" value={response.fixed_sections.why} />
          <InfoPill label="最大风险" value={response.fixed_sections.main_risk} />
          <InfoPill label="明天处理" value={response.fixed_sections.tomorrow_plan} />
        </div>
      ) : null}
      {suggestions.length ? <LineList title="执行要点" items={suggestions} /> : null}
      {warnings.length ? <LineList title="风险提示" items={warnings} /> : null}
    </div>
  );
}

export function AiInsightDialog({
  response,
  loading,
  onClose,
}: {
  response: AiDecisionSupportResponse | null;
  loading: boolean;
  onClose: () => void;
}) {
  if (!response && !loading) {
    return null;
  }
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-card ai-modal" role="dialog" aria-modal="true" aria-label="AI 解读榜单" onClick={(event) => event.stopPropagation()}>
        <div className="modal-title">
          <strong>AI 解读榜单</strong>
          <button type="button" onClick={onClose}>关闭</button>
        </div>
        {loading ? (
          <div className="empty-state">AI 正在读取榜单并生成分析...</div>
        ) : response ? (
          <AiInsightPanel response={response} />
        ) : null}
      </div>
    </div>
  );
}

export function LineList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="line-list">
      <span>{title}</span>
      <ul>
        {items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
      </ul>
    </div>
  );
}

export function MiniKline({ bars }: { bars: AnalysisResponse["bars"] }) {
  const visible = bars.filter((bar) => Number.isFinite(bar.open) && Number.isFinite(bar.close));
  if (!visible.length) {
    return <div className="chart empty-chart">等待分析后显示K线</div>;
  }
  const labels = visible.map((bar) => bar.timestamp.slice(5, 16).replace("T", " "));
  const candleData = visible.map((bar) => [
    Number(bar.open),
    Number(bar.close),
    Number(bar.low),
    Number(bar.high),
  ]);
  const closePrices = visible.map((bar) => Number(bar.close));
  const volumeData = visible.map((bar) => ({
    value: Number(bar.volume || 0),
    itemStyle: { color: Number(bar.close) >= Number(bar.open) ? "#d92d2d" : "#17965a" },
  }));
  const option = {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      confine: true,
      formatter: (params: Array<{ data?: number[]; seriesName: string; dataIndex?: number }>) => {
        const candle = params.find((item) => item.seriesName === "K线")?.data;
        if (!candle) return "";
        const index = params.find((item) => item.seriesName === "K线")?.dataIndex ?? 0;
        const label = labels[index] ?? "";
        return [
          label,
          `开 ${formatKlinePrice(candle[0])}`,
          `收 ${formatKlinePrice(candle[1])}`,
          `低 ${formatKlinePrice(candle[2])}`,
          `高 ${formatKlinePrice(candle[3])}`,
        ].join("<br/>");
      },
    },
    legend: {
      top: 2,
      right: 8,
      textStyle: { color: "#aeb8c7", fontSize: 10 },
      itemWidth: 10,
      itemHeight: 6,
    },
    grid: [
      { left: 42, right: 16, top: 28, height: "58%" },
      { left: 42, right: 16, top: "76%", height: "14%" },
    ],
    xAxis: [
      {
        type: "category",
        data: labels,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#26354a" } },
        axisLabel: { color: "#8f9caf", fontSize: 10, hideOverlap: true },
        axisTick: { show: false },
      },
      {
        type: "category",
        gridIndex: 1,
        data: labels,
        boundaryGap: true,
        axisLine: { show: false },
        axisLabel: { show: false },
        axisTick: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true,
        splitNumber: 4,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#8f9caf", fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#778395", fontSize: 9, formatter: formatKlineVolume },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: candleData,
        itemStyle: {
          color: "#d92d2d",
          color0: "#17965a",
          borderColor: "#d92d2d",
          borderColor0: "#17965a",
        },
      },
      makeMaSeries("MA5", closePrices, 5, "#f0b44c"),
      makeMaSeries("MA10", closePrices, 10, "#4f9df7"),
      makeMaSeries("MA20", closePrices, 20, "#9b7bff"),
      {
        name: "成交量",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData,
        barWidth: "58%",
      },
    ],
  };
  return (
    <div className="chart kline-chart" aria-label="分钟K线">
      <Suspense fallback={<div className="chart empty-chart">K线加载中...</div>}>
        <LazyKlineChart option={option} className="ths-kline-chart" />
      </Suspense>
    </div>
  );
}

function makeMaSeries(name: string, closePrices: number[], windowSize: number, color: string) {
  return {
    name,
    type: "line",
    data: closePrices.map((_, index) => {
      if (index < windowSize - 1) {
        return "-";
      }
      const slice = closePrices.slice(index - windowSize + 1, index + 1);
      const average = slice.reduce((sum, value) => sum + value, 0) / windowSize;
      return Number(average.toFixed(3));
    }),
    smooth: false,
    showSymbol: false,
    lineStyle: { width: 1, color },
    emphasis: { disabled: true },
  };
}

function formatKlinePrice(value?: number): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "--";
  return value >= 100 ? value.toFixed(2) : value.toFixed(3);
}

function formatKlineVolume(value?: number): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(0)}亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(0)}万`;
  return value.toFixed(0);
}
