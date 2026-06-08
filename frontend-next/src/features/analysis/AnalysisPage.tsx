import type { ColumnDef } from "@tanstack/solid-table";
import { createQuery } from "@tanstack/solid-query";
import { useLocation, useNavigate } from "@tanstack/solid-router";
import { For, Show, createEffect, createMemo, createSignal, onCleanup, untrack } from "solid-js";
import { apiClient } from "../../shared/api/client";
import { errorMessage } from "../../shared/api/errors";
import { queryKeys } from "../../shared/api/queryKeys";
import { KlineChart } from "../../shared/charts/KlineChart";
import { DataTable } from "../../shared/ui/DataTable";
import { PageScaffold } from "../shared/PageScaffold";
import { numberText, pctText, readRecord, text } from "../shared/dataAccess";
import {
  aiLines,
  analysisReason,
  anomalyRecord,
  buildAnalysisPayload,
  chartPoints,
  defaultAnalysisForm,
  keyLevelRows,
  parseSymbols,
  paperOrderDraftSearch,
  quoteRecord,
  runAnalysisWorkflow,
  runBatchAnalysis,
  type AnalysisFormState,
  type AnalysisSnapshot,
  type BatchAnalysisRow,
} from "./analysisModel";
import "./analysisSlice.css";

export function AnalysisPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const routeSymbol = createMemo(() => symbolFromSearch(location().search));
  const [form, setForm] = createSignal<AnalysisFormState>(defaultAnalysisForm);
  const [snapshot, setSnapshot] = createSignal<AnalysisSnapshot | null>(null);
  const [batchRows, setBatchRows] = createSignal<BatchAnalysisRow[]>([]);
  const [status, setStatus] = createSignal<"idle" | "loading" | "batch" | "error">("idle");
  const [message, setMessage] = createSignal("");
  let activeRequest: AbortController | null = null;

  const updateForm = <K extends keyof AnalysisFormState>(key: K, value: AnalysisFormState[K]) => setForm((current) => ({ ...current, [key]: value }));
  const currentSymbol = () => buildAnalysisPayload(form()).symbol;
  const responseRoot = createMemo(() => readRecord(snapshot()?.response));
  const suggestion = createMemo(() => readRecord(responseRoot().suggestion));
  const instrument = createMemo(() => readRecord(responseRoot().instrument));
  const metrics = createMemo(() => readRecord(responseRoot().metrics));
  const microstructure = createMemo(() => readRecord(responseRoot().microstructure));
  const analyzedSymbol = createMemo(() => text(responseRoot().symbol, ""));
  const liveQuoteQuery = createQuery(() => ({
    queryKey: queryKeys.quote(analyzedSymbol()),
    queryFn: ({ signal }) => apiClient.quote(analyzedSymbol(), { signal }),
    enabled: analyzedSymbol().length === 6,
  }));
  const currentQuote = createMemo(() => {
    const liveQuote = readRecord(liveQuoteQuery.data);
    const liveQuoteSymbol = text(liveQuote.symbol, analyzedSymbol());
    if (liveQuoteQuery.data && liveQuoteSymbol === analyzedSymbol()) return liveQuote;
    return quoteRecord(snapshot());
  });
  const currentAnomaly = createMemo(() => anomalyRecord(snapshot()));
  const chartValues = createMemo(() => chartPoints(snapshot()));
  const hasValidSymbol = createMemo(() => currentSymbol().length === 6);
  const hasBatchSymbols = createMemo(() => parseSymbols(form().batchSymbols).length > 0);
  const actionHeadline = createMemo(() => text(suggestion().plain_action_text ?? suggestion().effective_action ?? suggestion().action, snapshot() ? "观察" : "等待量化信号"));
  const riskLevel = createMemo(() => text(suggestion().risk_level, snapshot() ? "低风险" : "--"));
  const executionText = createMemo(() => text(suggestion().plain_execution_text ?? suggestion().strategy_notes ?? analysisReason(snapshot()), "--"));
  const invalidText = createMemo(() => text(suggestion().plain_invalid_condition ?? suggestion().why_not_execute, "暂无失效条件"));
  const statusText = createMemo(() => text(suggestion().signal_layer_text ?? suggestion().signal_layer, snapshot() ? "观察" : "--"));
  const supportLevel = createMemo(() => keyLevelRows(snapshot()).find((item) => String(item.direction) === "support") ?? keyLevelRows(snapshot())[0]);
  const resistanceLevel = createMemo(() => keyLevelRows(snapshot()).find((item) => String(item.direction) === "resistance") ?? keyLevelRows(snapshot())[1]);
  const aiSummary = createMemo(() => aiLines(snapshot())[0] ?? "AI 只解释，不放宽底线规则。");
  const canOpenPaperOrder = createMemo(() => Boolean(snapshot() && currentSymbol()));

  onCleanup(() => activeRequest?.abort());

  createEffect(() => {
    const symbol = routeSymbol();
    if (!symbol || symbol === untrack(form).symbol) return;
    activeRequest?.abort();
    activeRequest = null;
    setForm((current) => ({ ...current, symbol }));
    setSnapshot(null);
    setStatus("idle");
    setMessage("");
  });

  return (
    <PageScaffold page="analysis" class="analysis-workflow analysis-clean-layout">
      <section class="tq-analysis-page tq-page__full analysis-clean-page">
        <div class="analysis-clean-alert">
          <span>提示</span>
          <strong>{text(instrument().name, currentSymbol())}监控警示：</strong>
          <em>{snapshot() ? executionText() : "只跟踪，不追价，等价格到位后再做二次确认。"}</em>
        </div>

        <div class="analysis-clean-card analysis-clean-diagnosis">
          <div class="analysis-clean-row">
            <aside class="analysis-clean-input">
              <h3>输入控制</h3>
              <label class="analysis-clean-field">
                <span>证券代码</span>
                <input aria-label="分析代码" value={form().symbol} onInput={(event) => updateForm("symbol", event.currentTarget.value)} />
              </label>
              <label class="analysis-clean-field">
                <span>偏好策略</span>
                <select aria-label="策略偏好" value={form().preferStrategy} onChange={(event) => updateForm("preferStrategy", event.currentTarget.value as AnalysisFormState["preferStrategy"])}>
                  <option value="auto">自动选择最优因子</option>
                  <option value="positive_t">先买后卖</option>
                  <option value="negative_t">先卖后接回</option>
                </select>
              </label>
              <div class="analysis-clean-position-grid">
                <label class="analysis-clean-field">
                  <span>底仓</span>
                  <input aria-label="基础仓位" type="number" min="0" value={form().basePosition} onInput={(event) => updateForm("basePosition", Number(event.currentTarget.value))} />
                </label>
                <label class="analysis-clean-field">
                  <span>可卖</span>
                  <input aria-label="可用仓位" type="number" min="0" value={form().availablePosition} onInput={(event) => updateForm("availablePosition", Number(event.currentTarget.value))} />
                </label>
              </div>
              <label class="analysis-clean-check">
                <input type="checkbox" checked={form().includeAi} onChange={(event) => updateForm("includeAi", event.currentTarget.checked)} />
                AI 辅助解释
              </label>
              <button class="analysis-clean-primary" type="button" disabled={status() === "loading" || !hasValidSymbol()} onClick={() => void startAnalysis()} data-testid="analysis-control-start">
                {status() === "loading" ? "分析中" : "开始量化分析"}
              </button>
              <Show when={message()}>
                <p class={`analysis-message${status() === "error" ? " analysis-message--error" : ""}`}>{message()}</p>
              </Show>
            </aside>

            <div class="analysis-clean-output">
              <div class="analysis-clean-title">
                <h3>量化分析诊断矩阵</h3>
                <span>输入后先看结果，不前置操作</span>
              </div>
              <div class="analysis-stat-grid">
                <StatCell label="证券目标" value={currentSymbol()} sub="当前指定处理标的" />
                <StatCell label="操作建议" value={actionHeadline()} sub="条件不满足时禁止前置操作" tone="warn" />
                <StatCell label="动态风险等级" value={riskLevel()} sub="等待风控核心清洗数据" />
                <StatCell label="批量池排队" value={String(batchRows().length)} sub="当前队列结果数量" />
              </div>
              <div class="analysis-clean-note">
                <span>系统诊断判研原因</span>
                <p>系统优先检索当前证券的价格档位、持仓配比、即时手续费率、综合风险系数以及多因子失效条件。</p>
              </div>
            </div>
          </div>
        </div>

        <div class="analysis-clean-card analysis-clean-action-card tq-analysis-page__key-levels">
          <div class="analysis-clean-title">
            <h3>当前行动建议细则点</h3>
            <button class="analysis-clean-secondary" type="button" disabled={!canOpenPaperOrder()} onClick={() => void openPaperDraft()} data-testid="analysis-open-paper">
              模拟下单
            </button>
          </div>
          <div class="analysis-stat-grid">
            <StatCell label="入场参考位" value={numberText(supportLevel()?.price, "--")} />
            <StatCell label="预期卖出位" value={numberText(resistanceLevel()?.price, "--")} />
            <StatCell label="硬性止损点" value={text(supportLevel()?.invalid_condition, "--")} />
            <StatCell label="止盈保护位" value={statusText()} />
          </div>
          <div class="analysis-box-grid">
            <InfoBox title="错过了最佳建仓点怎么办？" body={invalidText()} />
            <InfoBox title="仓位及对冲平抑建议" body={`${pctText(suggestion().position_pct, "--")} / 预计价差 ${pctText(suggestion().expected_profit_pct, "--")}`} />
            <InfoBox title="AI 补充说明" body={aiSummary()} />
            <InfoBox title="买卖盘情况" body={text(microstructure().notes, "--")} />
          </div>
          <Show when={keyLevelRows(snapshot()).length}>
            <div class="analysis-levels">
              <For each={keyLevelRows(snapshot()).slice(0, 4)}>
                {(level) => (
                  <div class="analysis-level">
                    <strong>{levelDirectionText(level.direction)} {numberText(level.price)}</strong>
                    <span>{text(level.level_type)} / 强度 {numberText(level.strength_score)}</span>
                  </div>
                )}
              </For>
            </div>
          </Show>
        </div>

        <Show when={text(currentAnomaly().anomaly_text, "")}>
          <div class="analysis-clean-card tq-analysis-page__anomaly">
            <div class="analysis-clean-title"><h3>盘中异常提醒</h3></div>
            <div class="analysis-stat-grid analysis-stat-grid--three">
              <StatCell label="异常等级" value={text(currentAnomaly().anomaly_text)} />
              <StatCell label="风险分" value={numberText(currentAnomaly().score)} />
              <StatCell label="类型" value={text(currentAnomaly().pattern)} />
            </div>
          </div>
        </Show>

        <div class="analysis-clean-card analysis-clean-chart">
          <div class="analysis-clean-title"><h3>K线与多因子指标联动监控区</h3></div>
          <div class="analysis-kline-header">
            <span>开: <strong>{numberText(currentQuote().open_price, "--")}</strong></span>
            <span>高: <strong>{numberText(currentQuote().high_price, "--")}</strong></span>
            <span>低: <strong>{numberText(currentQuote().low_price, "--")}</strong></span>
            <span>收: <strong>{numberText(currentQuote().last_price ?? currentQuote().latest_price, "--")}</strong></span>
            <span>振幅: <strong>{pctText(metrics().amplitude_pct, "--")}</strong></span>
          </div>
          <div class="analysis-kline-frame">
            <Show when={chartValues().length > 0} fallback={<span class="analysis-kline-empty">等待量化分析启动后显示实时K线图形与动态指标流</span>}>
              <KlineChart points={chartValues()} height={260} variant="dark" />
            </Show>
          </div>
        </div>

        <div class="analysis-clean-card tq-analysis-page__data-table">
          <div class="analysis-clean-title">
            <h3>批量分析：今日最值得关注</h3>
            <button class="analysis-clean-secondary" type="button" disabled={status() === "batch" || !hasBatchSymbols()} onClick={() => void startBatch()} data-testid="analysis-batch">
              {status() === "batch" ? "分析中..." : "批量排序"}
            </button>
          </div>
          <label class="analysis-clean-field">
            <span>多个证券代码</span>
            <input aria-label="批量代码" value={form().batchSymbols} onInput={(event) => updateForm("batchSymbols", event.currentTarget.value)} />
          </label>
          <DataTable data={batchRows()} columns={batchColumns} emptyText="暂无批量结果" data-testid="analysis-batch-results" />
        </div>
      </section>
    </PageScaffold>
  );

  async function startAnalysis() {
    if (!hasValidSymbol()) {
      setStatus("error");
      setMessage("请输入 6 位证券代码");
      return;
    }
    activeRequest?.abort();
    const controller = new AbortController();
    activeRequest = controller;
    setStatus("loading");
    setMessage("");
    try {
      const result = await runAnalysisWorkflow(form(), { signal: controller.signal });
      if (activeRequest !== controller) return;
      setSnapshot(result);
      setMessage(`${currentSymbol()} 分析完成`);
      setStatus("idle");
    } catch (error) {
      if (activeRequest !== controller || controller.signal.aborted) return;
      setStatus("error");
      setMessage(errorMessage(error));
    } finally {
      if (activeRequest === controller) activeRequest = null;
    }
  }

  async function startBatch() {
    if (!hasBatchSymbols()) {
      setStatus("error");
      setMessage("请输入至少 1 个证券代码");
      return;
    }
    activeRequest?.abort();
    const controller = new AbortController();
    activeRequest = controller;
    setStatus("batch");
    setMessage("");
    try {
      const rows = await runBatchAnalysis(form(), { signal: controller.signal });
      if (activeRequest !== controller) return;
      setBatchRows(rows);
      setMessage(`${parseSymbols(form().batchSymbols).length} 个标的批量分析完成`);
      setStatus("idle");
    } catch (error) {
      if (activeRequest !== controller || controller.signal.aborted) return;
      setStatus("error");
      setMessage(errorMessage(error));
    } finally {
      if (activeRequest === controller) activeRequest = null;
    }
  }

  function openPaperDraft() {
    return navigate({ to: "/next/paper", search: paperOrderDraftSearch(snapshot(), form()) });
  }
}

