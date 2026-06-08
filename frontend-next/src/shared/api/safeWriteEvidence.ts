import type { ApiOperationName } from "./operations";
import type { SafeWriteContractId } from "./safeWriteContracts";

export type SafeWriteEvidenceStatus = "verified" | "partial" | "not-applicable";

export interface SafeWriteOperationEvidence {
  operation: ApiOperationName;
  status: SafeWriteEvidenceStatus;
  evidence: readonly string[];
  rollback: readonly string[];
  readback: readonly string[];
  permission: readonly string[];
  audit: readonly string[];
  notes?: string;
}

export interface SafeWriteContractEvidence {
  contractId: SafeWriteContractId;
  status: SafeWriteEvidenceStatus;
  operations: readonly SafeWriteOperationEvidence[];
  notes?: string;
}

export const safeWriteEvidence = {
  "FNX-SW-AUTH-MFA": {
    contractId: "FNX-SW-AUTH-MFA",
    status: "verified",
    operations: [
      {
        operation: "authTotpSetup",
        status: "verified",
        evidence: ["isolated-account mfa setup response includes secret and otpauth_uri"],
        rollback: ["authTotpDisable restores isolated account MFA state"],
        readback: ["authMe confirms mfa_totp_enabled after enable/disable"],
        permission: ["authenticated user required; unauthenticated route returns 401"],
        audit: ["operation audit records auth_mfa_setup/auth_mfa_enable/auth_mfa_disable"],
      },
      {
        operation: "authTotpEnable",
        status: "verified",
        evidence: ["generated TOTP code enables only for same isolated account"],
        rollback: ["authTotpDisable with current code restores previous disabled state"],
        readback: ["authMe confirms enabled state before rollback"],
        permission: ["authenticated user required; stale/missing TOTP rejected"],
        audit: ["operation audit records auth_mfa_enable"],
      },
      {
        operation: "authTotpDisable",
        status: "verified",
        evidence: ["generated TOTP code disables isolated account MFA"],
        rollback: ["final state is disabled and secret is not displayed again"],
        readback: ["authMe confirms disabled state"],
        permission: ["authenticated user required"],
        audit: ["operation audit records auth_mfa_disable"],
      },
    ],
  },
  "FNX-SW-WATCHLIST": {
    contractId: "FNX-SW-WATCHLIST",
    status: "verified",
    operations: [
      {
        operation: "watchlistUpsert",
        status: "verified",
        evidence: ["create/update uses isolated auth user watchlist row"],
        rollback: ["watchlistRemove deletes the created symbol"],
        readback: ["watchlist GET verifies created item and deletion"],
        permission: ["unauthenticated request rejected by auth guard"],
        audit: ["frontend-next client_request_id is sent in safe-write headers"],
      },
      {
        operation: "watchlistRemove",
        status: "verified",
        evidence: ["delete targets the isolated auth user symbol only"],
        rollback: ["upsert can restore previous symbol snapshot when needed"],
        readback: ["watchlist GET verifies item is absent"],
        permission: ["unauthenticated request rejected by auth guard"],
        audit: ["frontend-next client_request_id is sent in safe-write headers"],
      },
    ],
  },
  "FNX-SW-PAPER-ORDER": {
    contractId: "FNX-SW-PAPER-ORDER",
    status: "verified",
    operations: [
      {
        operation: "paperOrderCreate",
        status: "verified",
        evidence: ["isolated paper account creates an order or non-persisting business-rule probe"],
        rollback: ["admin reset restores isolated paper account"],
        readback: ["paper workspace/orders refetch confirms order/reset"],
        permission: ["can_paper_trade route guard and E2E 403 coverage"],
        audit: ["operation audit records paper_order_create"],
      },
      {
        operation: "paperOrderCancel",
        status: "verified",
        evidence: ["pending isolated paper order can be cancelled by owner"],
        rollback: ["admin reset clears isolated paper account after cancel"],
        readback: ["paper order GET/List confirms cancelled status"],
        permission: ["cross-account ownership returns 404"],
        audit: ["operation audit records paper_order_cancel"],
      },
    ],
  },
  "FNX-SW-PAPER-ACCOUNT": {
    contractId: "FNX-SW-PAPER-ACCOUNT",
    status: "verified",
    operations: [
      {
        operation: "paperAccountPause",
        status: "verified",
        evidence: ["isolated paper account can be paused by owner"],
        rollback: ["paperAccountResume restores active status"],
        readback: ["paper account GET confirms paused/active status"],
        permission: ["can_paper_trade route guard"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "paperAccountResume",
        status: "verified",
        evidence: ["isolated paper account resumes after pause"],
        rollback: ["pause/resume pair restores active state"],
        readback: ["paper account GET confirms active status"],
        permission: ["can_paper_trade route guard"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "paperAccountReconcile",
        status: "verified",
        evidence: ["dry-run reconcile returns diff summary for isolated account"],
        rollback: ["dry-run has no mutation; reset remains available for apply smoke"],
        readback: ["paper account GET remains consistent after preview"],
        permission: ["admin auth required for apply/preview endpoint"],
        audit: ["operation audit records paper_account_reconcile"],
      },
      {
        operation: "paperPositionsRefresh",
        status: "verified",
        evidence: ["isolated paper positions refresh is scoped to the owner account"],
        rollback: ["no position mutation when isolated account has no holdings"],
        readback: ["positions GET confirms stable empty or refreshed state"],
        permission: ["can_paper_trade route guard"],
        audit: ["safe-write headers include client_request_id"],
      },
    ],
  },
  "FNX-SW-TRADE-JOURNAL": {
    contractId: "FNX-SW-TRADE-JOURNAL",
    status: "verified",
    operations: [
      {
        operation: "tradeJournalCreate",
        status: "verified",
        evidence: ["isolated paper user creates a review-only journal entry"],
        rollback: ["trade journal DELETE removes the created entry"],
        readback: ["trade journal GET confirms create/delete"],
        permission: ["other-account account_id is rejected"],
        audit: ["safe-write headers include client_request_id"],
      },
    ],
  },
  "FNX-SW-BACKTEST-TASK": {
    contractId: "FNX-SW-BACKTEST-TASK",
    status: "verified",
    operations: [
      {
        operation: "backtestRunCreate",
        status: "verified",
        evidence: ["isolated user creates queued test run with fn-next marker"],
        rollback: ["backtest DELETE marks created run deleted"],
        readback: ["backtest detail/list confirms status transition"],
        permission: ["auth route guard and strategy access validation"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "backtestRunCancel",
        status: "verified",
        evidence: ["isolated queued test run can be cancelled"],
        rollback: ["cancelled test run is then deleted"],
        readback: ["backtest detail confirms cancelled/deleted"],
        permission: ["auth route guard and owner visibility"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "backtestValidationCreate",
        status: "verified",
        evidence: ["research-capable isolated user creates validation task"],
        rollback: ["validation DELETE removes created task"],
        readback: ["validation detail/list confirms status"],
        permission: ["research role required; non-research path covered by E2E"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "backtestOptimizationCreate",
        status: "verified",
        evidence: ["optimizer-capable isolated user creates optimization task"],
        rollback: ["optimization DELETE removes created task"],
        readback: ["optimization detail/list confirms status"],
        permission: ["optimizer role required"],
        audit: ["safe-write headers include client_request_id"],
      },
    ],
  },
  "FNX-SW-FEATURE-FLAG": {
    contractId: "FNX-SW-FEATURE-FLAG",
    status: "verified",
    operations: [
      {
        operation: "featureFlagUpdate",
        status: "verified",
        evidence: ["admin isolated user toggles a runtime-supported frontend flag"],
        rollback: ["restore previous flag value and verify"],
        readback: ["feature flags GET confirms restored value"],
        permission: ["non-admin receives 403"],
        audit: ["feature flag audit and operation audit record update"],
      },
    ],
  },
  "FNX-SW-PLAYBOOK-LIFECYCLE": {
    contractId: "FNX-SW-PLAYBOOK-LIFECYCLE",
    status: "verified",
    operations: [
      {
        operation: "lowBuyLifecycleUpdate",
        status: "verified",
        evidence: ["admin-token endpoint updates only lifecycle display/review state and returns audit_id before_hash after_hash"],
        rollback: ["write-rollback smoke restores previous lifecycle snapshot for deterministic fixture row"],
        readback: ["lowBuyLifecycle GET verifies status after update and after restore"],
        permission: ["missing admin token returns 401 and invalid token returns 403"],
        audit: ["operation_audit_log records frontend_next.low_buy_lifecycle_update with safe-write headers"],
      },
      {
        operation: "lowBuyStrategyUpdate",
        status: "verified",
        evidence: ["admin isolated update can pause/restore a strategy governance override and returns audit_id before_hash after_hash"],
        rollback: ["write-rollback smoke restores previous strategy governance status"],
        readback: ["low-buy strategies GET verifies restored state"],
        permission: ["missing admin token returns 401 and invalid token returns 403"],
        audit: ["operation_audit_log records frontend_next.low_buy_strategy_governance_update with safe-write headers"],
      },
    ],
    notes: "Playbook writes remain review/governance scoped and explicitly do not mutate priority_board, production_score or production sorting.",
  },
  "FNX-SW-STRATEGY-REVIEW": {
    contractId: "FNX-SW-STRATEGY-REVIEW",
    status: "verified",
    operations: [
      {
        operation: "strategyReviewRecord",
        status: "verified",
        evidence: ["backend review-records endpoint writes review-only record into operation audit trail"],
        rollback: ["DELETE /api/strategy-tracking/review-records/{review_id} records rollback delete marker"],
        readback: ["GET /api/strategy-tracking/review-records verifies create and deletion absence"],
        permission: ["authenticated user required; unauthenticated route returns 401"],
        audit: ["operation_audit_log records frontend_next.strategy_review_record and strategy_review_delete"],
      },
      {
        operation: "strategyTrackingRefresh",
        status: "verified",
        evidence: ["admin-token refresh endpoint exists, is bounded by range and returns audit_id"],
        rollback: ["refresh is read-model rebuild; no production strategy source mutation"],
        readback: ["strategy summary/items refetch after refresh"],
        permission: ["missing admin token returns 401 and invalid token returns 403"],
        audit: ["operation_audit_log records frontend_next.strategy_tracking_refresh with changed_strategy_results=false"],
      },
    ],
    notes: "Review records are display/review artifacts only and do not mutate production ranking inputs.",
  },
  "FNX-SW-DATA-TASK": {
    contractId: "FNX-SW-DATA-TASK",
    status: "verified",
    operations: [
      {
        operation: "dataJobSubmit",
        status: "verified",
        evidence: ["operation maps to POST /api/runtime-tasks with bounded task payload and audit_id"],
        rollback: ["POST /api/runtime-tasks/{task_id}/cancel marks isolated test task cancelled"],
        readback: ["GET /api/runtime-tasks/{task_id} verifies queued then cancelled"],
        permission: ["missing admin token returns 401 and invalid token returns 403"],
        audit: ["operation_audit_log records frontend_next.runtime_task_create and runtime_task_cancel"],
      },
      {
        operation: "dataQualityBackfill",
        status: "verified",
        evidence: ["admin-token backfill endpoint enqueues bounded runtime task and returns audit_id"],
        rollback: ["runtime task cancel endpoint marks isolated backfill task cancelled"],
        readback: ["runtimeTasks GET/detail confirms created test task and cancelled status"],
        permission: ["missing admin token returns 401 and invalid token returns 403"],
        audit: ["operation_audit_log records frontend_next.data_quality_backfill with safe-write headers"],
      },
      {
        operation: "runtimeTaskCreate",
        status: "verified",
        evidence: ["admin-token runtime task endpoint enqueues harmless smoke task and returns audit_id"],
        rollback: ["runtime task cancel endpoint marks isolated task cancelled"],
        readback: ["runtimeTasks GET/detail confirms created and cancelled status"],
        permission: ["missing admin token returns 401 and invalid token returns 403"],
        audit: ["operation_audit_log records frontend_next.runtime_task_create with safe-write headers"],
      },
    ],
    notes: "Runtime task smoke uses local isolated test task types and cancel rollback; worker semantics are unchanged.",
  },
  "FNX-SW-DATA-REPAIR": {
    contractId: "FNX-SW-DATA-REPAIR",
    status: "verified",
    operations: [
      {
        operation: "dataQualityRepair",
        status: "verified",
        evidence: ["admin-token repair endpoint enqueues dry-run or bounded repair task and returns audit_id"],
        rollback: ["runtime task cancel endpoint marks isolated repair task cancelled before worker apply"],
        readback: ["runtimeTasks/detail confirms repair task cancelled; data quality refetch remains available"],
        permission: ["missing admin token returns 401 and invalid token returns 403"],
        audit: ["operation_audit_log records frontend_next.data_quality_repair with safe-write headers"],
      },
    ],
    notes: "Cutover smoke uses dry-run/cancelled isolated task evidence; destructive database migration remains excluded.",
  },
  "FNX-SW-SETTINGS-SECTION": {
    contractId: "FNX-SW-SETTINGS-SECTION",
    status: "verified",
    operations: [
      {
        operation: "settingsUpdate",
        status: "verified",
        evidence: ["admin-token settings update echoes updated settings"],
        rollback: ["restore previous section values"],
        readback: ["settings GET confirms restored values"],
        permission: ["admin token required"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "sectorExclusionsUpdate",
        status: "verified",
        evidence: ["isolated user updates own sector exclusions"],
        rollback: ["restore previous excluded sector list"],
        readback: ["sectorExclusions GET confirms restored list"],
        permission: ["authenticated user scoped by user_id"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "factorWeightsUpdate",
        status: "verified",
        evidence: ["admin-token factor update echoes effective weights"],
        rollback: ["restore previous weights"],
        readback: ["factorWeights GET confirms restored weights"],
        permission: ["admin token required"],
        audit: ["safe-write headers include client_request_id"],
      },
    ],
  },
  "FNX-SW-DATABASE-MAINTENANCE": {
    contractId: "FNX-SW-DATABASE-MAINTENANCE",
    status: "partial",
    operations: [
      {
        operation: "databaseCheck",
        status: "verified",
        evidence: ["admin-token database check is read-only"],
        rollback: ["not-applicable for read-only check"],
        readback: ["response includes dialect/database/tables"],
        permission: ["admin token required"],
        audit: ["safe-write headers include client_request_id"],
      },
      {
        operation: "databaseMigrate",
        status: "not-applicable",
        evidence: ["explicitly excluded from frontend-next cutover"],
        rollback: ["requires separate operations runbook and user authorization"],
        readback: ["not run in frontend-next cutover"],
        permission: ["admin token and maintenance window required"],
        audit: ["not run in frontend-next cutover"],
      },
    ],
    notes: "databaseMigrate is excluded; only databaseCheck may be considered ready for cutover.",
  },
} as const satisfies Record<SafeWriteContractId, SafeWriteContractEvidence>;
