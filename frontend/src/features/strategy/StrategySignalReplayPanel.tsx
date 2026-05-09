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
          <span>先选策略，再按股票代码查询。这里只看历史信号，不会提交新回测。</span>
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
    <div className="strategy-signal-table" role="table" aria-label="策略信号复盘">
      <div className="strategy-signal-row head" role="row">
        <span>日期</span>
        <span>标的</span>
        <span>状态</span>
        <span>评分</span>
        <span>买点/止损</span>
        <span>摘要</span>
      </div>
      {items.map((item) => (
        <article className="strategy-signal-row" role="row" key={`${item.latest_trade_date}-${item.strategy_key}-${item.symbol}`}>
          <span>{item.latest_trade_date}</span>
          <strong>{item.name || item.symbol}<small>{item.symbol}</small></strong>
          <span>{item.buy_signal_text || item.buy_signal_state}</span>
          <b>{Number(item.score || 0).toFixed(1)}</b>
          <span>{item.entry_zone || "--"} / {typeof item.stop_loss === "number" ? item.stop_loss.toFixed(3) : "--"}</span>
          <span>{item.summary || item.reasons?.[0] || "已读取物化信号"}</span>
        </article>
      ))}
    </div>
  );
}
