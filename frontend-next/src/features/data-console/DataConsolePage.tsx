import { createQuery } from "@tanstack/solid-query";
import { For, Show, createEffect, createMemo, createSignal, onCleanup } from "solid-js";
import { getAdminApiToken, setAdminApiToken } from "../../shared/api/auth";
import { requestOperation } from "../../shared/api/client";
import { queryKeys } from "../../shared/api/queryKeys";
import type {
  AdminMetricsResponse,
  AdminTasksResponse,
  DataQualityCoverageResponse,
  DataQualitySlaResponse,
  RuntimeTaskSummaryResponse,
  RuntimeTasksResponse,
} from "../../shared/api/types";
import { Button } from "../../shared/ui/Button";
import { Icon as SharedIcon } from "../../shared/ui/Icon";
import { Modal } from "../../shared/ui/Modal";
import { readArray, readRecord, text } from "../shared/dataAccess";
import { PageScaffold } from "../shared/PageScaffold";
import { useAuth } from "../auth/authModel";
import {
  adminTaskRows,
  coverageRows,
  record,
  repairRows,
  slaRows,
  taskRows,
  workerRows,
  type DataConsoleRecord,
} from "./dataConsoleModel";
import "./data-console-slice.css";

type ModalState = {
  title: string;
  message: string;
  tone: "error" | "success";
};

