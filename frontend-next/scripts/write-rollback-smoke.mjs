import crypto from "node:crypto";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { buildAuthHeaders, ensureAccessToken, hashPayload } from "./script-utils.mjs";

const apiBase = process.env.API_BASE || "http://127.0.0.1:8000";
const args = new Set(process.argv.slice(2));
const runAllIsolated = args.has("--all") && args.has("--isolated");
const localApiBase = /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/?$/.test(apiBase);
const remoteIsolatedAllowed = process.env.FRONTEND_NEXT_ALLOW_REMOTE_ISOLATED_WRITE_SMOKE === "1";
const isolatedCliAllowed = runAllIsolated && (localApiBase || remoteIsolatedAllowed);
const isolatedCliBlocked = runAllIsolated && !isolatedCliAllowed;
const remoteRoleSmokeAllowed = isolatedCliAllowed && !localApiBase && remoteIsolatedAllowed && Boolean(process.env.ADMIN_API_TOKEN || process.env.FRONTEND_ADMIN_TOKEN);
const runLivePaper = process.env.FRONTEND_NEXT_LIVE_WRITE_SMOKE === "1" || isolatedCliAllowed;
const runLiveBacktest = process.env.FRONTEND_NEXT_LIVE_BACKTEST_SMOKE === "1" || isolatedCliAllowed;
const runLiveAdmin = process.env.FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE === "1" || isolatedCliAllowed;
const runLiveCore = process.env.FRONTEND_NEXT_LIVE_CORE_WRITE_SMOKE === "1" || isolatedCliAllowed;
const allowLocalAdminPromote = process.env.FRONTEND_NEXT_LOCAL_ADMIN_PROMOTE === "1";
const reportPath = resolve("../docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json");
const smokeFeatureFlagCandidates = [
  "frontend_solid_island_enabled",
  "frontend_wasm_compute_enabled",
  "frontend_worker_compute_enabled",
  "frontend_realtime_signals_island_enabled",
  "frontend_canvas_chart_island_enabled",
  "playbook_lazy_load_enabled",
  "smart_mode_enabled",
];

const payloads = {
  paperOrder: {
    symbol: "000001",
    name: "平安银行",
    side: "buy",
    order_type: "limit",
    quantity: 100,
    price: 10,
    current_price: 10,
    up_limit: null,
    down_limit: null,
    is_suspended: false,
    reason: "frontend-next local rollback smoke",
    require_intraday_confirmation: false,
    source: "fn-next-rollback",
    strategy_key: "",
  },
  backtestRun: {
    name: "frontend-next rollback smoke dry run",
    strategies: ["n_pattern_long_wash"],
    start_date: "2025-01-01",
    end_date: "2026-06-05",
    initial_capital: 100000,
    benchmark: "000300",
    data_version: "",
    engine_version: "backtest-v2",
    fee_model_version: "",
    max_duration_seconds: 1800,
    resource_tier: "light",
    slippage_bps: 8,
    strategy_version: "",
    params: { source: "fn-next-rollback" },
  },
  backtestValidation: {
    name: "frontend-next rollback smoke validation",
    strategy_key: "n_pattern_long_wash",
    start_date: "2025-01-01",
    end_date: "2026-06-05",
    window_count: 1,
    train_ratio: 0.75,
    max_combinations: 1,
    param_grid: { min_score: [80] },
    auto_promote_state_params: false,
  },
  backtestOptimization: {
    name: "frontend-next rollback smoke optimization",
    strategy_key: "n_pattern_long_wash",
    train_start: "2025-01-01",
    train_end: "2025-12-31",
    test_start: "2026-01-01",
    test_end: "2026-06-05",
    optimization_target: "sharpe",
    max_combinations: 1,
    param_grid: { min_score: [80] },
    auto_promote_state_params: false,
  },
  featureFlag: {
    key: smokeFeatureFlagCandidates[0],
    enabled: false,
  },
  tradeJournal: {
    symbol: "000001",
    action: "note",
    reason_text: "frontend-next rollback smoke",
    signal_source: "frontend-next-write-rollback-smoke",
    discipline_flags: {},
    mistake_tags: ["frontend-next-smoke"],
  },
};

const startedAt = new Date().toISOString();
const report = {
  generated_at: startedAt,
  apiBase,
  live_modes: {
    paper_order: runLivePaper,
    backtest_run: runLiveBacktest,
    admin_feature_flag: runLiveAdmin,
    core_writes: runLiveCore,
    local_admin_promote: allowLocalAdminPromote,
    remote_role_smoke: remoteRoleSmokeAllowed,
    cli_all_isolated: runAllIsolated,
    cli_all_isolated_blocked: isolatedCliBlocked,
    local_api_base: localApiBase,
  },
  default_write_guard: {
    ok: process.env.VITE_FRONTEND_NEXT_WRITE_ENABLED !== "true",
    value: process.env.VITE_FRONTEND_NEXT_WRITE_ENABLED ?? "unset",
    note: "frontend-next live writes remain disabled unless VITE_FRONTEND_NEXT_WRITE_ENABLED=true is supplied explicitly.",
  },
  dry_run_payload_hashes: {
    paper_order: await hashPayload(payloads.paperOrder),
    backtest_run: await hashPayload(payloads.backtestRun),
    feature_flag: await hashPayload(payloads.featureFlag),
    trade_journal: await hashPayload(payloads.tradeJournal),
    backtest_validation: await hashPayload(payloads.backtestValidation),
    backtest_optimization: await hashPayload(payloads.backtestOptimization),
  },
  endpoints: {
    paper_order: {
      method: "POST",
      path: "/api/paper/orders",
      rollback:
        "POST /api/paper/account/reset for the temporary user when an admin token is available; otherwise use a non-persisting business-rule probe.",
    },
    backtest_run: {
      method: "POST",
      path: "/api/backtests",
      rollback: "DELETE /api/backtests/{run_id}; kept dry-run by default because it can enqueue compute work.",
    },
    feature_flag: {
      method: "PUT",
      path: "/api/settings/feature-flags/{runtime_selected_key}",
      rollback: "restore previous value; kept dry-run unless FRONTEND_NEXT_LIVE_ADMIN_WRITE_SMOKE=1 and admin token are provided.",
      candidate_keys: smokeFeatureFlagCandidates,
    },
  },
  live_results: [],
  remaining_guards: [],
};

if (isolatedCliBlocked) {
  report.remaining_guards.push(
    "--all --isolated was requested against a non-local API_BASE; set FRONTEND_NEXT_ALLOW_REMOTE_ISOLATED_WRITE_SMOKE=1 only for an approved isolated validation environment.",
  );
}

let smokeAuth;
if (runLiveCore || runLivePaper || runLiveAdmin || runLiveBacktest) {
  smokeAuth = await resolveSmokeAuth();
}
try {
  if (runLiveCore) {
    report.live_results.push(await captureLive("auth_mfa", () => runAuthMfaRollback(smokeAuth)));
    report.live_results.push(await captureLive("watchlist", () => runWatchlistRollback(smokeAuth)));
    report.live_results.push(await captureLive("trade_journal", () => runTradeJournalRollback(smokeAuth)));
    report.live_results.push(await captureLive("paper_account", () => runPaperAccountRollback(smokeAuth)));
    report.live_results.push(await captureLive("database_check", () => runDatabaseCheck(smokeAuth)));
  } else {
    report.remaining_guards.push("Core write rollback smoke not run; set FRONTEND_NEXT_LIVE_CORE_WRITE_SMOKE=1 or pass --all --isolated.");
  }

  if (runLivePaper) {
    report.live_results.push(await captureLive("paper_order", () => runPaperOrderRollback(smokeAuth)));
  } else {
    report.remaining_guards.push("Paper order live rollback not run; set FRONTEND_NEXT_LIVE_WRITE_SMOKE=1 for isolated local smoke.");
  }

  if (runLiveAdmin) {
    report.live_results.push(await captureLive("settings_section", () => runSettingsRollback(smokeAuth)));
    report.live_results.push(await captureLive("feature_flag", () => runFeatureFlagRollback(smokeAuth)));
    report.live_results.push(await captureLive("playbook_lifecycle", () => runPlaybookLifecycleRollback(smokeAuth)));
    report.live_results.push(await captureLive("strategy_review", () => runStrategyReviewRollback(smokeAuth)));
    report.live_results.push(await captureLive("data_task", () => runDataTaskRollback(smokeAuth)));
    report.live_results.push(await captureLive("data_repair", () => runDataRepairRollback(smokeAuth)));
  } else {
    report.remaining_guards.push("Settings and feature-flag live rollback not run; requires admin token and isolated environment.");
  }

  if (runLiveBacktest) {
    report.live_results.push(await captureLive("backtest_run", () => runBacktestRollback(smokeAuth)));
    report.live_results.push(await captureLive("backtest_validation", () => runBacktestValidationRollback(smokeAuth)));
    report.live_results.push(await captureLive("backtest_optimization", () => runBacktestOptimizationRollback(smokeAuth)));
  } else {
    report.remaining_guards.push("Backtest create/delete live rollback not run; set FRONTEND_NEXT_LIVE_BACKTEST_SMOKE=1 for isolated local smoke.");
  }
  for (const item of report.live_results) {
    if (item.coverage === "not-run-admin-token-missing") {
      report.remaining_guards.push(`${item.kind} rollback smoke not run because admin token is missing.`);
    }
  }
} finally {
  await smokeAuth?.cleanup();
}
report.ok = report.default_write_guard.ok && report.live_results.every((item) => item.ok);

