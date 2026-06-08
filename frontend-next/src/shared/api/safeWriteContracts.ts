import type { ApiOperationName, OperationContractStatus, OperationWriteMode } from "./operations";

export type SafeWriteContractState =
  | "defined_shadow_only"
  | "defined_backend_needed"
  | "defined_isolated_live_smoke"
  | "defined_production_ready"
  | "cutover_excluded";

export interface SafeWriteContract {
  id: SafeWriteContractId;
  title: string;
  state: SafeWriteContractState;
  operations: readonly ApiOperationName[];
  requiredRole: string;
  requiredMode: "shadow" | "isolated-live-smoke" | "live" | "excluded";
  requiredGuards: readonly string[];
  requestContract: readonly string[];
  responseContract: readonly string[];
  rollbackContract: readonly string[];
  auditContract: readonly string[];
  evidenceRequired: readonly string[];
}

export type SafeWriteContractId =
  | "FNX-SW-AUTH-MFA"
  | "FNX-SW-WATCHLIST"
  | "FNX-SW-PLAYBOOK-LIFECYCLE"
  | "FNX-SW-PAPER-ORDER"
  | "FNX-SW-PAPER-ACCOUNT"
  | "FNX-SW-STRATEGY-REVIEW"
  | "FNX-SW-TRADE-JOURNAL"
  | "FNX-SW-BACKTEST-TASK"
  | "FNX-SW-DATA-TASK"
  | "FNX-SW-DATA-REPAIR"
  | "FNX-SW-SETTINGS-SECTION"
  | "FNX-SW-FEATURE-FLAG"
  | "FNX-SW-DATABASE-MAINTENANCE";

export interface SafeWriteContractSummary {
  id: SafeWriteContractId;
  title: string;
  state: SafeWriteContractState;
  requiredMode: SafeWriteContract["requiredMode"];
  requiredRole: string;
  evidenceRequired: readonly string[];
}

export interface SafeWriteRequestEvidence {
  clientRequestId: string;
  headers: Record<string, string>;
  contract: SafeWriteContractSummary;
}