export function DataConsolePage() {
  const auth = useAuth();
  const [lastCheck, setLastCheck] = createSignal(formatDateTime(new Date()));
  const [isRefreshing, setIsRefreshing] = createSignal(false);
  const [logSearch, setLogSearch] = createSignal("");
  const [adminToken, setAdminToken] = createSignal("");
  const [adminUnlocked, setAdminUnlocked] = createSignal(false);
  const [modal, setModal] = createSignal<ModalState | null>(null);
  let refreshTimer: ReturnType<typeof setTimeout> | undefined;

  const coverageQuery = createQuery(() => ({
    queryKey: queryKeys.dataQualityCoverage,
    queryFn: ({ signal }) => requestOperation<DataQualityCoverageResponse>("dataQualityCoverage", {}, { signal }),
  }));
  const slaQuery = createQuery(() => ({
    queryKey: queryKeys.dataQualitySla,
    queryFn: ({ signal }) => requestOperation<DataQualitySlaResponse>("dataQualitySla", {}, { signal }),
  }));
  const runtimeTasksQuery = createQuery(() => ({
    queryKey: queryKeys.runtimeTasks,
    queryFn: ({ signal }) => requestOperation<RuntimeTasksResponse>("runtimeTasks", { query: { limit: 40 } }, { signal }),
  }));
  const runtimeTaskSummaryQuery = createQuery(() => ({
    queryKey: queryKeys.runtimeTaskSummary,
    queryFn: ({ signal }) => requestOperation<RuntimeTaskSummaryResponse>("runtimeTaskSummary", {}, { signal }),
  }));
  const adminMetricsQuery = createQuery(() => ({
    queryKey: queryKeys.adminMetrics,
    queryFn: ({ signal }) => requestOperation<AdminMetricsResponse>("adminMetrics", {}, { signal }),
  }));
  const adminTasksQuery = createQuery(() => ({
    queryKey: queryKeys.adminTasks,
    queryFn: ({ signal }) => requestOperation<AdminTasksResponse>("adminTasks", {}, { signal }),
  }));

  const coverageRoot = createMemo(() => record(coverageQuery.data));
  const coverageItems = createMemo(() => coverageRows(coverageQuery.data));
  const slaItems = createMemo(() => slaRows(slaQuery.data));
  const runtimeTasks = createMemo(() => taskRows(runtimeTasksQuery.data));
  const adminTasks = createMemo(() => adminTaskRows(adminTasksQuery.data));
  const workers = createMemo(() => buildWorkerCards(workerRows(adminTasksQuery.data)));
  const allTasks = createMemo(() => [...runtimeTasks(), ...adminTasks()]);
  const runtimeSummary = createMemo(() => readRecord(runtimeTaskSummaryQuery.data));
  const systemStats = createMemo(() => buildSystemStats(readRecord(adminMetricsQuery.data), runtimeSummary(), allTasks(), workers()));
  const decision = createMemo(() => buildDecisionState(coverageRoot(), slaItems(), coverageQuery.isError || slaQuery.isError));
  const providerCards = createMemo(() => buildProviderCards(readRecord(adminMetricsQuery.data)));
  const coverageTableRows = createMemo(() => buildCoverageTableRows(coverageRoot(), coverageItems(), slaItems()));
  const errorLogs = createMemo(() => buildErrorLogs([...allTasks(), ...repairRows(slaQuery.data)]));
  const filteredLogs = createMemo(() => {
    const keyword = logSearch().trim().toLowerCase();
    if (!keyword) return errorLogs();
    return errorLogs().filter((item) => `${item.id} ${item.task} ${item.message} ${item.meta} ${item.code}`.toLowerCase().includes(keyword));
  });
  const layerSummary = createMemo(() => buildLayerSummary(decision(), filteredLogs().length, errorLogs().length, providerCards().length, workers().length));

  createEffect(() => {
    if (typeof window === "undefined") return;
    const timer = window.setInterval(() => setLastCheck(formatDateTime(new Date())), 1000);
    onCleanup(() => window.clearInterval(timer));
  });

  onCleanup(() => {
    if (refreshTimer) clearTimeout(refreshTimer);
  });

  const refreshAll = () => {
    setIsRefreshing(true);
    setLastCheck(formatDateTime(new Date()));
    void Promise.allSettled([
      coverageQuery.refetch(),
      slaQuery.refetch(),
      runtimeTasksQuery.refetch(),
      runtimeTaskSummaryQuery.refetch(),
      adminMetricsQuery.refetch(),
      adminTasksQuery.refetch(),
    ]).finally(() => {
      if (refreshTimer) clearTimeout(refreshTimer);
      refreshTimer = setTimeout(() => setIsRefreshing(false), 260);
    });
  };

  const handleAdminAction = (actionName: string) => {
    if (!auth.isAdmin()) {
      setAdminUnlocked(false);
      setModal({
        title: "权限不足",
        message: `您正在请求执行 [${actionName}]。当前账号不是管理员，只允许查看数据状态。`,
        tone: "error",
      });
      return;
    }
    const token = adminToken().trim() || getAdminApiToken();
    if (!token) {
      setAdminUnlocked(false);
      setModal({
        title: "管理授权缺失",
        message: `您正在请求执行 [${actionName}]。当前管理员账号未加载管理授权令牌，仅可查看，不记录维护意图。`,
        tone: "error",
      });
      return;
    }
    if (adminToken().trim()) setAdminApiToken(adminToken().trim());
    setAdminUnlocked(true);
    setModal({
      title: "指令已记录",
      message: `已基于当前管理员账号记录 [${actionName}] 本地维护意图。当前不直接发起生产写入，正式执行待复验后开启。`,
      tone: "success",
    });
  };

  return (
    <PageScaffold page="data" class="data-terminal-page">
      <section class="data-terminal tq-page__full" aria-label="量化数据状态监控终端">
        <header class="data-terminal-header">
          <div class="data-terminal-brand">
            <span class="data-terminal-brand__mark" aria-hidden="true"><Icon name="activity" /></span>
            <div>
              <div class="data-terminal-brand__line">
                <h1>QuantData 实时监控</h1>
                <span>PROD</span>
              </div>
              <p>节点: Node-01 | 延迟低于 {systemStats().latencyLabel}</p>
            </div>
          </div>
          <div class="data-terminal-header__tools">
            <div class="data-terminal-last-check">
              <span>LAST CHECK</span>
              <strong>{lastCheck()}</strong>
            </div>
            <Button variant="subtle" size="sm" class={`data-terminal-refresh${isRefreshing() ? " data-terminal-refresh--spinning" : ""}`} icon={<Icon name="refresh" />} onClick={refreshAll}>
              刷新
            </Button>
          </div>
        </header>

        <main class="data-terminal-body">
          <section class="data-terminal-layer-strip" aria-label="数据可用性摘要">
            <For each={layerSummary()}>
              {(item) => (
                <div class={`data-terminal-layer-strip__item data-terminal-layer-strip__item--${item.tone}`}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <em>{item.detail}</em>
                </div>
              )}
            </For>
          </section>

          <section class="data-terminal-grid data-terminal-grid--top">
            <DecisionCard state={decision()} />
            <SlaCard rows={slaItems()} coverage={coverageRoot()} />
            <BackendCard stats={systemStats()} />
          </section>

          <section class="data-terminal-grid data-terminal-grid--middle">
            <ProviderCard providers={providerCards()} lastCheck={lastCheck()} />
            <CoverageTable rows={coverageTableRows()} />
          </section>

          <WorkerCluster workers={workers()} />

          <TroubleConsole logs={filteredLogs()} total={errorLogs().length} search={logSearch()} onSearch={setLogSearch} />

          <AdminControlPanel
            token={adminToken()}
            unlocked={adminUnlocked()}
            accountStatus={auth.isAdmin() ? "管理员账号" : "普通账号"}
            onTokenChange={setAdminToken}
            onAction={handleAdminAction}
          />
        </main>

        <footer class="data-terminal-footer">
          QuantData-Monitor Pro v2.5.0-Compact · Database Engine: SQLite/MySQL · System State: {decision().footerState}
        </footer>
      </section>

      <Modal
        open={modal() !== null}
        title={modal()?.title ?? ""}
        onClose={() => setModal(null)}
        width={360}
        class={`data-terminal-modal data-terminal-modal--${modal()?.tone ?? "error"}`}
      >
        <div class="data-terminal-modal__body">
          <span class="data-terminal-modal__icon" aria-hidden="true">
            <Icon name={modal()?.tone === "success" ? "check" : "shield"} />
          </span>
          <p>{modal()?.message}</p>
          <div class="data-terminal-modal__footer">
            <Button variant="primary" size="sm" onClick={() => setModal(null)}>确定</Button>
          </div>
        </div>
      </Modal>
    </PageScaffold>
  );
}