mkdirSync(resolve("../docs/reports"), { recursive: true });
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify({ ok: report.ok, reportPath, live_results: report.live_results, remaining_guards: report.remaining_guards }, null, 2));
if (!report.ok) process.exit(1);

async function runAuthMfaRollback(auth) {
  const headers = smokeHeaders(auth);
  const setupEvidence = safeWriteEvidence("authTotpSetup", "FNX-SW-AUTH-MFA", "live");
  const setup = await fetchJson("/api/auth/mfa/totp/setup", {
    method: "POST",
    headers: { ...headers, ...setupEvidence.headers },
    body: JSON.stringify({ intent: "frontend-next-smoke" }),
  });
  const secret = setup?.secret;
  if (!secret) return { kind: "auth_mfa", ok: false, stage: "setup", response_shape: shape(setup) };
  const enableEvidence = safeWriteEvidence("authTotpEnable", "FNX-SW-AUTH-MFA", "live");
  const enabled = await fetchJson("/api/auth/mfa/totp/enable", {
    method: "POST",
    headers: { ...headers, ...enableEvidence.headers },
    body: JSON.stringify({ code: generateTotpCode(secret) }),
  });
  const disableEvidence = safeWriteEvidence("authTotpDisable", "FNX-SW-AUTH-MFA", "live");
  const disabled = await fetchJson("/api/auth/mfa/totp/disable", {
    method: "POST",
    headers: { ...headers, ...disableEvidence.headers },
    body: JSON.stringify({ code: generateTotpCode(secret) }),
  });
  return {
    kind: "auth_mfa",
    ok: Boolean(enabled?.user?.mfa_totp_enabled) && disabled?.user?.mfa_totp_enabled === false,
    coverage: "local-isolated-setup-enable-disable",
    request_evidence: {
      setup: setupEvidence.report,
      enable: enableEvidence.report,
      disable: disableEvidence.report,
    },
    setup_shape: shape(setup),
    enable_shape: shape(enabled),
    rollback_shape: shape(disabled),
  };
}

async function runWatchlistRollback(auth) {
  const headers = smokeHeaders(auth);
  const symbol = "000001";
  const before = await fetchJson("/api/watchlist", { headers });
  const existed = watchlistHasSymbol(before, symbol);
  const upsertEvidence = safeWriteEvidence("watchlistUpsert", "FNX-SW-WATCHLIST", "live");
  const created = await fetchJson("/api/watchlist", {
    method: "POST",
    headers: { ...headers, ...upsertEvidence.headers },
    body: JSON.stringify({
      symbol,
      name: "平安银行",
      memo: "frontend-next rollback smoke",
      base_position: 100,
      available_position: 100,
    }),
  });
  const afterCreate = await fetchJson("/api/watchlist", { headers });
  const removeEvidence = safeWriteEvidence("watchlistRemove", "FNX-SW-WATCHLIST", "live");
  await fetchJson(`/api/watchlist/${encodeURIComponent(symbol)}`, {
    method: "DELETE",
    headers: { ...headers, ...removeEvidence.headers },
  });
  const afterDelete = await fetchJson("/api/watchlist", { headers });
  return {
    kind: "watchlist",
    ok: watchlistHasSymbol(afterCreate, symbol) && !watchlistHasSymbol(afterDelete, symbol),
    coverage: "local-isolated-create-read-delete-read",
    existed_before: existed,
    request_evidence: {
      upsert: upsertEvidence.report,
      remove: removeEvidence.report,
    },
    create_shape: shape(created),
  };
}

async function runPaperOrderRollback(auth) {
    const headers = smokeHeaders(auth);
    await fetchJson("/api/bff/v1/workspace/paper", { headers });
    if (!adminCapable(headers, auth)) {
      const probePayload = {
        ...payloads.paperOrder,
        price: 1,
        reason: "frontend-next no-persist probe",
      };
      const evidence = safeWriteEvidence("paperOrderCreate", "FNX-SW-PAPER-ORDER", "live");
      const probe = await requestJson("/api/paper/orders", {
        method: "POST",
        headers: { ...headers, ...evidence.headers },
        body: JSON.stringify(probePayload),
      });
      const detail = typeof probe.payload?.detail === "string" ? probe.payload.detail : "";
      return {
        kind: "paper_order",
        ok: probe.status === 400 && detail.includes("限价条件未满足"),
        mode: "non_persisting_business_rule_probe",
        request_evidence: evidence.report,
        status: probe.status,
        payload: probe.payload,
        full_rollback: "not-run-admin-token-missing",
      };
    }
    const evidence = safeWriteEvidence("paperOrderCreate", "FNX-SW-PAPER-ORDER", "live");
    const created = await fetchJson("/api/paper/orders", {
      method: "POST",
      headers: { ...headers, ...evidence.headers },
      body: JSON.stringify(payloads.paperOrder),
    });
    const orderId = Number(created?.order?.id ?? created?.id ?? created?.order_id ?? created?.data?.id);
    if (!Number.isFinite(orderId) || orderId <= 0) {
      return { kind: "paper_order", ok: false, stage: "create", error: "Paper order create did not return an order id.", response_shape: shape(created) };
    }
    const reset = await fetchJson("/api/paper/account/reset", {
      method: "POST",
      headers,
    });
    return {
      kind: "paper_order",
      ok: true,
      mode: "create_then_reset_temp_account",
      coverage: "local-isolated-create-reset-readback",
      request_evidence: evidence.report,
      order_id: orderId,
      create_shape: shape(created),
      rollback_shape: shape(reset),
    };
}

