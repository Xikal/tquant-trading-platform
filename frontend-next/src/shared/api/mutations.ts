import { requestJson } from "./client";
import { recordTelemetry } from "../telemetry/clientTelemetry";
import {
  getOperation,
  operationCanSendWhenWriteEnabled,
  operationPath,
  type ApiOperationDefinition,
  type ApiOperationName,
  type OperationContractStatus,
  type OperationPathOptions,
  type OperationWriteMode,
} from "./operations";
import {
  safeWriteContractBlockedMessage,
  safeWriteContractSummaryForOperation,
  safeWriteRequestEvidenceForOperation,
  type SafeWriteContractSummary,
} from "./safeWriteContracts";
import type {
  BacktestRunCreate,
  BacktestRunCreateResponse,
  FactorWeightsUpdate,
  FactorWeightsUpdateResponse,
  FeatureFlagUpdateRequest,
  FeatureFlagUpdateResponse,
  PaperOrderCreate,
  PaperOrderResponse,
  SectorExclusionsUpdateResponse,
  SettingsPayload,
  SettingsUpdateResponse,
  TradeJournalEntryCreate,
  TradeJournalEntryResponse,
  UserSectorExclusionsUpdate,
} from "./types";

export type MutationKind =
  | "paper-order"
  | "paper-account"
  | "backtest-run"
  | "backtest-task"
  | "feature-flag"
  | "settings"
  | "watchlist"
  | "playbook"
  | "strategy-review"
  | "trade-journal"
  | "data-job";

export interface MutationResult<T = unknown> {
  mode: "shadow" | "live";
  kind: MutationKind;
  operation: ApiOperationName;
  endpoint: string;
  method: string;
  payload: unknown;
  contractStatus: OperationContractStatus;
  safeWriteContract?: SafeWriteContractSummary;
  writeMode: OperationWriteMode;
  invalidates: readonly string[];
  clientRequestId?: string;
  response?: T;
  message: string;
}

export type Requester = <T>(path: string, init?: RequestInit) => Promise<T>;
export type PermissionResolver = boolean | (() => boolean);

export function frontendNextWriteEnabled(): boolean {
  return import.meta.env.VITE_FRONTEND_NEXT_WRITE_ENABLED === "true";
}

export function frontendNextWriteMode(): OperationWriteMode {
  return (import.meta.env.VITE_FRONTEND_NEXT_WRITE_MODE as OperationWriteMode | undefined) ?? "shadow";
}

