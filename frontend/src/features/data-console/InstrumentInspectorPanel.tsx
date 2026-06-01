import { Alert, Button, Input, Space, Tag } from "antd";
import type { InstrumentInspectorResponse } from "../../api/dataConsoleInspector";
import { InfoPill } from "../workspace-shared/WorkspaceComponents";
import styles from "./DataConsolePage.module.css";

export function InstrumentInspectorPanel({
  symbol,
  result,
  loading,
  error,
  onSymbolChange,
  onInspect,
}: {
  symbol: string;
  result: InstrumentInspectorResponse | null;
  loading: boolean;
  error: string;
  onSymbolChange: (value: string) => void;
  onInspect: () => void;
}) {
  const empty = !loading && !error && (!result || (!result.quote && !result.kline && !result.rules && !result.sector && !result.events.length));
  return (
    <div className={styles.panelBody}>
      <Space.Compact>
        <Input aria-label="单票巡检代码" value={symbol} placeholder="输入 6 位代码" onChange={(event) => onSymbolChange(event.target.value)} />
        <Button type="primary" onClick={onInspect} loading={loading}>巡检</Button>
      </Space.Compact>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {result?.partial_errors.length ? <Alert type="warning" showIcon message={result.partial_errors.join("；")} /> : null}
      {empty ? <div className={styles.empty}>未找到该标的或暂无数据</div> : null}
      {result ? (
        <div className={styles.inspectorResult}>
          <div className={styles.summaryGrid}>
            <InfoPill label="行情质量" value={result.quote?.source_quality || (result.quote?.is_stale ? "stale" : result.quote ? "ok" : "missing")} tone={result.quote?.is_stale ? "warn" : result.quote ? "neutral" : "down"} />
            <InfoPill label="K 线" value={result.kline ? `${result.kline.bars.length} 根` : "missing"} tone={result.kline ? "neutral" : "down"} />
            <InfoPill label="交易规则" value={result.rules?.turnaround_mode || "missing"} tone={result.rules ? "neutral" : "down"} />
            <InfoPill label="事件" value={`${result.events.length} 条`} />
          </div>
          <div className={styles.kvList}>
            <div className={styles.kvRow}><strong>行情</strong><span className={styles.detail}>{result.quote ? `${result.quote.name} ${result.quote.last_price} / ${result.quote.change_pct}%` : "missing"}</span></div>
            <div className={styles.kvRow}><strong>板块</strong><span className={styles.detail}>{result.sector?.sector_name || "missing"}</span></div>
            <div className={styles.kvRow}><strong>规则</strong><span className={styles.detail}>{result.rules ? `${result.rules.same_day_sell_allowed ? "可当日卖出" : "T+1"} · ${result.rules.notes}` : "missing"}</span></div>
            <div className={styles.kvRow}><strong>覆盖</strong><span>{result.partial_errors.length ? <Tag color="orange">partial</Tag> : <Tag color="green">ok</Tag>}</span></div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