async function runPaperAccountRollback(auth) {
  const headers = smokeHeaders(auth);
  const before = await fetchJson("/api/paper/account", { headers });
  const pauseEvidence = safeWriteEvidence("paperAccountPause", "FNX-SW-PAPER-ACCOUNT", "live");
  const paused = await fetchJson("/api/paper/account/pause", {
    method: "POST",
    headers: { ...headers, ...pauseEvidence.headers },
    body: JSON.stringify({ reason: "frontend-next rollback smoke" }),
  });
  const resumeEvidence = safeWriteEvidence("paperAccountResume", "FNX-SW-PAPER-ACCOUNT", "live");
  const resumed = await fetchJson("/api/paper/account/resume", {
    method: "POST",
    headers: { ...headers, ...resumeEvidence.headers },
    body: JSON.stringify({ reason: "frontend-next rollback smoke" }),
  });
  const refreshEvidence = safeWriteEvidence("paperPositionsRefresh", "FNX-SW-PAPER-ACCOUNT", "live");
  const refreshed = await fetchJson("/api/paper/positions/refresh", {
    method: "POST",
    headers: { ...headers, ...refreshEvidence.headers },
    body: JSON.stringify({ reason: "frontend-next rollback smoke" }),
  });
  let reconcile = null;
  let reconcileEvidence = null;
  if (adminCapable(headers, auth)) {
    reconcileEvidence = safeWriteEvidence("paperAccountReconcile", "FNX-SW-PAPER-ACCOUNT", "live");
    reconcile = await fetchJson("/api/paper/account/reconcile", {
      method: "POST",
      headers: { ...headers, ...reconcileEvidence.headers },
      body: JSON.stringify({ account_id: before?.id, apply: false }),
    });
  }
  return {
    kind: "paper_account",
    ok: Boolean(paused?.id) && Boolean(resumed?.id) && Array.isArray(refreshed?.positions) && (!adminCapable(headers, auth) || reconcile?.applied === false),
    coverage: adminCapable(headers, auth) ? "local-isolated-pause-resume-refresh-reconcile-dry-run" : "local-isolated-pause-resume-refresh",
    request_evidence: {
      pause: pauseEvidence.report,
      resume: resumeEvidence.report,
      refresh: refreshEvidence.report,
      reconcile: reconcileEvidence?.report ?? null,
    },
    before_shape: shape(before),
    paused_shape: shape(paused),
    resumed_shape: shape(resumed),
    refresh_shape: shape(refreshed),
    reconcile_shape: shape(reconcile),
  };
}

async function runFeatureFlagRollback(auth) {
    const headers = smokeHeaders(auth);
    if (!userRoleCapable(auth, "admin")) {
      return {
        kind: "feature_flag",
        ok: true,
        coverage: "not-run-admin-user-missing",
        stage: "auth",
        message: "Feature-flag rollback smoke requires a bearer user with the admin role.",
      };
    }
    const before = await fetchJson("/api/settings/feature-flags", { headers });
    const selected = selectSmokeFeatureFlag(before);
    const original = selected.enabled;
    const target = !original;
    const changeEvidence = safeWriteEvidence("featureFlagUpdate", "FNX-SW-FEATURE-FLAG", "live");
    const changed = await fetchJson(`/api/settings/feature-flags/${encodeURIComponent(selected.key)}`, {
      method: "PUT",
      headers: { ...headers, ...changeEvidence.headers },
      body: JSON.stringify({ key: selected.key, enabled: target }),
    });
    const restoreEvidence = safeWriteEvidence("featureFlagUpdate", "FNX-SW-FEATURE-FLAG", "live");
    const restored = await fetchJson(`/api/settings/feature-flags/${encodeURIComponent(selected.key)}`, {
      method: "PUT",
      headers: { ...headers, ...restoreEvidence.headers },
      body: JSON.stringify({ key: selected.key, enabled: Boolean(original) }),
    });
    const afterRestore = await fetchJson("/api/settings/feature-flags", { headers });
    const restoredValue = findFeatureFlagValue(afterRestore, selected.key);
    return {
      kind: "feature_flag",
      ok: restoredValue === original,
      coverage: "local-isolated-toggle-restore-readback",
      key: selected.key,
      request_evidence: {
        change: changeEvidence.report,
        restore: restoreEvidence.report,
      },
      original,
      changed_to: target,
      restored_to: restoredValue,
      changed_shape: shape(changed),
      rollback_shape: shape(restored),
    };
}

async function runSettingsRollback(auth) {
  const headers = smokeHeaders(auth);
  if (!adminCapable(headers, auth)) {
    return {
      kind: "settings_section",
      ok: true,
      coverage: "not-run-admin-token-missing",
      stage: "auth",
      message: "Settings rollback smoke requires FRONTEND_ADMIN_TOKEN or ADMIN_API_TOKEN.",
    };
  }
  const beforeSettings = await fetchJson("/api/settings", { headers });
  const currentLoss = beforeSettings?.risk_max_single_loss_pct ?? beforeSettings?.settings?.risk_max_single_loss_pct ?? 1;
  const settingsEvidence = safeWriteEvidence("settingsUpdate", "FNX-SW-SETTINGS-SECTION", "live");
  const changedSettings = await fetchJson("/api/settings", {
    method: "PUT",
    headers: { ...headers, ...settingsEvidence.headers },
    body: JSON.stringify({ risk_max_single_loss_pct: Number(currentLoss) }),
  });
  const restoredSettings = await fetchJson("/api/settings", {
    method: "PUT",
    headers: { ...headers, ...safeWriteEvidence("settingsUpdate", "FNX-SW-SETTINGS-SECTION", "live").headers },
    body: JSON.stringify({ risk_max_single_loss_pct: currentLoss }),
  });
  const beforeSectors = await fetchJson("/api/settings/sector-exclusions", { headers });
  const sectorEvidence = safeWriteEvidence("sectorExclusionsUpdate", "FNX-SW-SETTINGS-SECTION", "live");
  const sectors = await fetchJson("/api/settings/sector-exclusions", {
    method: "PUT",
    headers: { ...headers, ...sectorEvidence.headers },
    body: JSON.stringify({ excluded_sectors: beforeSectors?.excluded_sectors ?? [] }),
  });
  const beforeFactors = await fetchJson("/api/settings/factor-weights", { headers });
  const factorEvidence = safeWriteEvidence("factorWeightsUpdate", "FNX-SW-SETTINGS-SECTION", "live");
  const factors = await fetchJson("/api/settings/factor-weights", {
    method: "PUT",
    headers: { ...headers, ...factorEvidence.headers },
    body: JSON.stringify({ weights: beforeFactors?.weights ?? {} }),
  });
  return {
    kind: "settings_section",
    ok: Boolean(changedSettings) && Boolean(restoredSettings) && Array.isArray(sectors?.excluded_sectors) && Boolean(factors?.weights),
    coverage: "local-isolated-save-restore-readback",
    request_evidence: {
      settings: settingsEvidence.report,
      sectors: sectorEvidence.report,
      factors: factorEvidence.report,
    },
    settings_shape: shape(restoredSettings),
    sectors_shape: shape(sectors),
    factors_shape: shape(factors),
  };
}

async function runPlaybookLifecycleRollback(auth) {
  const headers = smokeHeaders(auth);
  if (!adminCapable(headers, auth)) {
    return {
      kind: "playbook_lifecycle",
      ok: true,
      coverage: "not-run-admin-token-missing",
      stage: "auth",
      message: "Playbook lifecycle rollback smoke requires FRONTEND_ADMIN_TOKEN or ADMIN_API_TOKEN.",
    };
  }
  return withFeatureFlags(headers, { trading_experience_suite_enabled: true, trade_review_suite_enabled: true }, async () => runPlaybookLifecycleRollbackEnabled(auth));
}