function DecisionCard(props: { state: DecisionState }) {
  return (
    <article class={`data-terminal-card data-terminal-card--decision data-terminal-card--${props.state.tone}`}>
      <div>
        <div class="data-terminal-card__meta">
          <span>{props.state.badge}</span>
          <small><Icon name="clock" /> {props.state.timeLabel}</small>
        </div>
        <h2>今日数据能用吗？</h2>
        <div class="data-decision-alert">
          <Icon name="alert" />
          <div>
            <h3>{props.state.title}</h3>
            <p>{props.state.detail}</p>
          </div>
        </div>
      </div>
      <div class="data-terminal-card__foot">
        <span>主链降级：{props.state.fallback}</span>
        <strong><i />{props.state.accessLabel}</strong>
      </div>
    </article>
  );
}

function SlaCard(props: { rows: DataConsoleRecord[]; coverage: DataConsoleRecord }) {
  const checks = () => buildSlaChecks(props.rows, props.coverage);
  return (
    <article class="data-terminal-card">
      <div class="data-terminal-section-head">
        <h3><Icon name="shield" /> 数据一致性巡检 (SLA)</h3>
        <span>{coveragePercent(props.coverage)} 覆盖</span>
      </div>
      <div class="data-sla-list">
        <For each={checks()}>
          {(item) => (
            <div class={item.pass ? "data-sla-list__row data-sla-list__row--pass" : "data-sla-list__row data-sla-list__row--fail"}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          )}
        </For>
      </div>
      <p class="data-terminal-note">备注：日线交易标的按当前覆盖率校验，高频数据源依赖本地缓存和 Worker 心跳。</p>
    </article>
  );
}

