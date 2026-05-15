import { useEffect, useRef, useState } from "react";
import { strategiesApi, type StrategySignalReplayItem } from "../../api/strategies";
import { EmptyPlaceholder, ErrorBanner, SkeletonBlock } from "../../components/shared/Feedback";
import { NumberField, SearchField, SelectField } from "../../components/shared/FormFields";
import { useBacktestStrategyOptions } from "../backtest/useBacktestStrategyOptions";

export function StrategySignalReplayPanel({ title }: { title: string }) {
  const [symbol, setSymbol] = useState("");
  const [strategy, setStrategy] = useState("first_board");
  const [items, setItems] = useState<StrategySignalReplayItem[]>([]);
  const [lookbackDays, setLookbackDays] = useState("60");
  const [onlyFailures, setOnlyFailures] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requestSeqRef = useRef(0);
  const strategyOptions = useBacktestStrategyOptions();

  function loadReplay(nextSymbol: string, nextLimit: number) {
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError("");
    void strategiesApi.listSignalReplay(strategy, nextSymbol, nextLimit, Number(lookbackDays) || 60)
      .then((result) => {
        if (requestSeqRef.current === requestSeq) setItems(result.items ?? []);
      })
      .catch((err) => {
        if (requestSeqRef.current === requestSeq) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (requestSeqRef.current === requestSeq) setLoading(false);
      });
  }

  useEffect(() => {
    loadReplay("", 12);
    return () => {
      requestSeqRef.current += 1;
    };
  }, [strategy, lookbackDays]);

  return (
    <section className="panel strategy-signals-panel">
      <div className="strategy-panel-title">
        <div>
          <h2>{title}</h2>
          <span>用案例方式看最近信号：当时建议什么价格、止损在哪里、为什么入选。</span>
        </div>
      </div>
      <div className="strategy-signal-grid">
        <SearchField label="标的搜索" value={symbol} placeholder="输入代码或名称" onChange={setSymbol} />
        <SelectField
          label="策略"
          value={strategy}
          onChange={(event) => setStrategy(event.target.value)}
          options={strategyOptions.map(([value, label]) => ({ value, label }))}
        />
        <NumberField
          label="交易日窗口"
          suffix="个交易日"
          value={lookbackDays}
          min={1}
          max={120}
          onChange={(event) => setLookbackDays(event.target.value)}
        />
        <button type="button" className="primary" onClick={() => loadReplay(symbol, 24)} disabled={loading}>
          {loading ? "查询中" : "查询信号"}
        </button>
      </div>
      {error ? <ErrorBanner message={`信号复盘查询失败：${error}`} /> : null}
      <SignalReplayRows
        items={items}
        symbol={symbol}
        strategy={strategy}
        loading={loading}
        lookbackDays={Number(lookbackDays) || 60}
        onlyFailures={onlyFailures}
        onToggleFailures={() => setOnlyFailures((value) => !value)}
      />
    </section>
  );
}