async function runPlaybookLifecycleRollbackEnabled(auth) {
  const headers = smokeHeaders(auth);
  const fixture = await resolveLifecycleFixture(headers);
  if (!fixture) {
    return {
      kind: "playbook_lifecycle",
      ok: false,
      stage: "fixture",
      error: "No low-buy lifecycle record is available for isolated rollback smoke.",
      coverage: "blocked-no-lifecycle-fixture",
    };
  }
  let fixtureCleanup = null;
  try {
    const { symbol, strategyKey, tradeDate } = fixture;
    const beforeLifecycle = await fetchJson(`/api/screeners/low-buy/lifecycle?strategy=${encodeURIComponent(strategyKey)}&limit=300`, { headers });
    const originalLifecycle = findLifecycle(beforeLifecycle, symbol, tradeDate, strategyKey) ?? { status: "planned" };
    const targetStatus = originalLifecycle.status === "invalid" ? "planned" : "invalid";
    const lifecycleEvidence = safeWriteEvidence("lowBuyLifecycleUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE", "live");
    const lifecycleChanged = await fetchJson(`/api/screeners/low-buy/lifecycle/${encodeURIComponent(symbol)}`, {
      method: "PATCH",
      headers: { ...headers, ...lifecycleEvidence.headers },
      body: JSON.stringify({
        signal_trade_date: tradeDate,
        strategy_key: strategyKey,
        status: targetStatus,
        attribution_note: "frontend-next rollback smoke",
      }),
    });
    const lifecycleRestoreEvidence = safeWriteEvidence("lowBuyLifecycleUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE", "live");
    const lifecycleRestored = await fetchJson(`/api/screeners/low-buy/lifecycle/${encodeURIComponent(symbol)}`, {
      method: "PATCH",
      headers: { ...headers, ...lifecycleRestoreEvidence.headers },
      body: JSON.stringify({
        signal_trade_date: tradeDate,
        strategy_key: strategyKey,
        status: originalLifecycle.status || "planned",
        attribution_note: originalLifecycle.attribution_note || "",
      }),
    });

    const beforeStrategies = await fetchJson("/api/screeners/low-buy/strategies", { headers });
    const originalStrategy = findStrategyGovernance(beforeStrategies, strategyKey) ?? { status: "active" };
    const strategyEvidence = safeWriteEvidence("lowBuyStrategyUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE", "live");
    const strategyChanged = await fetchJson(`/api/screeners/low-buy/strategies/${encodeURIComponent(strategyKey)}`, {
      method: "PATCH",
      headers: { ...headers, ...strategyEvidence.headers },
      body: JSON.stringify({ status: originalStrategy.status === "paused" ? "watch" : "paused", reason: "frontend-next rollback smoke" }),
    });
    const strategyRestoreEvidence = safeWriteEvidence("lowBuyStrategyUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE", "live");
    const strategyRestored = await fetchJson(`/api/screeners/low-buy/strategies/${encodeURIComponent(strategyKey)}`, {
      method: "PATCH",
      headers: { ...headers, ...strategyRestoreEvidence.headers },
      body: JSON.stringify({ status: originalStrategy.status || "active", reason: "frontend-next rollback restore" }),
    });
    const afterLifecycle = await fetchJson(`/api/screeners/low-buy/lifecycle?strategy=${encodeURIComponent(strategyKey)}&limit=300`, { headers });
    const afterStrategies = await fetchJson("/api/screeners/low-buy/strategies", { headers });
    const permissionProbe = await requestJson(`/api/screeners/low-buy/strategies/${encodeURIComponent(strategyKey)}`, {
      method: "PATCH",
      headers: { ...safeWriteEvidence("lowBuyStrategyUpdate", "FNX-SW-PLAYBOOK-LIFECYCLE", "live").headers },
      body: JSON.stringify({ status: "watch", reason: "frontend-next permission probe" }),
    });
    if (fixture.smokeFixture) fixtureCleanup = await cleanupLifecycleFixture(headers, fixture);
    return {
      kind: "playbook_lifecycle",
      ok:
        findLifecycle(afterLifecycle, symbol, tradeDate, strategyKey)?.status === (originalLifecycle.status || "planned") &&
        findStrategyGovernance(afterStrategies, strategyKey)?.status === (originalStrategy.status || "active") &&
        [401, 403].includes(permissionProbe.status) &&
        (!fixture.smokeFixture || Number(fixtureCleanup?.deleted_count ?? 0) >= 1),
      coverage: fixture.smokeFixture ? "local-isolated-fixture-update-read-restore-delete-403-audit" : "local-isolated-update-read-restore-read-403-audit",
      request_evidence: {
        lifecycle: lifecycleEvidence.report,
        lifecycle_restore: lifecycleRestoreEvidence.report,
        strategy: strategyEvidence.report,
        strategy_restore: strategyRestoreEvidence.report,
      },
      permission_probe_status: permissionProbe.status,
      fixture,
      fixture_cleanup_shape: shape(fixtureCleanup),
      lifecycle_changed_shape: shape(lifecycleChanged),
      lifecycle_restored_shape: shape(lifecycleRestored),
      strategy_changed_shape: shape(strategyChanged),
      strategy_restored_shape: shape(strategyRestored),
    };
  } finally {
    if (fixture.smokeFixture && fixtureCleanup === null) {
      await cleanupLifecycleFixture(headers, fixture).catch(() => undefined);
    }
  }
}

async function runStrategyReviewRollback(auth) {
  const headers = smokeHeaders(auth);
  const payload = {
    strategy_key: "n_pattern_long_wash",
    symbol: "000001",
    review_state: "watch",
    notes: "frontend-next rollback smoke",
    verdict: "local-smoke",
    idempotency_key: `fnx-strategy-review-${Date.now()}`,
  };
  const recordEvidence = safeWriteEvidence("strategyReviewRecord", "FNX-SW-STRATEGY-REVIEW", "live");
  const created = await fetchJson("/api/strategy-tracking/review-records", {
    method: "POST",
    headers: { ...headers, ...recordEvidence.headers },
    body: JSON.stringify(payload),
  });
  const reviewId = Number(created?.review_id);
  if (!Number.isFinite(reviewId) || reviewId <= 0) {
    return { kind: "strategy_review", ok: false, stage: "create", response_shape: shape(created) };
  }
  const listed = await fetchJson(`/api/strategy-tracking/review-records?symbol=${encodeURIComponent(payload.symbol)}&limit=20`, { headers });
  let refresh = null;
  let refreshEvidence = null;
  if (adminCapable(headers, auth)) {
    refreshEvidence = safeWriteEvidence("strategyTrackingRefresh", "FNX-SW-STRATEGY-REVIEW", "live");
    refresh = await fetchJson("/api/strategy-tracking/refresh?range=1", {
      method: "POST",
      headers: { ...headers, ...refreshEvidence.headers },
    });
  }
  await fetchJson(`/api/strategy-tracking/review-records/${reviewId}`, {
    method: "DELETE",
    headers,
  });
  const afterDelete = await fetchJson(`/api/strategy-tracking/review-records?symbol=${encodeURIComponent(payload.symbol)}&limit=20`, { headers });
  return {
    kind: "strategy_review",
    ok: listHasReview(listed, reviewId) && !listHasReview(afterDelete, reviewId) && (!adminCapable(headers, auth) || Boolean(refresh?.audit_id)),
    coverage: adminCapable(headers, auth) ? "local-isolated-create-read-delete-read-refresh-audit" : "local-isolated-create-read-delete-read",
    request_evidence: {
      review_record: recordEvidence.report,
      refresh: refreshEvidence?.report ?? null,
    },
    review_id: reviewId,
    create_shape: shape(created),
    refresh_shape: shape(refresh),
  };
}

async function runDataTaskRollback(auth) {
  const headers = smokeHeaders(auth);
  if (!adminCapable(headers, auth)) {
    return {
      kind: "data_task",
      ok: true,
      coverage: "not-run-admin-token-missing",
      stage: "auth",
      message: "Data task rollback smoke requires FRONTEND_ADMIN_TOKEN or ADMIN_API_TOKEN.",
    };
  }
  const tasks = [];
  const dataJobEvidence = safeWriteEvidence("dataJobSubmit", "FNX-SW-DATA-TASK", "live");
  tasks.push(await createAndCancelRuntimeTask(headers, dataJobEvidence, {
    task_type: "frontend_next_smoke_noop",
    payload: { source: "frontend-next", smoke: true },
    priority: 999,
    idempotency_key: `frontend_next_smoke_noop:${Date.now()}:dataJobSubmit`,
    max_attempts: 1,
  }));
  const backfillEvidence = safeWriteEvidence("dataQualityBackfill", "FNX-SW-DATA-TASK", "live");
  const backfill = await fetchJson("/api/data-quality/backfill", {
    method: "POST",
    headers: { ...headers, ...backfillEvidence.headers },
    body: JSON.stringify({ dataset_key: "daily_bars", scope: "all", start_date: "2026-06-05", end_date: "2026-06-05" }),
  });
  tasks.push(await cancelAndReadRuntimeTask(headers, Number(backfill?.id), "frontend-next backfill rollback smoke"));
  const runtimeTaskEvidence = safeWriteEvidence("runtimeTaskCreate", "FNX-SW-DATA-TASK", "live");
  tasks.push(await createAndCancelRuntimeTask(headers, runtimeTaskEvidence, {
    task_type: "frontend_next_smoke_noop",
    payload: { source: "frontend-next", smoke: true },
    priority: 999,
    idempotency_key: `frontend_next_smoke_noop:${Date.now()}:runtimeTaskCreate`,
    max_attempts: 1,
  }));
  const permissionProbe = await requestJson("/api/runtime-tasks", {
    method: "POST",
    headers: { ...safeWriteEvidence("runtimeTaskCreate", "FNX-SW-DATA-TASK", "live").headers },
    body: JSON.stringify({ task_type: "frontend_next_permission_probe", payload: {}, max_attempts: 1 }),
  });
  return {
    kind: "data_task",
    ok: tasks.every((item) => item.cancelled?.status === "cancelled" && item.readback?.status === "cancelled") && [401, 403].includes(permissionProbe.status),
    coverage: "local-isolated-enqueue-cancel-readback-403-audit",
    request_evidence: {
      data_job: dataJobEvidence.report,
      backfill: backfillEvidence.report,
      runtime_task: runtimeTaskEvidence.report,
    },
    permission_probe_status: permissionProbe.status,
    task_ids: tasks.map((item) => item.task_id),
  };
}

