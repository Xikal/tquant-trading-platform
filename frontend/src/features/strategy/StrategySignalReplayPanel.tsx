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
      <SignalReplayRows items={items} symbol={symbol} strategy={strategy} loading={loading} lookbackDays={Number(lookbackDays) || 60} />
    </section>
  );
}

function SignalReplayRows({
  items,
  symbol,
  strategy,
  loading,
  lookbackDays,
}: {
  items: StrategySignalReplayItem[];
  symbol: string;
  strategy: string;
  loading: boolean;
  lookbackDays: number;
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
  return (
    <div className="strategy-signal-case-grid" aria-label="策略信号案例">
      {items.map((item) => (
        <article className="strategy-signal-case" key={`${item.latest_trade_date}-${item.strategy_key}-${item.symbol}`}>
          <header>
            <div>
              <strong>{item.name || item.symbol}</strong>
              <span>{item.symbol} · {item.latest_trade_date}</span>
            </div>
            <b className={`signal-state ${stateTone(item.buy_signal_state)}`}>{stateLabel(item.buy_signal_state, item.buy_signal_text)}</b>
          </header>
          <div className="signal-case-metrics">
            <span>建议区间 <b>{item.entry_zone || "--"}</b></span>
            <span>止损价 <b>{typeof item.stop_loss === "number" ? item.stop_loss.toFixed(3) : "--"}</b></span>
            <span>信号强度 <b>{scoreLabel(item.score)}</b></span>
          </div>
          <p>{item.summary || item.reasons?.[0] || "该票进入策略观察池，建议结合买点区间和止损价复盘。"}</p>
        </article>
      ))}
    </div>
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

function scoreLabel(score?: number | null): string {
  if (typeof score !== "number" || !Number.isFinite(score)) return "--";
  if (score >= 85) return "强";
  if (score >= 75) return "中";
  return "弱";
}