function StatCell(props: { label: string; value: string; sub?: string; tone?: "warn" }) {
  return (
    <div class="analysis-stat-cell">
      <span>{props.label}</span>
      <strong class={props.tone ? `analysis-stat-cell__value--${props.tone}` : ""}>{props.value}</strong>
      <Show when={props.sub}><small>{props.sub}</small></Show>
    </div>
  );
}

function InfoBox(props: { title: string; body: string }) {
  return (
    <div class="analysis-info-box">
      <span>{props.title}</span>
      <p>{props.body}</p>
    </div>
  );
}

const batchColumns: ColumnDef<BatchAnalysisRow>[] = [
  { header: "代码", accessorKey: "symbol" },
  { header: "名称", accessorKey: "name" },
  { header: "动作", accessorKey: "action" },
  { header: "分数", cell: (ctx) => <span class="tnum">{numberText(ctx.row.original.score)}</span> },
  { header: "仓位", cell: (ctx) => <span class="tnum">{pctText(ctx.row.original.positionPct)}</span> },
  { header: "风险", accessorKey: "risk" },
  { header: "价格", accessorKey: "price" },
  { header: "原因", accessorKey: "reason" },
];

function levelDirectionText(value: unknown): string {
  if (value === "support") return "支撑";
  if (value === "resistance") return "压力";
  return text(value);
}

function symbolFromSearch(search: unknown): string {
  const value = readSearchValue(search, "symbol");
  if (typeof value !== "string" && typeof value !== "number") return "";
  return parseSymbols(String(value))[0] ?? "";
}

function readSearchValue(search: unknown, key: string): unknown {
  return search && typeof search === "object" ? (search as Record<string, unknown>)[key] : undefined;
}