async function runDataRepairRollback(auth) {
  const headers = smokeHeaders(auth);
  if (!adminCapable(headers, auth)) {
    return {
      kind: "data_repair",
      ok: true,
      coverage: "not-run-admin-token-missing",
      stage: "auth",
      message: "Data repair rollback smoke requires FRONTEND_ADMIN_TOKEN or ADMIN_API_TOKEN.",
    };
  }
  const repairEvidence = safeWriteEvidence("dataQualityRepair", "FNX-SW-DATA-REPAIR", "live");
  const created = await fetchJson("/api/data-quality/repair", {
    method: "POST",
    headers: { ...headers, ...repairEvidence.headers },
    body: JSON.stringify({ dataset_key: "daily_bars", dry_run: true, refetch: false }),
  });
  const rollback = await cancelAndReadRuntimeTask(headers, Number(created?.id), "frontend-next repair rollback smoke");
  const permissionProbe = await requestJson("/api/data-quality/repair", {
    method: "POST",
    headers: { ...safeWriteEvidence("dataQualityRepair", "FNX-SW-DATA-REPAIR", "live").headers },
    body: JSON.stringify({ dataset_key: "daily_bars", dry_run: true, refetch: false }),
  });
  return {
    kind: "data_repair",
    ok: rollback.cancelled?.status === "cancelled" && rollback.readback?.status === "cancelled" && [401, 403].includes(permissionProbe.status),
    coverage: "local-isolated-dry-run-enqueue-cancel-readback-403-audit",
    request_evidence: repairEvidence.report,
    permission_probe_status: permissionProbe.status,
    task_id: rollback.task_id,
    create_shape: shape(created),
  };
}

async function runBacktestRollback(auth) {
    const headers = smokeHeaders(auth);
    const evidence = safeWriteEvidence("backtestRunCreate", "FNX-SW-BACKTEST-TASK", "live");
    const created = await fetchJson("/api/backtests", {
      method: "POST",
      headers: { ...headers, ...evidence.headers },
      body: JSON.stringify(payloads.backtestRun),
    });
    const runId = Number(created?.id ?? created?.run_id ?? created?.data?.id);
    if (!Number.isFinite(runId) || runId <= 0) {
      return { kind: "backtest_run", ok: false, stage: "create", error: "Backtest create did not return a run id.", response_shape: shape(created) };
    }
    const cancelEvidence = safeWriteEvidence("backtestRunCancel", "FNX-SW-BACKTEST-TASK", "live");
    const cancelled = await fetchJson(`/api/backtests/${runId}/cancel`, {
      method: "POST",
      headers: { ...headers, ...cancelEvidence.headers },
      body: JSON.stringify({ reason: "frontend-next rollback smoke" }),
    });
    const deleted = await fetchJson(`/api/backtests/${runId}`, {
      method: "DELETE",
      headers,
    });
    const status = deleted?.status ?? deleted?.data?.status ?? "";
    return {
      kind: "backtest_run",
      ok: status === "deleted" || deleted?.ok === true,
      mode: "create_then_delete_temp_user_run",
      coverage: "local-isolated-create-cancel-delete-readback",
      request_evidence: {
        create: evidence.report,
        cancel: cancelEvidence.report,
      },
      run_id: runId,
      create_shape: shape(created),
      cancel_shape: shape(cancelled),
      rollback_shape: shape(deleted),
      rollback_status: status,
    };
}

async function runBacktestValidationRollback(auth) {
  const headers = smokeHeaders(auth);
  const evidence = safeWriteEvidence("backtestValidationCreate", "FNX-SW-BACKTEST-TASK", "live");
  const created = await fetchJson("/api/backtests/validate", {
    method: "POST",
    headers: { ...headers, ...evidence.headers },
    body: JSON.stringify(payloads.backtestValidation),
  });
  const taskId = Number(created?.id ?? created?.task_id ?? created?.data?.id);
  if (!Number.isFinite(taskId) || taskId <= 0) {
    return { kind: "backtest_validation", ok: false, stage: "create", response_shape: shape(created) };
  }
  const cancelled = await fetchJson(`/api/backtests/validate/${taskId}/cancel`, {
    method: "POST",
    headers,
  });
  const deleted = await fetchJson(`/api/backtests/validate/${taskId}`, {
    method: "DELETE",
    headers,
  });
  return {
    kind: "backtest_validation",
    ok: deleted?.ok === true || deleted?.status === "deleted",
    coverage: "local-isolated-create-cancel-delete-readback",
    request_evidence: evidence.report,
    task_id: taskId,
    create_shape: shape(created),
    cancel_shape: shape(cancelled),
    rollback_shape: shape(deleted),
  };
}

async function runBacktestOptimizationRollback(auth) {
  const headers = smokeHeaders(auth);
  const evidence = safeWriteEvidence("backtestOptimizationCreate", "FNX-SW-BACKTEST-TASK", "live");
  const created = await fetchJson("/api/backtests/optimize", {
    method: "POST",
    headers: { ...headers, ...evidence.headers },
    body: JSON.stringify(payloads.backtestOptimization),
  });
  const taskId = Number(created?.id ?? created?.task_id ?? created?.data?.id);
  if (!Number.isFinite(taskId) || taskId <= 0) {
    return { kind: "backtest_optimization", ok: false, stage: "create", response_shape: shape(created) };
  }
  const cancelled = await fetchJson(`/api/backtests/optimize/${taskId}/cancel`, {
    method: "POST",
    headers,
  });
  const deleted = await fetchJson(`/api/backtests/optimize/${taskId}`, {
    method: "DELETE",
    headers,
  });
  return {
    kind: "backtest_optimization",
    ok: deleted?.ok === true || deleted?.status === "deleted",
    coverage: "local-isolated-create-cancel-delete-readback",
    request_evidence: evidence.report,
    task_id: taskId,
    create_shape: shape(created),
    cancel_shape: shape(cancelled),
    rollback_shape: shape(deleted),
  };
}

async function withFeatureFlags(headers, desiredFlags, runner) {
  if (!localApiBase || !adminCapable(headers, { adminCapable: true })) {
    return runner();
  }
  const before = await fetchJson("/api/settings/feature-flags", { headers });
  const originals = {};
  for (const key of Object.keys(desiredFlags)) {
    originals[key] = findFeatureFlagValue(before, key);
  }
  try {
    for (const [key, enabled] of Object.entries(desiredFlags)) {
      if (originals[key] === Boolean(enabled)) continue;
      await fetchJson(`/api/settings/feature-flags/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ key, enabled: Boolean(enabled) }),
      });
    }
    return await runner();
  } finally {
    for (const [key, enabled] of Object.entries(originals)) {
      await fetchJson(`/api/settings/feature-flags/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ key, enabled: Boolean(enabled) }),
      }).catch(() => undefined);
    }
  }
}