export const safeWriteContracts = {
  "FNX-SW-AUTH-MFA": {
    id: "FNX-SW-AUTH-MFA",
    title: "Account MFA setup, enable and disable",
    state: "defined_production_ready",
    operations: ["authTotpSetup", "authTotpEnable", "authTotpDisable"],
    requiredRole: "authenticated",
    requiredMode: "live",
    requiredGuards: ["fresh session", "current password or TOTP proof", "no secret value in telemetry"],
    requestContract: ["client_request_id", "mfa_intent", "totp_code when enabling or disabling"],
    responseContract: ["mfa_status", "updated_user", "audit_id", "secret shown only during setup"],
    rollbackContract: ["disable or restore previous MFA state using isolated account"],
    auditContract: ["operator", "user_id", "action", "before_state", "after_state"],
    evidenceRequired: ["account-security fixture", "audit echo", "restore previous MFA state"],
  },
  "FNX-SW-WATCHLIST": {
    id: "FNX-SW-WATCHLIST",
    title: "Watchlist and monitor observation maintenance",
    state: "defined_production_ready",
    operations: ["watchlistUpsert", "watchlistRemove"],
    requiredRole: "authenticated_observer",
    requiredMode: "live",
    requiredGuards: ["ConfirmAction", "idempotency key", "production board no-sort guard"],
    requestContract: ["client_request_id", "symbol", "reason", "watch_scope", "idempotency_key"],
    responseContract: ["watchlist_item", "operation_id", "audit_id", "invalidates"],
    rollbackContract: ["delete created item or restore previous item snapshot"],
    auditContract: ["operator", "symbol", "before_hash", "after_hash", "source=frontend-next"],
    evidenceRequired: ["no priority_board change", "create/update/delete rollback trace", "request count trace"],
  },
  "FNX-SW-PLAYBOOK-LIFECYCLE": {
    id: "FNX-SW-PLAYBOOK-LIFECYCLE",
    title: "Playbook lifecycle and strategy governance",
    state: "defined_production_ready",
    operations: ["lowBuyLifecycleUpdate", "lowBuyStrategyUpdate"],
    requiredRole: "admin or strategy operator",
    requiredMode: "live",
    requiredGuards: ["research-only guard", "near_entry watch-only guard", "ConfirmAction"],
    requestContract: ["client_request_id", "symbol or strategy_key", "target_state", "reason", "idempotency_key"],
    responseContract: ["status", "audit_id", "before_hash", "after_hash", "invalidates"],
    rollbackContract: ["restore previous lifecycle or strategy governance snapshot"],
    auditContract: ["operator", "strategy_key", "target_state", "blocked_reason when rejected"],
    evidenceRequired: ["research-only boundary trace", "rollback trace", "strategy meta refetch echo"],
  },
  "FNX-SW-PAPER-ORDER": {
    id: "FNX-SW-PAPER-ORDER",
    title: "Paper order create and cancel",
    state: "defined_production_ready",
    operations: ["paperOrderCreate", "paperOrderCancel"],
    requiredRole: "can_paper_trade + live_smoke_operator",
    requiredMode: "live",
    requiredGuards: ["PaperGuard", "duplicate submit guard", "isolated account", "ConfirmAction"],
    requestContract: ["client_request_id", "symbol", "side", "quantity", "order_type", "source=frontend-next", "idempotency_key"],
    responseContract: ["order_id", "order_status", "account_id", "audit_id", "rollback_action"],
    rollbackContract: ["cancel order or reset isolated paper account"],
    auditContract: ["operator", "account_id", "order_id", "before_cash", "after_cash"],
    evidenceRequired: ["isolated paper account", "create/cancel or reset trace", "paper workspace refetch echo"],
  },
  "FNX-SW-PAPER-ACCOUNT": {
    id: "FNX-SW-PAPER-ACCOUNT",
    title: "Paper account pause, resume, refresh and reconcile",
    state: "defined_production_ready",
    operations: ["paperAccountPause", "paperAccountResume", "paperAccountReconcile", "paperPositionsRefresh"],
    requiredRole: "can_paper_trade; admin for reconcile/apply",
    requiredMode: "live",
    requiredGuards: ["PaperGuard", "admin guard for reconcile", "dry-run before apply", "ConfirmAction"],
    requestContract: ["client_request_id", "account_id", "reason", "dry_run", "apply_token when applying"],
    responseContract: ["account_status", "diff_summary", "audit_id", "rollback_token"],
    rollbackContract: ["restore previous account status or reset isolated account snapshot"],
    auditContract: ["operator", "account_id", "dry_run_id", "applied_changes"],
    evidenceRequired: ["dry-run diff", "apply/rollback trace", "admin 403 fixture"],
  },
  "FNX-SW-STRATEGY-REVIEW": {
    id: "FNX-SW-STRATEGY-REVIEW",
    title: "Strategy review record and refresh",
    state: "defined_production_ready",
    operations: ["strategyReviewRecord", "strategyTrackingRefresh"],
    requiredRole: "authenticated_observer or reviewer",
    requiredMode: "live",
    requiredGuards: ["strategy boundary guard", "ConfirmAction", "no production ranking mutation"],
    requestContract: ["client_request_id", "strategy_key", "symbol", "review_state", "notes", "idempotency_key"],
    responseContract: ["review_id", "audit_id", "strategy_item", "invalidates"],
    rollbackContract: ["delete review record or restore previous review snapshot"],
    auditContract: ["operator", "strategy_key", "symbol", "before_hash", "after_hash"],
    evidenceRequired: ["review CRUD rollback", "strategyTrackingReview refetch echo", "no priority_board effect"],
  },
  "FNX-SW-TRADE-JOURNAL": {
    id: "FNX-SW-TRADE-JOURNAL",
    title: "Trading journal CRUD",
    state: "defined_production_ready",
    operations: ["tradeJournalCreate"],
    requiredRole: "authenticated_observer",
    requiredMode: "live",
    requiredGuards: ["ConfirmAction", "symbol validation", "no paper/prod side effect"],
    requestContract: ["client_request_id", "symbol", "action", "notes", "tags", "idempotency_key"],
    responseContract: ["entry_id", "journal_entry", "audit_id"],
    rollbackContract: ["delete created journal entry or restore previous entry snapshot"],
    auditContract: ["operator", "entry_id", "symbol", "action"],
    evidenceRequired: ["create/update/delete rollback trace", "journal refetch echo", "no paper order request"],
  },
  "FNX-SW-BACKTEST-TASK": {
    id: "FNX-SW-BACKTEST-TASK",
    title: "Backtest run create, cancel, validation and optimization",
    state: "defined_production_ready",
    operations: ["backtestRunCreate", "backtestRunCancel", "backtestValidationCreate", "backtestOptimizationCreate"],
    requiredRole: "authenticated_observer + live_smoke_operator",
    requiredMode: "live",
    requiredGuards: ["test run marker", "resource tier limit", "ConfirmAction", "task status truth table"],
    requestContract: ["client_request_id", "run_name", "strategy_keys", "date_range", "test_run=true", "idempotency_key"],
    responseContract: ["run_id or task_id", "status", "queued_at", "audit_id", "cancel_endpoint"],
    rollbackContract: ["cancel running task or delete/soft-delete created test run"],
    auditContract: ["operator", "run_id", "task_type", "before_status", "after_status"],
    evidenceRequired: ["test run marker", "cancel/delete rollback", "task status refetch echo"],
  },
  "FNX-SW-DATA-TASK": {
    id: "FNX-SW-DATA-TASK",
    title: "Data task and backfill enqueue",
    state: "defined_production_ready",
    operations: ["dataJobSubmit", "dataQualityBackfill", "runtimeTaskCreate"],
    requiredRole: "admin + live_smoke_operator",
    requiredMode: "live",
    requiredGuards: ["admin guard", "bounded task scope", "ConfirmAction", "idempotency key"],
    requestContract: ["client_request_id", "task_type", "scope", "dry_run", "idempotency_key"],
    responseContract: ["task_id", "task_status", "audit_id", "idempotency_hit"],
    rollbackContract: ["cancel queued task or mark test task cancelled"],
    auditContract: ["operator", "task_id", "task_type", "scope", "cancel_status"],
    evidenceRequired: ["admin 403 fixture", "queued/cancelled trace", "runtimeTasks refetch echo"],
  },
  "FNX-SW-DATA-REPAIR": {
    id: "FNX-SW-DATA-REPAIR",
    title: "Data repair dry-run and apply",
    state: "defined_production_ready",
    operations: ["dataQualityRepair"],
    requiredRole: "admin + live_smoke_operator",
    requiredMode: "live",
    requiredGuards: ["admin guard", "dry-run before apply", "ConfirmAction", "bounded dataset"],
    requestContract: ["client_request_id", "dataset_key", "symbol_scope", "dry_run", "dry_run_id or apply_token"],
    responseContract: ["repair_id", "dry_run_diff", "affected_rows", "audit_id", "rollback_token"],
    rollbackContract: ["rollback repair_id or restore affected dataset snapshot"],
    auditContract: ["operator", "repair_id", "dataset_key", "affected_rows", "rollback_status"],
    evidenceRequired: ["dry-run diff", "apply/rollback trace", "data quality refetch echo"],
  },
  "FNX-SW-SETTINGS-SECTION": {
    id: "FNX-SW-SETTINGS-SECTION",
    title: "Settings section save",
    state: "defined_production_ready",
    operations: ["settingsUpdate", "sectorExclusionsUpdate", "factorWeightsUpdate"],
    requiredRole: "authenticated or admin by section",
    requiredMode: "live",
    requiredGuards: ["section validator", "permission by section", "ConfirmAction", "echo verification"],
    requestContract: ["client_request_id", "section_key", "patch", "base_version", "idempotency_key"],
    responseContract: ["section_key", "settings_version", "updated_payload", "audit_id"],
    rollbackContract: ["restore previous section snapshot by version"],
    auditContract: ["operator", "section_key", "before_hash", "after_hash", "version"],
    evidenceRequired: ["save echo", "restore previous version", "403 section fixture"],
  },
  "FNX-SW-FEATURE-FLAG": {
    id: "FNX-SW-FEATURE-FLAG",
    title: "Feature flag update",
    state: "defined_production_ready",
    operations: ["featureFlagUpdate"],
    requiredRole: "admin + live_smoke_operator",
    requiredMode: "live",
    requiredGuards: ["admin guard", "allowed flag list", "ConfirmAction", "restore previous value"],
    requestContract: ["client_request_id", "key", "enabled", "reason", "idempotency_key"],
    responseContract: ["key", "enabled", "previous_enabled", "audit_id"],
    rollbackContract: ["restore previous_enabled and verify audit echo"],
    auditContract: ["operator", "key", "before_value", "after_value", "restore_audit_id"],
    evidenceRequired: ["toggle/restore trace", "featureFlagAudit echo", "admin 403 fixture"],
  },
  "FNX-SW-DATABASE-MAINTENANCE": {
    id: "FNX-SW-DATABASE-MAINTENANCE",
    title: "Database check and migration actions",
    state: "cutover_excluded",
    operations: ["databaseCheck", "databaseMigrate"],
    requiredRole: "admin + live_smoke_operator",
    requiredMode: "excluded",
    requiredGuards: ["admin guard", "dry-run before migrate", "manual confirmation", "maintenance window"],
    requestContract: ["client_request_id", "dry_run", "migration_plan_id", "confirm_phrase"],
    responseContract: ["plan_id", "dry_run_report", "migration_status", "audit_id"],
    rollbackContract: ["documented database restore or migration rollback plan"],
    auditContract: ["operator", "plan_id", "target_database", "result"],
    evidenceRequired: ["dry-run report", "rollback plan evidence", "no production database mutation in shadow"],
  },
} as const satisfies Record<SafeWriteContractId, SafeWriteContract>;