function SignalReplayRows({
  items,
  symbol,
  strategy,
  loading,
  lookbackDays,
  onlyFailures,
  onToggleFailures,
}: {
  items: StrategySignalReplayItem[];
  symbol: string;
  strategy: string;
  loading: boolean;
  lookbackDays: number;
  onlyFailures: boolean;
  onToggleFailures: () => void;
}) {
  if (loading) {
    return <SkeletonBlock rows={4} title />;
  }
  if (!items.length) {
    return (
      <EmptyPlaceholder
        title="暂无信号复盘"
        description={symbol ? `${symbol} 在 ${strategy} 最近 ${lookbackDays} 个交易日内无信号记录，可扩大窗口或切换策略。` : `该策略最近 ${lookbackDays} 个交易日内无信号记录，可扩大窗口或切换策略。`}
      />
    );
  }
  const summary = summarizeReplay(items);
  const visibleItems = onlyFailures ? items.filter((item) => outcomeTone(item) === "bad") : items;
  return (
    <>
      <div className="strategy-signal-summary">
        <strong>过去 {lookbackDays} 天共 {items.length} 个信号</strong>
        <span>✅ {summary.good} 盈利/强信号</span>
        <span>❌ {summary.bad} 亏损/放弃</span>
        <span>⏳ {summary.pending} 待验证</span>
        <button type="button" className={onlyFailures ? "active" : ""} onClick={onToggleFailures}>
          只看失败信号
        </button>
      </div>
      {!visibleItems.length ? (
        <EmptyPlaceholder title="没有失败信号" description="当前筛选条件下没有可归类为失败的信号。" />
      ) : null}
      <div className="strategy-signal-case-grid" aria-label="策略信号案例">
      {visibleItems.map((item) => (
        <article className="strategy-signal-case" key={`${item.latest_trade_date}-${item.strategy_key}-${item.symbol}`}>
          <header>
            <div>
              <strong>{item.name || item.symbol}</strong>
              <span>{item.symbol} · {item.latest_trade_date}</span>
            </div>
            <b className={`signal-state ${outcomeTone(item)}`}>{outcomeLabel(item)}</b>
          </header>
          <div className="signal-case-metrics">
            <span>建议区间 <b>{item.entry_zone || "--"}</b></span>
            <span>止损价 <b>{typeof item.stop_loss === "number" ? item.stop_loss.toFixed(3) : "--"}</b></span>
            <span>信号强度 <b>{scoreLabel(item.score)}</b></span>
          </div>
          <p>{item.summary || item.reasons?.[0] || "该票进入策略观察池，建议结合买点区间和止损价复盘。"}</p>
          <details className="strategy-signal-detail">
            <summary>展开当时的买入依据</summary>
            <p>{signalReasonText(item)}</p>
          </details>
        </article>
      ))}
      </div>
    </>
  );
}

function stateLabel(state?: string, fallback?: string): string {
  if (state === "buy_now") return "立即可买";
  if (state === "soft_buy_now") return "小仓试买";
  if (state === "near_entry") return "等待确认";
  if (state === "watch") return "继续观察";
  if (state === "avoid") return "今天放弃";
  return fallback || "等待";
}

function stateTone(state?: string): string {
  if (state === "buy_now" || state === "soft_buy_now") return "ok";
  if (state === "near_entry" || state === "watch") return "warn";
  if (state === "avoid") return "bad";
  return "neutral";
}

function outcomeLabel(item: StrategySignalReplayItem): string {
  const pnl = resolvePnl(item);
  if (typeof pnl === "number") return pnl >= 0 ? `盈利 ${pnl.toFixed(2)}%` : `亏损 ${pnl.toFixed(2)}%`;
  if (item.outcome === "win" || item.outcome === "success") return "盈利";
  if (item.outcome === "loss" || item.outcome === "failed") return "亏损";
  if (item.buy_signal_state === "avoid") return "今天放弃";
  return stateLabel(item.buy_signal_state, item.buy_signal_text);
}

function outcomeTone(item: StrategySignalReplayItem): string {
  const pnl = resolvePnl(item);
  if (typeof pnl === "number") return pnl >= 0 ? "ok" : "bad";
  if (item.outcome === "win" || item.outcome === "success") return "ok";
  if (item.outcome === "loss" || item.outcome === "failed") return "bad";
  return stateTone(item.buy_signal_state);
}

function resolvePnl(item: StrategySignalReplayItem): number | null {
  if (typeof item.pnl_pct === "number" && Number.isFinite(item.pnl_pct)) return item.pnl_pct;
  if (typeof item.return_pct === "number" && Number.isFinite(item.return_pct)) return item.return_pct;
  return null;
}

function summarizeReplay(items: StrategySignalReplayItem[]) {
  return items.reduce(
    (acc, item) => {
      const tone = outcomeTone(item);
      if (tone === "ok") acc.good += 1;
      else if (tone === "bad") acc.bad += 1;
      else acc.pending += 1;
      return acc;
    },
    { good: 0, bad: 0, pending: 0 }
  );
}

function signalReasonText(item: StrategySignalReplayItem): string {
  if (item.reasons?.length) return item.reasons.join("；");
  const snapshotReason = typeof item.signal_snapshot?.reason === "string" ? item.signal_snapshot.reason : "";
  if (snapshotReason) return snapshotReason;
  return "后端未返回当时完整依据，可结合建议区间、止损价和信号摘要复盘。";
}

function scoreLabel(score?: number | null): string {
  if (typeof score !== "number" || !Number.isFinite(score)) return "--";
  if (score >= 85) return "强";
  if (score >= 75) return "中";
  return "弱";
}