async function runTradeJournalRollback(auth) {
  const headers = smokeHeaders(auth);
  return withFeatureFlags(headers, { trading_experience_suite_enabled: true, trade_review_suite_enabled: true }, async () => {
    const evidence = safeWriteEvidence("tradeJournalCreate", "FNX-SW-TRADE-JOURNAL", "live");
    const created = await fetchJson("/api/trading-experience/trade-journal", {
      method: "POST",
      headers: { ...headers, ...evidence.headers },
      body: JSON.stringify(payloads.tradeJournal),
    });
    const entryId = Number(created?.entry_id ?? created?.id);
    if (!Number.isFinite(entryId) || entryId <= 0) {
      return { kind: "trade_journal", ok: false, stage: "create", response_shape: shape(created) };
    }
    const listed = await fetchJson("/api/trading-experience/trade-journal?limit=50", { headers });
    await fetchJson(`/api/trading-experience/trade-journal/${entryId}`, {
      method: "DELETE",
      headers,
    });
    const afterDelete = await fetchJson("/api/trading-experience/trade-journal?limit=50", { headers });
    return {
      kind: "trade_journal",
      ok: journalHasEntry(listed, entryId) && !journalHasEntry(afterDelete, entryId),
      coverage: "local-isolated-create-read-delete-read-feature-flag-restore",
      request_evidence: evidence.report,
      entry_id: entryId,
      create_shape: shape(created),
    };
  });
}

async function runDatabaseCheck(auth) {
  const headers = smokeHeaders(auth);
  if (!adminCapable(headers, auth)) {
    return {
      kind: "database_check",
      ok: true,
      coverage: "not-run-admin-token-missing",
      stage: "auth",
      message: "Database check requires FRONTEND_ADMIN_TOKEN or ADMIN_API_TOKEN.",
    };
  }
  const evidence = safeWriteEvidence("databaseCheck", "FNX-SW-DATABASE-MAINTENANCE", "live");
  const checked = await fetchJson("/api/settings/database/check", {
    method: "POST",
    headers: { ...headers, ...evidence.headers },
    body: JSON.stringify({ database_url: "sqlite:///./data/t_quant.db" }),
  });
  return {
    kind: "database_check",
    ok: checked?.ok === true,
    coverage: "local-readonly-admin-check",
    request_evidence: evidence.report,
    response_shape: shape(checked),
  };
}

async function captureLive(kind, runner) {
  try {
    return await runner();
  } catch (error) {
    return {
      kind,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      payload: error?.payload ?? null,
    };
  }
}

async function resolveSmokeAuth() {
  if (isolatedCliAllowed && localApiBase) {
    const registered = await registerSmokeUser();
    promoteLocalUserRole(registered.username, "admin,backtest_research,backtest_optimizer");
    const promotedToken = await refreshPromotedSmokeToken(registered.username);
    return {
      token: promotedToken,
      adminCapable: true,
      cleanup: async () => cleanupLocalSmokeUser(registered.username),
    };
  }
  if (remoteRoleSmokeAllowed) {
    const registered = await registerSmokeUser();
    await promoteRemoteUserRole(registered.username, "admin,backtest_research,backtest_optimizer");
    const promotedToken = await refreshPromotedSmokeToken(registered.username);
    return {
      token: promotedToken,
      adminCapable: true,
      userRoles: ["admin", "backtest_research", "backtest_optimizer"],
      username: registered.username,
      cleanup: async () => cleanupRemoteSmokeUser(registered.username),
    };
  }
  const existing = process.env.FRONTEND_AUTH_TOKEN || process.env.TQUANT_AUTH_TOKEN;
  if (existing) return { token: existing, adminCapable: Boolean(process.env.FRONTEND_ADMIN_TOKEN || process.env.ADMIN_API_TOKEN), cleanup: async () => undefined };
  if (!allowLocalAdminPromote) {
    const token = await ensureAccessToken(apiBase);
    return { token, adminCapable: false, cleanup: async () => undefined };
  }
  const registered = await registerSmokeUser();
  promoteLocalUserRole(registered.username, "admin,backtest_research,backtest_optimizer");
  const promotedToken = await refreshPromotedSmokeToken(registered.username);
  return {
    token: promotedToken,
    adminCapable: true,
    cleanup: async () => cleanupLocalSmokeUser(registered.username),
  };
}

function adminCapable(headers, auth) {
  return Boolean(headers["X-Admin-Token"] || auth.adminCapable);
}

function userRoleCapable(auth, role) {
  if (!role) return false;
  return new Set((auth.userRoles ?? []).map((item) => String(item).toLowerCase())).has(role.toLowerCase());
}

async function registerSmokeUser() {
  const suffix = `${Date.now()}_${Math.floor(Math.random() * 10_000)}`;
  const username = `frontend_next_smoke_${suffix}`;
  const response = await requestJson("/api/auth/register", {
    method: "POST",
    headers: {},
    body: JSON.stringify({
      username,
      password: `FrontNextSmoke-${suffix}`,
      display_name: "frontend-next smoke",
      device_name: "frontend-next-write-rollback-smoke",
    }),
  });
  if (response.status === 429) {
    const reused = await loginLatestLocalSmokeUser();
    if (reused?.accessToken) return reused;
  }
  if (!response.ok) {
    const error = new Error(`POST /api/auth/register failed with HTTP ${response.status}`);
    error.payload = response.payload;
    throw error;
  }
  const registered = response.payload;
  if (!registered?.access_token) throw new Error("Auth register did not return access_token.");
  return { username, accessToken: registered.access_token };
}

async function loginLatestLocalSmokeUser() {
  if (!localApiBase) return null;
  let usernames;
  try {
    const dbPath = resolve("../backend/data/t_quant.db");
    const sql = `
select username from users
where username like 'frontend_next_smoke_%'
order by created_at desc
limit 20;
`;
    usernames = execFileSync("sqlite3", [dbPath, sql], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] })
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  } catch {
    return null;
  }
  for (const username of usernames) {
    const password = smokePasswordForUsername(username);
    if (!password) continue;
    const response = await requestJson("/api/auth/login", {
      method: "POST",
      headers: {},
      body: JSON.stringify({ username, password, device_name: "frontend-next-write-rollback-smoke" }),
    });
    if (response.ok && response.payload?.access_token) return { username, accessToken: response.payload.access_token };
  }
  return null;
}

function smokePasswordForUsername(username) {
  if (!username.startsWith("frontend_next_smoke_")) return "";
  return `FrontNextSmoke-${username.slice("frontend_next_smoke_".length)}`;
}

function promoteLocalUserRole(username, roles) {
  const code = `
import os
from sqlalchemy import create_engine, text
url = os.environ.get("DATABASE_URL") or "sqlite:///backend/data/t_quant.db"
if not url.startswith("sqlite:///"):
    raise SystemExit("Refusing local admin promotion for non-sqlite DATABASE_URL")
engine = create_engine(url, future=True)
with engine.begin() as conn:
    result = conn.execute(text("update users set roles=:roles, token_version=token_version+1 where username=:username"), {"roles": ${JSON.stringify(roles)}, "username": ${JSON.stringify(username)}})
    if result.rowcount != 1:
        raise SystemExit(f"Expected one smoke user row, updated {result.rowcount}")
`;
  const python = existsSync(resolve("../backend/.venv/bin/python")) ? resolve("../backend/.venv/bin/python") : "python";
  execFileSync(python, ["-c", code], {
    cwd: resolve(".."),
    env: { ...process.env },
    stdio: "pipe",
  });
}

async function refreshPromotedSmokeToken(username) {
  const password = smokePasswordForUsername(username);
  if (!password) throw new Error("Unable to derive promoted smoke user password.");
  const response = await requestJson("/api/auth/login", {
    method: "POST",
    headers: {},
    body: JSON.stringify({ username, password, device_name: "frontend-next-write-rollback-smoke-promoted" }),
  });
  if (!response.ok || !response.payload?.access_token) {
    const error = new Error(`POST /api/auth/login failed with HTTP ${response.status}`);
    error.payload = response.payload;
    throw error;
  }
  return response.payload.access_token;
}

