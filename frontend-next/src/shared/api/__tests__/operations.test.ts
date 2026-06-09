import { describe, expect, it } from "vitest";
import { apiOperations, featureOperations, getOperation, operationPath } from "../operations";
import { queryKeys } from "../queryKeys";
import { safeWriteContractForOperation, safeWriteContracts, safeWriteRequestEvidenceForOperation } from "../safeWriteContracts";
import type { SafeWriteContractState } from "../safeWriteContracts";

describe("frontend-next API operations", () => {
  it("covers the main feature operation groups", () => {
    expect(featureOperations.auth).toContain("authLogin");
    expect(featureOperations.analysis).toContain("analyzeSymbol");
    expect(featureOperations.playbook).toContain("lowBuyPriorityBoard");
    expect(featureOperations["strategy-tracking"]).toContain("strategyReviewRecord");
    expect(featureOperations.backtest).toContain("backtestRuns");
    expect(featureOperations["data-console"]).toContain("dataJobSubmit");
    expect(featureOperations.settings).toContain("featureFlagUpdate");
  });

  it("builds path and query strings from operation names", () => {
    expect(operationPath("featureFlagUpdate", { path: { key: "frontend solid" } })).toBe(
      "/api/settings/feature-flags/frontend%20solid",
    );
    expect(operationPath("monitorWorkspace", { query: { view: "action", priority_limit: 12, empty: "" } })).toBe(
      "/api/bff/v1/workspace/monitor?view=action&priority_limit=12",
    );
    expect(operationPath("lowBuyQuotes", { query: { symbols: ["000001", "510300"] } })).toBe(
      "/api/screeners/low-buy/quotes?symbols=000001%2C510300",
    );
  });

  it("marks production-ready and still-blocked write contracts explicitly", () => {
    expect(getOperation("watchlistUpsert").contractStatus).toBe("ready");
    expect(getOperation("backtestRunCreate").contractStatus).toBe("blocked_contract_needed");
    expect(getOperation("backtestRunCancel").contractStatus).toBe("blocked_contract_needed");
    expect(getOperation("backtestValidationCreate").contractStatus).toBe("blocked_contract_needed");
    expect(getOperation("backtestOptimizationCreate").contractStatus).toBe("blocked_contract_needed");
    expect(getOperation("featureFlagUpdate").contractStatus).toBe("ready");
    expect(getOperation("settingsUpdate").contractStatus).toBe("ready");
    expect(getOperation("strategyReviewRecord").contractStatus).toBe("ready");
    expect(getOperation("dataQualityRepair").contractStatus).toBe("ready");
    expect(getOperation("databaseMigrate").contractStatus).toBe("blocked_contract_needed");
  });

  it("keeps query keys tied to operation names", () => {
    expect(queryKeys.strategyTrackingDetail("abc")).toEqual([
      "frontend-next",
      "operation",
      "strategyTrackingDetail",
      { path: { item_id: "abc" } },
    ]);
  });

  it("does not leave operation definitions without a status", () => {
    expect(Object.values(apiOperations).every((operation) => operation.contractStatus)).toBe(true);
  });

  it("does not expose removed backtest task writes through safe write contracts", () => {
    expect(safeWriteContractForOperation("backtestRunCreate")).toBeUndefined();
    expect(safeWriteContractForOperation("backtestRunCancel")).toBeUndefined();
    expect(safeWriteContractForOperation("backtestValidationCreate")).toBeUndefined();
    expect(safeWriteContractForOperation("backtestOptimizationCreate")).toBeUndefined();
  });

  it("maps every active guarded non-ready write operation to a safe write contract", () => {
    const cutoverExcludedWrites = new Set([
      "backtestRunCreate",
      "backtestRunCancel",
      "backtestValidationCreate",
      "backtestOptimizationCreate",
    ]);
    const missing = Object.entries(apiOperations)
      .filter(([, operation]) => operation.method !== "GET" && operation.contractStatus !== "ready")
      .filter(([name]) => !cutoverExcludedWrites.has(name))
      .filter(([name]) => !safeWriteContractForOperation(name as keyof typeof apiOperations))
      .map(([name]) => name);

    expect(missing).toEqual([]);
  });

  it("builds audit headers for guarded live write requests", () => {
    const evidence = safeWriteRequestEvidenceForOperation(
      "featureFlagUpdate",
      "live",
      "fnx-featureFlagUpdate-test",
    );

    expect(evidence?.clientRequestId).toBe("fnx-featureFlagUpdate-test");
    expect(evidence?.contract.id).toBe("FNX-SW-FEATURE-FLAG");
    expect(evidence?.headers).toEqual({
      "X-Frontend-Next-Client-Request-Id": "fnx-featureFlagUpdate-test",
      "X-Frontend-Next-Contract-Id": "FNX-SW-FEATURE-FLAG",
      "X-Frontend-Next-Contract-State": "defined_production_ready",
      "X-Frontend-Next-Operation": "featureFlagUpdate",
      "X-Frontend-Next-Source": "frontend-next",
      "X-Frontend-Next-Write-Mode": "live",
    });
  });

  it("keeps cutover write contracts evidence-rich before any operation can be promoted", () => {
    const missingEvidence = Object.values(safeWriteContracts)
      .filter((contract) => contract.id !== "FNX-SW-DATABASE-MAINTENANCE")
      .filter(
        (contract) =>
          empty(contract.requestContract) ||
          empty(contract.responseContract) ||
          empty(contract.rollbackContract) ||
          empty(contract.auditContract) ||
          !contract.requestContract.some((item) => item.includes("client_request_id")) ||
          !contract.evidenceRequired.some((item) => /403|rollback|restore|trace|audit|echo/i.test(item)),
      )
      .map((contract) => contract.id);

    expect(missingEvidence).toEqual([]);
  });

  it("keeps production-ready contracts explicit and database maintenance excluded", () => {
    const contracts = Object.values(safeWriteContracts).map((contract) => ({
      id: contract.id,
      state: contract.state as SafeWriteContractState,
      requiredMode: contract.requiredMode as string,
    }));
    const productionReady = contracts.filter((contract) => contract.state === "defined_production_ready" && contract.requiredMode === "live");
    const blockers = contracts.filter((contract) => contract.state === "defined_backend_needed");

    expect(productionReady.map((contract) => contract.id)).toEqual([
      "FNX-SW-AUTH-MFA",
      "FNX-SW-WATCHLIST",
      "FNX-SW-PLAYBOOK-LIFECYCLE",
      "FNX-SW-STRATEGY-REVIEW",
      "FNX-SW-TRADE-JOURNAL",
      "FNX-SW-DATA-TASK",
      "FNX-SW-DATA-REPAIR",
      "FNX-SW-SETTINGS-SECTION",
      "FNX-SW-FEATURE-FLAG",
    ]);
    expect(blockers.map((contract) => contract.id)).toEqual([]);
    expect(safeWriteContracts["FNX-SW-DATABASE-MAINTENANCE"].state).toBe("cutover_excluded");
    expect(getOperation("featureFlagUpdate").contractStatus).toBe("ready");
    expect(getOperation("databaseMigrate").contractStatus).toBe("blocked_contract_needed");
  });
});

function empty(values: readonly unknown[]): boolean {
  return Array.from(values).length === 0;
}