function BackendCard(props: { stats: SystemStats }) {
  return (
    <article class="data-terminal-card">
      <div class="data-terminal-section-head">
        <h3><Icon name="cpu" /> 数据处理后台与链路积压</h3>
        <span class={`data-terminal-status data-terminal-status--${props.stats.heartbeatTone}`}><i />{props.stats.heartbeatTone === "ok" ? "系统正常" : "等待遥测"} (心跳 {props.stats.heartbeatLabel})</span>
      </div>
      <div class="data-backend-metrics">
        <div>
          <span>24H 完成任务</span>
          <strong>{props.stats.completed24h} 个</strong>
        </div>
        <div class={props.stats.failed > 0 ? "data-backend-metrics__danger" : ""}>
          <span>累计失败任务</span>
          <strong>{props.stats.failed} 个</strong>
        </div>
      </div>
      <div class="data-backend-queue">
        <div><span>排队中</span><strong>{props.stats.queued}</strong></div>
        <div><span>运行中</span><strong>{props.stats.running}</strong></div>
        <div><span>重试等待</span><strong>{props.stats.retrying}</strong></div>
      </div>
      <div class={props.stats.lowPriorityPaused ? "data-backend-throttle data-backend-throttle--paused" : "data-backend-throttle"}>
        <span>低优先级降载</span>
        <strong>{props.stats.lowPriorityPaused ? "已开启" : "未开启"}</strong>
        <small>暂停积压 {props.stats.pausedQueued} · 可领取 {props.stats.claimableQueued}</small>
      </div>
      <div class="data-terminal-card__foot">
        <span>兜底系统：后台就绪</span>
        <span>状态: <strong>{props.stats.queueLabel}</strong></span>
      </div>
    </article>
  );
}

function ProviderCard(props: { providers: ProviderState[]; lastCheck: string }) {
  return (
    <article class="data-terminal-card data-provider-card">
      <div class="data-terminal-section-head data-terminal-section-head--border">
        <div>
          <h3>数据源通道 (降级链)</h3>
          <p>探测配置：自动进入降级重试</p>
        </div>
        <span class={props.providers.some((item) => item.tone !== "ok") ? "data-provider-card__quality data-provider-card__quality--warn" : "data-provider-card__quality"}>{props.providers.some((item) => item.tone !== "ok") ? "质量下降" : "质量正常"}</span>
      </div>
      <div class="data-provider-grid">
        <For each={props.providers}>
          {(item) => (
            <div class="data-provider-tile">
              <div>
                <strong>{item.name}</strong>
                <i class={`data-provider-tile__dot data-provider-tile__dot--${item.tone}`} />
              </div>
              <span>{item.detail}</span>
              <div>
                <b>{item.status}</b>
                <small>{item.latency}</small>
              </div>
            </div>
          )}
        </For>
      </div>
      <p class="data-provider-card__time">最近更新: {props.lastCheck}</p>
    </article>
  );
}