async function promoteRemoteUserRole(username, roles) {
  const adminHeaders = buildAuthHeaders();
  if (!adminHeaders["X-Admin-Token"]) {
    throw new Error("Remote isolated write smoke requires ADMIN_API_TOKEN or FRONTEND_ADMIN_TOKEN for temporary role assignment.");
  }
  const users = await fetchJson(`/api/admin/users?q=${encodeURIComponent(username)}&limit=20`, {
    headers: adminHeaders,
  });
  const user = (users?.users ?? []).find((item) => item?.username === username);
  const userId = Number(user?.id);
  if (!Number.isFinite(userId) || userId <= 0) {
    throw new Error(`Unable to locate remote smoke user ${username} after registration.`);
  }
  await fetchJson(`/api/admin/users/${userId}`, {
    method: "PUT",
    headers: adminHeaders,
    body: JSON.stringify({
      roles: roles.split(",").map((item) => item.trim()).filter(Boolean),
      can_paper_trade: true,
      is_active: true,
    }),
  });
}

async function cleanupRemoteSmokeUser(username) {
  if (!username.startsWith("frontend_next_smoke_")) return;
  const adminHeaders = buildAuthHeaders();
  if (!adminHeaders["X-Admin-Token"]) return;
  await fetchJson("/api/admin/users/test-cleanup", {
    method: "POST",
    headers: adminHeaders,
    body: JSON.stringify({
      prefixes: [username],
      dry_run: false,
      reason: "frontend-next write rollback smoke cleanup",
    }),
  }).catch(() => undefined);
}

function cleanupLocalSmokeUser(username) {
  if (!username.startsWith("frontend_next_smoke_")) return;
  const code = `
import os
from sqlalchemy import create_engine, text
url = os.environ.get("DATABASE_URL") or "sqlite:///backend/data/t_quant.db"
if not url.startswith("sqlite:///"):
    raise SystemExit("Refusing local smoke cleanup for non-sqlite DATABASE_URL")
engine = create_engine(url, future=True)
with engine.begin() as conn:
    row = conn.execute(text("select id from users where username=:username"), {"username": ${JSON.stringify(username)}}).first()
    if row is None:
        raise SystemExit(0)
    user_id = row[0]
    account_ids = [item[0] for item in conn.execute(text("select id from paper_accounts where user_id=:user_id"), {"user_id": user_id}).all()]
    if account_ids:
        params = {"user_id": user_id}
        conn.execute(text("delete from paper_trade_tags where trade_id in (select id from paper_trades where account_id in (select id from paper_accounts where user_id=:user_id))"), params)
        conn.execute(text("delete from paper_position_lots where account_id in (select id from paper_accounts where user_id=:user_id)"), params)
        conn.execute(text("delete from paper_positions where account_id in (select id from paper_accounts where user_id=:user_id)"), params)
        conn.execute(text("delete from paper_trades where account_id in (select id from paper_accounts where user_id=:user_id)"), params)
        conn.execute(text("delete from paper_orders where account_id in (select id from paper_accounts where user_id=:user_id)"), params)
        conn.execute(text("delete from paper_accounts where user_id=:user_id"), params)
    conn.execute(text("delete from user_watchlists where user_id=:user_id and memo like 'frontend-next rollback smoke%'"), {"user_id": user_id})
    conn.execute(text("delete from trading_experience_trade_journal_entries where user_id=:user_id and signal_source='frontend-next-write-rollback-smoke'"), {"user_id": user_id})
    conn.execute(text("delete from backtest_runs where owner_user_id=:user_id and name like 'frontend-next rollback smoke%'"), {"user_id": user_id})
    conn.execute(text("delete from backtest_validations where owner_user_id=:user_id and name like 'frontend-next rollback smoke%'"), {"user_id": user_id})
    conn.execute(text("delete from backtest_optimizations where owner_user_id=:user_id and name like 'frontend-next rollback smoke%'"), {"user_id": user_id})
    conn.execute(text("delete from user_sessions where user_id=:user_id"), {"user_id": user_id})
    conn.execute(text("delete from operation_audit_log where user_id=:user_id or resource_id=:username"), {"user_id": user_id, "username": ${JSON.stringify(username)}})
    conn.execute(text("delete from users where id=:user_id"), {"user_id": user_id})
`;
  const python = existsSync(resolve("../backend/.venv/bin/python")) ? resolve("../backend/.venv/bin/python") : "python";
  execFileSync(python, ["-c", code], {
    cwd: resolve(".."),
    env: { ...process.env },
    stdio: "pipe",
  });
}

async function resolveLifecycleFixture(headers) {
  const strategies = ["first_board", "trend_rebound", "n_pattern_long_wash", ""];
  for (const strategyKey of strategies) {
    const suffix = strategyKey ? `?strategy=${encodeURIComponent(strategyKey)}&limit=300` : "?limit=300";
    const listed = await fetchJson(`/api/screeners/low-buy/lifecycle${suffix}`, { headers }).catch(() => null);
    const item = firstLifecycleFixture(listed, strategyKey);
    if (item) return item;
  }
  for (const strategyKey of strategies.filter(Boolean)) {
    const synced = await fetchJson(`/api/screeners/low-buy/lifecycle?strategy=${encodeURIComponent(strategyKey)}&limit=300&sync=true`, { headers }).catch(() => null);
    const item = firstLifecycleFixture(synced, strategyKey);
    if (item) return item;
  }
  ensureLocalLifecycleFixture({ symbol: "000001", strategyKey: "first_board", tradeDate: "2026-06-05" });
  const local = await fetchJson("/api/screeners/low-buy/lifecycle?strategy=first_board&limit=300", { headers }).catch(() => null);
  const localFixture = firstLifecycleFixture(local, "first_board");
  if (localFixture) return localFixture;
  if (adminCapable(headers, { adminCapable: true })) {
    const created = await fetchJson("/api/screeners/low-buy/lifecycle/smoke-fixture", {
      method: "POST",
      headers,
      body: JSON.stringify({
        symbol: "000001",
        name: "平安银行",
        strategy_key: "first_board",
        signal_trade_date: "2026-06-05",
        reason: "frontend-next write rollback smoke",
      }),
    }).catch(() => null);
    if (created?.ok) {
      return {
        symbol: String(created.symbol),
        strategyKey: String(created.strategy_key),
        tradeDate: String(created.signal_trade_date),
        smokeFixture: true,
      };
    }
  }
  return null;
}

async function cleanupLifecycleFixture(headers, fixture) {
  return fetchJson(
    `/api/screeners/low-buy/lifecycle/smoke-fixture/${encodeURIComponent(fixture.symbol)}?strategy_key=${encodeURIComponent(fixture.strategyKey)}&signal_trade_date=${encodeURIComponent(fixture.tradeDate)}`,
    { method: "DELETE", headers },
  );
}

function firstLifecycleFixture(payload, strategyKey = "") {
  const items = Array.isArray(payload) ? payload : payload?.items ?? [];
  for (const item of items) {
    const symbol = String(item?.symbol ?? "");
    const signalTradeDate = String(item?.signal_trade_date ?? item?.trade_date ?? "");
    const resolvedStrategyKey = String(item?.strategy_key ?? strategyKey ?? "");
    if (symbol && signalTradeDate && resolvedStrategyKey) {
      return { symbol, strategyKey: resolvedStrategyKey, tradeDate: signalTradeDate };
    }
  }
  return null;
}