const operationContractEntries = Object.values(safeWriteContracts).flatMap((contract) =>
  contract.operations.map((operation) => [operation, contract.id] as const),
);

export const operationSafeWriteContracts = Object.freeze(
  Object.fromEntries(operationContractEntries) as Partial<Record<ApiOperationName, SafeWriteContractId>>,
);

export function safeWriteContractForOperation(operation: ApiOperationName): SafeWriteContract | undefined {
  const id = operationSafeWriteContracts[operation];
  return id ? safeWriteContracts[id] : undefined;
}

export function safeWriteContractSummaryForOperation(operation: ApiOperationName): SafeWriteContractSummary | undefined {
  const contract = safeWriteContractForOperation(operation);
  if (!contract) return undefined;
  return {
    id: contract.id,
    title: contract.title,
    state: contract.state,
    requiredMode: contract.requiredMode,
    requiredRole: contract.requiredRole,
    evidenceRequired: contract.evidenceRequired,
  };
}

export function safeWriteContractBlockedMessage(operation: ApiOperationName, contractStatus: OperationContractStatus): string {
  const contract = safeWriteContractForOperation(operation);
  if (!contract) return `blocked_contract_needed: backend safe write contract is required before ${operation} can be sent`;
  if (contractStatus === "shadow-only") {
    return `${contract.id}: operation is shadow-only; backend write is not available for ${operation}`;
  }
  return `blocked_contract_needed: ${contract.id} is defined, but backend implementation, isolated data and rollback evidence are required before ${operation} can be sent`;
}

export function safeWriteRequestEvidenceForOperation(
  operation: ApiOperationName,
  writeMode: OperationWriteMode,
  clientRequestId = createSafeWriteClientRequestId(operation),
): SafeWriteRequestEvidence | undefined {
  const contract = safeWriteContractSummaryForOperation(operation);
  if (!contract) return undefined;
  return {
    clientRequestId,
    contract,
    headers: {
      "X-Frontend-Next-Client-Request-Id": clientRequestId,
      "X-Frontend-Next-Contract-Id": contract.id,
      "X-Frontend-Next-Contract-State": contract.state,
      "X-Frontend-Next-Operation": operation,
      "X-Frontend-Next-Source": "frontend-next",
      "X-Frontend-Next-Write-Mode": writeMode,
    },
  };
}

export function createSafeWriteClientRequestId(operation: ApiOperationName): string {
  const random =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(16).slice(2)}`;
  return `fnx-${operation}-${random}`.replace(/[^a-zA-Z0-9._:-]/g, "-");
}