function CoverageTable(props: { rows: CoverageRow[] }) {
  return (
    <article class="data-terminal-card data-coverage-card">
      <div class="data-terminal-section-head data-terminal-section-head--border">
        <h3>数据完整度检查 (全市场数据集)</h3>
        <span>日线完成对齐</span>
      </div>
      <div class="data-terminal-table-wrap">
        <table class="data-terminal-table">
          <thead>
            <tr>
              <th>评估数据集</th>
              <th>覆盖率</th>
              <th>应有行</th>
              <th>实有行</th>
              <th>待补</th>
              <th>异常行</th>
              <th>重复行</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <For each={props.rows}>
              {(item) => (
                <tr>
                  <td>{item.dataset}</td>
                  <td><strong class={item.status === "正常" ? "data-text-ok" : "data-text-warn"}>{item.coverage}</strong></td>
                  <td>{item.expected}</td>
                  <td>{item.actual}</td>
                  <td>{item.missing}</td>
                  <td>{item.invalid}</td>
                  <td>{item.duplicate}</td>
                  <td><span class={item.status === "正常" ? "data-terminal-pill data-terminal-pill--ok" : "data-terminal-pill data-terminal-pill--warn"}>{item.status}</span></td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
      <div class="data-terminal-info">
        <Icon name="info" />
        <p><strong>无待补任务：</strong> 当前 {props.rows.reduce((sum, item) => sum + item.missing, 0)} 个故障数据集。若高频数据源依赖本地缓存，请检查数据库配置、物化表连接状态及本地引擎代理心跳。</p>
      </div>
    </article>
  );
}

function WorkerCluster(props: { workers: WorkerCard[] }) {
  return (
    <article class="data-terminal-card data-worker-card">
      <div class="data-terminal-section-head">
        <h3><Icon name="server" /> 运行时计算集群状况 (Running Workers)</h3>
        <span>心跳检测间隔: 5s/次</span>
      </div>
      <div class="data-worker-grid">
        <For each={props.workers}>
          {(item) => (
            <div class="data-worker-tile">
              <div>
                <strong>{item.name}</strong>
                <span>{item.id}</span>
              </div>
              <div>
                <b>{item.status}</b>
                <span>心跳: {item.heartbeat}</span>
              </div>
            </div>
          )}
        </For>
        <Show when={!props.workers.length}>
          <div class="data-log-empty">暂无运行时 worker 心跳数据</div>
        </Show>
      </div>
    </article>
  );
}

function TroubleConsole(props: { logs: ErrorLog[]; total: number; search: string; onSearch: (value: string) => void }) {
  return (
    <article class="data-terminal-card data-trouble-card">
      <div class="data-trouble-card__head">
        <div>
          <h3><Icon name="terminal" /> 高危排错控制台 (24H 故障流)</h3>
          <p>数据清洗或物化视图异常。相同并发异常日志已作模式聚合归纳。</p>
        </div>
        <div class="data-log-search">
          <input value={props.search} onInput={(event) => props.onSearch(event.currentTarget.value)} placeholder="快速搜索表名/异常代码..." />
          <span>{props.search ? props.logs.length : props.total} 个{props.search ? "匹配" : "关联"}报错</span>
        </div>
      </div>
      <div class="data-log-list">
        <For each={props.logs}>
          {(item) => (
            <div class="data-log-item">
              <div>
                <span>#{item.id}</span>
                <strong>{item.task}</strong>
                <small>delay: {item.delay}</small>
              </div>
              <p>{item.message}</p>
              <div>
                <span>{item.meta}</span>
                <strong>{item.code}</strong>
              </div>
            </div>
          )}
        </For>
        <Show when={!props.logs.length}>
          <div class="data-log-empty">暂无匹配错误</div>
        </Show>
      </div>
    </article>
  );
}

function AdminControlPanel(props: {
  token: string;
  unlocked: boolean;
  accountStatus: string;
  onTokenChange: (value: string) => void;
  onAction: (actionName: string) => void;
}) {
  return (
    <article class="data-terminal-card data-admin-card">
      <h3>管理操作解锁</h3>
      <p>当前不会真实写入生产，只记录本地维护意图；正式执行需二次复验后开启。</p>
      <div class="data-admin-card__row">
        <label>
          <Icon name="key" />
          <input
            type="password"
            value={props.token}
            onInput={(event) => props.onTokenChange(event.currentTarget.value)}
            placeholder="粘贴管理员授权令牌"
          />
        </label>
        <div>
          <Button variant="primary" size="sm" onClick={() => props.onAction("数据重新拉取")}>数据重新拉取</Button>
          <Button variant="subtle" size="sm" onClick={() => props.onAction("修复缺失物化表")}>修复缺失物化表</Button>
          <Button variant="subtle" size="sm" onClick={() => props.onAction("检测可用池范围")}>检测可用池范围</Button>
        </div>
      </div>
      <div class={props.unlocked ? "data-admin-card__status data-admin-card__status--ok" : "data-admin-card__status"}>
        <i />
        <span>{props.unlocked ? "管理员账号已确认 · 当前仅记录维护意图" : `当前账号权限状态：${props.accountStatus} · 管理操作锁定`}</span>
      </div>
    </article>
  );
}

interface DecisionState {
  tone: "ok" | "danger";
  badge: string;
  timeLabel: string;
  title: string;
  detail: string;
  fallback: string;
  accessLabel: string;
  footerState: string;
}

interface SystemStats {
  completed24h: number;
  failed: number;
  queued: number;
  running: number;
  retrying: number;
  lowPriorityPaused: boolean;
  pausedQueued: number;
  claimableQueued: number;
  latencyLabel: string;
  heartbeatLabel: string;
  heartbeatTone: "ok" | "warn";
  queueLabel: string;
}

interface ProviderState {
  name: string;
  tone: "ok" | "warn" | "danger";
  detail: string;
  status: string;
  latency: string;
}

interface CoverageRow {
  dataset: string;
  coverage: string;
  expected: number | string;
  actual: number | string;
  missing: number;
  invalid: number;
  duplicate: number;
  status: string;
}

interface WorkerCard {
  name: string;
  id: string;
  status: string;
  heartbeat: string;
}

interface ErrorLog {
  id: string;
  task: string;
  delay: string;
  message: string;
  meta: string;
  code: string;
}

interface LayerSummaryItem {
  label: string;
  value: string;
  detail: string;
  tone: "ok" | "warn";
}

function buildLayerSummary(decision: DecisionState, filteredErrors: number, totalErrors: number, providers: number, workers: number): LayerSummaryItem[] {
  const blocked = decision.tone === "danger";
  return [
    {
      label: "结论",
      value: decision.accessLabel,
      detail: decision.title,
      tone: blocked ? "warn" : "ok",
    },
    {
      label: "异常",
      value: `${filteredErrors}/${totalErrors}`,
      detail: totalErrors ? "存在任务或 SLA 异常，先看下方排错" : "未发现关联故障",
      tone: totalErrors ? "warn" : "ok",
    },
    {
      label: "技术明细",
      value: `${providers} 源 / ${workers} Worker`,
      detail: "Provider、SLA、任务明细在下方展开",
      tone: providers && workers ? "ok" : "warn",
    },
  ];
}

function buildDecisionState(coverage: DataConsoleRecord, sla: DataConsoleRecord[], hasError: boolean): DecisionState {
  const blockers = sla.flatMap((item) => readArray(item.blockers));
  const failed = hasError || blockers.length > 0 || sla.some((item) => isBadStatus(item.status)) || Number(coverage.missing_days ?? readArray(coverage.missing_dates).length) > 0;
  return failed
    ? {
        tone: "danger",
        badge: "决策阻断 ALERT",
        timeLabel: latestDataTime(sla, coverage),
        title: "关键数据不可用，先暂停使用",
        detail: "分钟线、逐笔成交或 SLA 数据未达到核心要求。仅作决策提示，不会发起自动委托下单。",
        fallback: "主动降级中",
        accessLabel: "暂停接入",
        footerState: "Downgraded",
      }
    : {
        tone: "ok",
        badge: "决策通过 READY",
        timeLabel: latestDataTime(sla, coverage),
        title: "关键数据可用，允许观察使用",
        detail: "当前覆盖率与 SLA 未发现阻断项。页面仍只展示数据状态，不执行生产写入。",
        fallback: "无需降级",
        accessLabel: "可观察",
        footerState: "Healthy",
      };
}

function buildSlaChecks(rows: DataConsoleRecord[], coverage: DataConsoleRecord) {
  const missing = Number(coverage.missing_days ?? readArray(coverage.missing_dates).length) || 0;
  const invalidRows = rows.reduce((sum, item) => sum + numberValue(item.invalid_rows), 0);
  const blockers = rows.flatMap((item) => readArray(item.blockers)).length;
  const coverageOk = missing === 0;
  return [
    { label: "行情新鲜度", value: rows.some((item) => isBadStatus(item.status)) ? "不通过 (存在过期数据)" : "通过 (关键数据正常)", pass: !rows.some((item) => isBadStatus(item.status)) },
    { label: "覆盖率缺口", value: coverageOk ? "通过 (未发现缺口)" : `不通过 (${missing} 个缺口)`, pass: coverageOk },
    { label: "复权一致性", value: invalidRows ? `不通过 (${invalidRows} 行异常)` : "通过 (无 Invalid/重复)", pass: invalidRows === 0 },
    { label: "关键 SLA 达成", value: blockers ? `不通过 (${blockers} 个阻断)` : "通过 (核心 SLA 正常)", pass: blockers === 0 },
  ];
}

function buildSystemStats(metrics: DataConsoleRecord, runtimeSummary: DataConsoleRecord, tasks: DataConsoleRecord[], workers: WorkerCard[]): SystemStats {
  const failed = numberValue(pickMetric(runtimeSummary, ["failed"])) || numberValue(pickMetric(metrics, ["failed", "failed_count", "runtime_failed_count"])) || tasks.filter((item) => isBadStatus(item.status)).length;
  const queued = numberValue(pickMetric(runtimeSummary, ["queued"])) || numberValue(pickMetric(metrics, ["queued", "queued_count"])) || tasks.filter((item) => text(item.status).includes("等待") || item.status === "queued").length;
  const running = numberValue(pickMetric(runtimeSummary, ["running", "running_count"])) || numberValue(pickMetric(metrics, ["running", "running_count"])) || tasks.filter((item) => item.status === "running").length;
  const retrying = numberValue(pickMetric(runtimeSummary, ["retrying"])) || numberValue(pickMetric(metrics, ["retrying", "retry_count"])) || tasks.filter((item) => text(item.status).includes("重试")).length;
  const completed = numberValue(pickMetric(runtimeSummary, ["succeeded_recent"])) || numberValue(pickMetric(metrics, ["completed_24h", "completed_count", "succeeded_count"])) || tasks.filter((item) => item.status === "succeeded" || item.status === "finished").length;
  const pausedQueued = numberValue(runtimeSummary.paused_queued);
  const claimableQueued = numberValue(runtimeSummary.claimable_queued) || Math.max(queued - pausedQueued, 0);
  const heartbeat = workers.map((item) => Number.parseFloat(item.heartbeat)).filter(Number.isFinite);
  const latency = numberValue(pickMetric(metrics, ["latency_ms", "p95_ms", "oldest_queued_age_seconds"])) || numberValue(runtimeSummary.longest_wait_seconds);
  const hasTelemetry = heartbeat.length > 0 || latency > 0;
  return {
    completed24h: completed,
    failed,
    queued,
    running,
    retrying,
    lowPriorityPaused: runtimeSummary.low_priority_tasks_paused === true,
    pausedQueued,
    claimableQueued,
    latencyLabel: hasTelemetry ? `${latency}ms` : "暂无遥测",
    heartbeatLabel: heartbeat.length ? `${Math.min(...heartbeat)}s前` : "无心跳",
    heartbeatTone: heartbeat.length ? "ok" : "warn",
    queueLabel: queued || running || retrying ? (pausedQueued ? "降载积压" : "有积压") : "无积压",
  };
}

function buildProviderCards(metrics: DataConsoleRecord): ProviderState[] {
  const providers = readArray<DataConsoleRecord>(metrics.providers ?? metrics.provider_status ?? metrics.data_sources);
  const rows = providers.length
    ? providers.slice(0, 4)
    : [
        { name: "Tencent", status: "degraded", latency_ms: 0 },
        { name: "EastMoney", status: "degraded", latency_ms: 0 },
        { name: "AkShare", status: "degraded", latency_ms: 0 },
        { name: "Sina", status: "degraded", latency_ms: 0 },
      ];
  return rows.map((item) => {
    const status = text(item.status ?? item.health ?? "degraded");
    const tone = isBadStatus(item.status) || status.includes("降级") ? "warn" : "ok";
    return {
      name: text(item.name ?? item.provider ?? item.source, "Provider"),
      tone,
      detail: text(item.detail ?? item.message, "未配置主动探测"),
      status: tone === "ok" ? "可用" : "已降级",
      latency: `${numberValue(item.latency_ms ?? item.latency ?? item.p95_ms)}ms`,
    };
  });
}

function buildCoverageTableRows(coverage: DataConsoleRecord, items: DataConsoleRecord[], sla: DataConsoleRecord[]): CoverageRow[] {
  const rows = items.length ? items : coverage.dataset_key ? [coverage] : sla;
  if (!rows.length) {
    return [{
      dataset: "日线交易标的池 / --",
      coverage: "100.00%",
      expected: 0,
      actual: 0,
      missing: 0,
      invalid: 0,
      duplicate: 0,
      status: "正常",
    }];
  }
  return rows.slice(0, 6).map((item) => {
    const missing = numberValue(item.missing_days ?? readArray(item.missing_dates).length);
    const invalid = numberValue(item.invalid_rows);
    const duplicate = numberValue(item.duplicate_rows);
    return {
      dataset: `${text(item.dataset_key ?? item.symbol, "日线交易标的池")} / ${text(item.as_of_date ?? item.trade_date ?? coverage.as_of_date, "--")}`,
      coverage: coveragePercent(item),
      expected: numberValue(item.expected_rows ?? item.expected_days ?? item.total_days) || "--",
      actual: numberValue(item.actual_rows ?? item.present_days ?? item.rows) || "--",
      missing,
      invalid,
      duplicate,
      status: missing || invalid || duplicate || isBadStatus(item.status) ? "需复核" : "正常",
    };
  });
}

function buildWorkerCards(rows: DataConsoleRecord[]): WorkerCard[] {
  return rows.slice(0, 4).map((item) => ({
    name: text(item.component ?? item.name ?? item.worker_type, "worker"),
    id: text(item.worker_id ?? item.id, "--"),
    status: isBadStatus(item.status) ? "WARN" : "ON",
    heartbeat: `${numberValue(item.heartbeat_age_seconds)}s`,
  }));
}

function buildErrorLogs(rows: DataConsoleRecord[]): ErrorLog[] {
  const failed = rows.filter((item) => isBadStatus(item.status) || item.error_message || item.error || item.exception);
  return failed.slice(0, 10).map((item, index) => ({
    id: text(item.id ?? item.task_id, String(index + 1)),
    task: text(item.task_type ?? item.type ?? item.repair_id, "runtime_task"),
    delay: relativeDelay(item.updated_at ?? item.created_at),
    message: text(item.error_message ?? item.error ?? item.exception ?? item.reason, "数据任务返回异常，需要人工复核"),
    meta: `任务来源: ${text(item.scope ?? item.source, "runtime")} | 标的: ${text(item.symbol, "--")} (${text(item.name ?? item.stock_name, "--")}) | engine: ${text(item.engine, "--")}`,
    code: text(item.error_code ?? item.code, "--"),
  }));
}

function Icon(props: { name: string }) {
  return <SharedIcon name={props.name} />;
}

function pickMetric(recordValue: DataConsoleRecord, keys: string[]): unknown {
  for (const key of keys) {
    if (recordValue[key] !== undefined && recordValue[key] !== null && recordValue[key] !== "") return recordValue[key];
  }
  return undefined;
}

function coveragePercent(recordValue: DataConsoleRecord): string {
  const parsed = Number(recordValue.coverage_pct ?? recordValue.coverage ?? recordValue.coverage_rate ?? 1);
  if (!Number.isFinite(parsed)) return "--";
  const normalized = Math.abs(parsed) > 1 ? parsed : parsed * 100;
  return `${normalized.toFixed(2)}%`;
}

function isBadStatus(status: unknown): boolean {
  const value = String(status ?? "").toLowerCase();
  return ["failed", "error", "stale", "blocked", "degraded", "down", "warn"].some((item) => value.includes(item));
}

function numberValue(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function latestDataTime(sla: DataConsoleRecord[], coverage: DataConsoleRecord): string {
  const raw = text(coverage.as_of_date ?? coverage.generated_at ?? sla[0]?.as_of_date ?? sla[0]?.updated_at, "");
  return raw ? raw.slice(5, 16).replace("T", " ") : "--";
}

function relativeDelay(value: unknown): string {
  const raw = text(value, "");
  const date = raw ? new Date(raw) : null;
  if (!date || Number.isNaN(date.getTime())) return "1s ago";
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.round(minutes / 60)}h ago`;
}

function formatDateTime(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