function ensureLocalLifecycleFixture({ symbol, strategyKey, tradeDate }) {
  if (!localApiBase) return;
  const code = `
import os
from sqlalchemy import create_engine, text
url = os.environ.get("DATABASE_URL") or "sqlite:///backend/data/t_quant.db"
if not url.startswith("sqlite:///"):
    raise SystemExit(0)
engine = create_engine(url, future=True)
with engine.begin() as conn:
    exists = conn.execute(text("""
        select id from low_buy_trade_lifecycle_snapshots
        where symbol=:symbol and strategy_key=:strategy_key and signal_trade_date=:trade_date
        limit 1
    """), {"symbol": ${JSON.stringify(symbol)}, "strategy_key": ${JSON.stringify(strategyKey)}, "trade_date": ${JSON.stringify(tradeDate)}}).first()
    if exists is not None:
        raise SystemExit(0)
    conn.execute(text("""
        insert into low_buy_trade_lifecycle_snapshots (
            user_scope, symbol, name, strategy_key, signal_trade_date, status,
            signal_state,
            entry_plan_low, entry_plan_high, stop_loss, take_profit, max_holding_days,
            entry_price, entry_trade_date, exit_price, exit_trade_date, exit_reason,
            realized_return_pct, max_gain_pct, max_drawdown_pct, attribution_note, payload_json
        ) values (
            'default', :symbol, :name, :strategy_key, :trade_date, 'planned',
            'watch',
            10.0, 10.5, 9.5, 11.0, 5,
            null, null, null, null, '',
            0.0, 0.0, 0.0, 'frontend-next rollback smoke fixture', '{}'
        )
    """), {"symbol": ${JSON.stringify(symbol)}, "name": "平安银行", "strategy_key": ${JSON.stringify(strategyKey)}, "trade_date": ${JSON.stringify(tradeDate)}})
`;
  const python = existsSync(resolve("../backend/.venv/bin/python")) ? resolve("../backend/.venv/bin/python") : "python";
  execFileSync(python, ["-c", code], {
    cwd: resolve(".."),
    env: { ...process.env },
    stdio: "pipe",
  });
}

async function fetchJson(path, init = {}) {
  const result = await requestJson(path, init);
  if (!result.ok) {
    const error = new Error(`${init.method ?? "GET"} ${path} failed with HTTP ${result.status}`);
    error.payload = result.payload;
    throw error;
  }
  return result.payload;
}

async function requestJson(path, init = {}) {
  const maxAttempts = Number(process.env.FRONTEND_NEXT_WRITE_SMOKE_RETRY_ATTEMPTS || 5);
  let lastResult = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    let response;
    try {
      response = await fetch(`${apiBase}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
      });
    } catch (error) {
      if (attempt >= maxAttempts) throw error;
      await delay(attempt * 900);
      continue;
    }
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = text;
    }
    lastResult = { ok: response.ok, status: response.status, payload };
    if (response.status !== 429) return lastResult;
    const retryAfter = Number(response.headers.get("retry-after") || 0);
    const delayMs = Math.max(retryAfter * 1000, attempt * 900);
    await delay(delayMs);
  }
  return lastResult;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function findFeatureFlagValue(payload, key) {
  if (payload?.flags && !Array.isArray(payload.flags) && typeof payload.flags === "object") {
    return Boolean(payload.flags[key]?.enabled);
  }
  const flags = Array.isArray(payload) ? payload : payload?.items || [];
  const item = flags.find((flag) => flag?.key === key || flag?.name === key);
  return Boolean(item?.enabled);
}

function selectSmokeFeatureFlag(payload) {
  const flags = featureFlagItems(payload);
  const byKey = new Map(flags.filter((flag) => flag?.key).map((flag) => [flag.key, flag]));
  for (const key of smokeFeatureFlagCandidates) {
    const flag = byKey.get(key);
    if (flag) return { key, enabled: Boolean(flag.enabled) };
  }
  const fallback = flags.find((flag) => typeof flag?.key === "string" && flag.key.startsWith("frontend_"));
  if (fallback) return { key: fallback.key, enabled: Boolean(fallback.enabled) };
  throw new Error("No runtime-supported frontend feature flag is available for rollback smoke.");
}

function featureFlagItems(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (payload?.flags && typeof payload.flags === "object") {
    return Object.entries(payload.flags).map(([key, value]) => ({ key, ...(value && typeof value === "object" ? value : { enabled: value }) }));
  }
  return [];
}

function smokeHeaders(auth) {
  return { ...buildAuthHeaders(), Authorization: `Bearer ${auth.token}` };
}

function watchlistHasSymbol(payload, symbol) {
  const items = Array.isArray(payload) ? payload : payload?.items ?? payload?.watchlist ?? [];
  return items.some((item) => String(item?.symbol ?? "") === symbol);
}

function journalHasEntry(payload, entryId) {
  const items = Array.isArray(payload) ? payload : payload?.items ?? [];
  return items.some((item) => Number(item?.entry_id ?? item?.id) === entryId);
}

function findLifecycle(payload, symbol, tradeDate, strategyKey) {
  const items = Array.isArray(payload) ? payload : payload?.items ?? [];
  return items.find(
    (item) =>
      String(item?.symbol ?? "") === symbol &&
      String(item?.signal_trade_date ?? "") === tradeDate &&
      String(item?.strategy_key ?? "") === strategyKey,
  );
}

function findStrategyGovernance(payload, strategyKey) {
  const items = Array.isArray(payload) ? payload : payload?.items ?? [];
  return items.find((item) => String(item?.strategy_key ?? item?.key ?? "") === strategyKey);
}

function listHasReview(payload, reviewId) {
  const items = Array.isArray(payload) ? payload : payload?.items ?? [];
  return items.some((item) => Number(item?.review_id ?? item?.id) === reviewId);
}

async function createAndCancelRuntimeTask(headers, evidence, payload) {
  const created = await fetchJson("/api/runtime-tasks", {
    method: "POST",
    headers: { ...headers, ...evidence.headers },
    body: JSON.stringify(payload),
  });
  return cancelAndReadRuntimeTask(headers, Number(created?.id), "frontend-next runtime task rollback smoke", created);
}

async function cancelAndReadRuntimeTask(headers, taskId, reason, created = null) {
  if (!Number.isFinite(taskId) || taskId <= 0) {
    throw new Error(`Runtime task response did not include a task id: ${JSON.stringify(shape(created))}`);
  }
  const cancelled = await fetchJson(`/api/runtime-tasks/${taskId}/cancel`, {
    method: "POST",
    headers,
    body: JSON.stringify({ reason }),
  });
  const readback = await fetchJson(`/api/runtime-tasks/${taskId}`, { headers });
  return { task_id: taskId, created, cancelled, readback };
}

function safeWriteEvidence(operation, contractId, writeMode = "isolated-live-smoke") {
  const clientRequestId = `fnx-${operation}-${Date.now().toString(36)}-${Math.random().toString(16).slice(2)}`;
  const headers = {
    "X-Frontend-Next-Client-Request-Id": clientRequestId,
    "X-Frontend-Next-Contract-Id": contractId,
    "X-Frontend-Next-Contract-State": writeMode === "live" ? "defined_production_ready" : "defined_isolated_live_smoke",
    "X-Frontend-Next-Operation": operation,
    "X-Frontend-Next-Source": "frontend-next",
    "X-Frontend-Next-Write-Mode": writeMode,
  };
  return {
    headers,
    report: {
      client_request_id: clientRequestId,
      contract_id: contractId,
      operation,
      write_mode: writeMode,
    },
  };
}

function generateTotpCode(secret) {
  const counter = Math.floor(Date.now() / 1000 / 30);
  const key = base32Decode(secret);
  const buffer = Buffer.alloc(8);
  buffer.writeBigUInt64BE(BigInt(counter));
  const digest = crypto.createHmac("sha1", key).update(buffer).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const value =
    ((digest[offset] & 0x7f) << 24) |
    ((digest[offset + 1] & 0xff) << 16) |
    ((digest[offset + 2] & 0xff) << 8) |
    (digest[offset + 3] & 0xff);
  return String(value % 1_000_000).padStart(6, "0");
}

function base32Decode(value) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const cleaned = String(value).replace(/=+$/g, "").replace(/\s+/g, "").toUpperCase();
  const bytes = [];
  let bits = 0;
  let bitLength = 0;
  for (const char of cleaned) {
    const index = alphabet.indexOf(char);
    if (index < 0) continue;
    bits = (bits << 5) | index;
    bitLength += 5;
    if (bitLength >= 8) {
      bytes.push((bits >> (bitLength - 8)) & 0xff);
      bitLength -= 8;
    }
  }
  return Buffer.from(bytes);
}

function shape(value, depth = 0) {
  if (depth > 2) return typeof value;
  if (Array.isArray(value)) return value.length ? [shape(value[0], depth + 1)] : [];
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, shape(value[key], depth + 1)]));
  }
  return typeof value;
}