export function createMutationClient(options: { writeEnabled?: boolean; writeMode?: OperationWriteMode; requester?: Requester; isAdmin?: PermissionResolver } = {}) {
  const writeEnabled = options.writeEnabled ?? frontendNextWriteEnabled();
  const writeMode = options.writeMode ?? frontendNextWriteMode();
  const requester = options.requester ?? requestJson;
  const isAdmin = options.isAdmin;

  async function mutate<T>(
    kind: MutationKind,
    operation: ApiOperationName,
    payload: unknown,
    init: RequestInit,
    pathOptions: OperationPathOptions = {},
  ): Promise<MutationResult<T>> {
    const definition = getOperation(operation);
    const endpoint = operationPath(operation, pathOptions);
    const method = init.method ?? definition.method;
    const base = {
      kind,
      operation,
      endpoint,
      method,
      payload,
      contractStatus: definition.contractStatus,
      safeWriteContract: safeWriteContractSummaryForOperation(operation),
      writeMode,
      invalidates: definition.invalidates ?? [],
    } satisfies Omit<MutationResult<T>, "mode" | "message" | "response">;
    if (definition.contractStatus === "shadow-only") {
      recordMutationTelemetry(kind, operation, endpoint, method, definition.contractStatus, writeMode, "shadow-only", base.safeWriteContract?.id);
      return {
        ...base,
        mode: "shadow",
        message: safeWriteContractBlockedMessage(operation, definition.contractStatus),
      };
    }
    if (definition.contractStatus === "blocked_contract_needed") {
      recordMutationTelemetry(kind, operation, endpoint, method, definition.contractStatus, writeMode, "blocked_contract_needed", base.safeWriteContract?.id);
      return {
        ...base,
        mode: "shadow",
        message: safeWriteContractBlockedMessage(operation, definition.contractStatus),
      };
    }
    if (!writeEnabled) {
      recordMutationTelemetry(kind, operation, endpoint, method, definition.contractStatus, writeMode, "write-disabled", base.safeWriteContract?.id);
      return {
        ...base,
        mode: "shadow",
        message: "frontend-next write flag is disabled; no backend mutation was sent",
      };
    }
    if (!writeModeAllowsOperation(definition, writeMode) || !operationCanSendWhenWriteEnabled(operation)) {
      recordMutationTelemetry(kind, operation, endpoint, method, definition.contractStatus, writeMode, "mode-blocked", base.safeWriteContract?.id);
      return {
        ...base,
        mode: "shadow",
        message: `frontend-next write mode ${writeMode} does not allow ${definition.contractStatus} backend mutation`,
      };
    }
    if (definition.requiresAdmin && !resolvePermission(isAdmin)) {
      recordMutationTelemetry(kind, operation, endpoint, method, definition.contractStatus, writeMode, "permission-blocked", base.safeWriteContract?.id);
      return {
        ...base,
        mode: "shadow",
        message: "admin permission is required before this mutation can be sent",
      };
    }
    const evidence = safeWriteRequestEvidenceForOperation(operation, writeMode);
    const response = await requester<T>(endpoint, evidence ? withSafeWriteHeaders(init, evidence.headers) : init);
    recordMutationTelemetry(kind, operation, endpoint, method, definition.contractStatus, writeMode, "sent", evidence?.contract.id, evidence?.clientRequestId);
    return {
      ...base,
      mode: "live",
      clientRequestId: evidence?.clientRequestId,
      response,
      message: evidence
        ? `backend mutation sent through frontend-next guarded adapter (${evidence.contract.id})`
        : "backend mutation sent through frontend-next guarded adapter",
    };
  }

  return {
    createPaperOrder: (payload: PaperOrderCreate) =>
      mutate<PaperOrderResponse>("paper-order", "paperOrderCreate", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    pausePaperAccount: (payload: Record<string, unknown> = {}) =>
      mutate("paper-account", "paperAccountPause", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    resumePaperAccount: (payload: Record<string, unknown> = {}) =>
      mutate("paper-account", "paperAccountResume", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    reconcilePaperAccount: (payload: Record<string, unknown>) =>
      mutate("paper-account", "paperAccountReconcile", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    createBacktestRun: (payload: BacktestRunCreate) =>
      mutate<BacktestRunCreateResponse>("backtest-run", "backtestRunCreate", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    cancelBacktestRun: (runId: string | number, payload: Record<string, unknown> = {}) =>
      mutate("backtest-task", "backtestRunCancel", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }, { path: { run_id: runId } }),
    updateFeatureFlag: (key: string, payload: FeatureFlagUpdateRequest) =>
      mutate<FeatureFlagUpdateResponse>("feature-flag", "featureFlagUpdate", payload, {
        method: "PUT",
        body: JSON.stringify(payload),
      }, { path: { key } }),
    updateSettings: (payload: Partial<SettingsPayload>) =>
      mutate<SettingsUpdateResponse>("settings", "settingsUpdate", payload, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    updateSectorExclusions: (payload: UserSectorExclusionsUpdate) =>
      mutate<SectorExclusionsUpdateResponse>("settings", "sectorExclusionsUpdate", payload, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    updateFactorWeights: (payload: FactorWeightsUpdate) =>
      mutate<FactorWeightsUpdateResponse>("settings", "factorWeightsUpdate", payload, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    upsertWatchlistShadow: (payload: Record<string, unknown>) =>
      mutate("watchlist", "watchlistUpsert", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    removeWatchlistShadow: (symbol: string) =>
      mutate("watchlist", "watchlistRemove", { symbol }, {
        method: "DELETE",
      }, { path: { symbol } }),
    updateLowBuyLifecycleShadow: (symbol: string, payload: Record<string, unknown>) =>
      mutate("playbook", "lowBuyLifecycleUpdate", payload, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }, { path: { symbol } }),
    recordStrategyReviewShadow: (payload: Record<string, unknown>) =>
      mutate("strategy-review", "strategyReviewRecord", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    createTradeJournalShadow: (payload: TradeJournalEntryCreate) =>
      mutate<TradeJournalEntryResponse>("trade-journal", "tradeJournalCreate", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    submitDataJobShadow: (payload: Record<string, unknown>) =>
      mutate("data-job", "dataJobSubmit", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    submitDataBackfillShadow: (payload: Record<string, unknown>) =>
      mutate("data-job", "dataQualityBackfill", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    submitDataRepairShadow: (payload: Record<string, unknown>) =>
      mutate("data-job", "dataQualityRepair", payload, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  };
}

function recordMutationTelemetry(
  kind: MutationKind,
  operation: ApiOperationName,
  endpoint: string,
  method: string,
  contractStatus: OperationContractStatus,
  writeMode: OperationWriteMode,
  status: string,
  safeWriteContractId?: string,
  clientRequestId?: string,
) {
  recordTelemetry({
    kind: "mutation",
    name: operation,
    status,
    meta: {
      kind,
      method,
      endpoint: endpoint.split("?")[0],
      contract_status: contractStatus,
      write_mode: writeMode,
      safe_write_contract_id: safeWriteContractId ?? "",
      client_request_id: clientRequestId ?? "",
    },
  });
}

export const mutationClient = createMutationClient();

function writeModeAllowsOperation(definition: ApiOperationDefinition, writeMode: OperationWriteMode): boolean {
  if (writeMode === "shadow") return false;
  if (writeMode === "isolated-live-smoke") return definition.contractStatus === "live-smoke";
  return definition.contractStatus === "ready";
}

function resolvePermission(permission: PermissionResolver | undefined): boolean {
  if (typeof permission === "function") return permission();
  return permission === true;
}

function withSafeWriteHeaders(init: RequestInit, headers: Record<string, string>): RequestInit {
  return {
    ...init,
    headers: {
      ...headersToRecord(init.headers),
      ...headers,
    },
  };
}

function headersToRecord(headers: HeadersInit | undefined): Record<string, string> {
  if (!headers) return {};
  if (headers instanceof Headers) {
    const record: Record<string, string> = {};
    headers.forEach((value, key) => {
      record[key] = value;
    });
    return record;
  }
  if (Array.isArray(headers)) return Object.fromEntries(headers);
  return headers;
}
