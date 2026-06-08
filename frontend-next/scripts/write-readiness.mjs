import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import * as ts from "typescript";

const operationsPath = resolve("src/shared/api/operations.ts");
const contractsPath = resolve("src/shared/api/safeWriteContracts.ts");
const evidencePath = resolve("src/shared/api/safeWriteEvidence.ts");
const rollbackPath = resolve("../docs/reports/frontend-next-write-rollback-smoke-2026-06-05.json");
const jsonReportPath = resolve("../docs/reports/frontend-next-write-readiness-2026-06-07.json");
const markdownReportPath = resolve("../docs/reports/frontend-next-write-readiness-2026-06-07.md");
const strict = process.argv.includes("--strict") || process.argv.includes("--fail-on-blockers");

const operations = readOperations();
const contracts = readSafeWriteContracts();
const contractEvidence = readSafeWriteEvidence();
const rollbackEvidence = readRollbackEvidence();
const writeOperations = new Set(Object.values(contracts).flatMap((contract) => contract.operations));

const contractRows = Object.values(contracts).map((contract) => {
  const operationRows = contract.operations.map((operationName) => {
    const operation = operations[operationName];
    const staticEvidence = contractEvidence[contract.id]?.operations?.[operationName];
    return {
      operation: operationName,
      feature: operation?.feature ?? "unknown",
      method: operation?.method ?? "unknown",
      path: operation?.path ?? "unknown",
      contract_status: operation?.contractStatus ?? "missing_operation",
      requires_admin: operation?.requiresAdmin === true,
      rollback_evidence: rollbackEvidence.operationEvidence[operationName] ?? "missing",
      evidence_status: staticEvidence?.status ?? "missing",
      evidence_notes: staticEvidence?.notes ?? "",
    };
  });
  const missingOperations = operationRows.filter((row) => row.contract_status === "missing_operation").length;
  const blockedOperations = operationRows.filter((row) => row.contract_status !== "ready").length;
  const missingEvidence = operationRows.filter((row) => row.evidence_status !== "verified").length;
  const missingRollbackEvidence = operationRows.filter((row) => row.rollback_evidence === "missing").length;
  const cutoverExcluded = contract.state === "cutover_excluded" || contract.requiredMode === "excluded";
  const productionReadyState = contract.state === "defined_production_ready";
  const liveModeReady = contract.requiredMode === "live";
  return {
    id: contract.id,
    title: contract.title,
    state: contract.state,
    required_mode: contract.requiredMode,
    required_role: contract.requiredRole,
    operation_count: operationRows.length,
    missing_operations: missingOperations,
    non_ready_operations: blockedOperations,
    missing_evidence_operations: missingEvidence,
    missing_rollback_operations: missingRollbackEvidence,
    evidence_status: contractEvidence[contract.id]?.status ?? "missing",
    cutover_excluded: cutoverExcluded,
    evidence_required: contract.evidenceRequired,
    operations: operationRows,
    production_ready:
      !cutoverExcluded &&
      productionReadyState &&
      liveModeReady &&
      missingOperations === 0 &&
      blockedOperations === 0 &&
      missingEvidence === 0 &&
      missingRollbackEvidence === 0,
    blocker_reasons: [
      cutoverExcluded ? "contract is excluded from cutover scope" : null,
      productionReadyState ? null : `contract state is ${contract.state}`,
      liveModeReady ? null : `requiredMode is ${contract.requiredMode}`,
      missingOperations ? `${missingOperations} operations are missing from apiOperations` : null,
      blockedOperations ? `${blockedOperations} operations are not ready` : null,
      missingEvidence ? `${missingEvidence} operations lack verified static evidence` : null,
      missingRollbackEvidence ? `${missingRollbackEvidence} operations lack rollback smoke evidence` : null,
    ].filter(Boolean),
  };
});

const uncoveredWriteOperations = Object.entries(operations)
  .filter(([, operation]) => operation.method !== "GET")
  .filter(([name]) => !writeOperations.has(name))
  .map(([name, operation]) => ({
    operation: name,
    feature: operation.feature,
    method: operation.method,
    path: operation.path,
    contract_status: operation.contractStatus,
    classification: classifyUncoveredWrite(name, operation),
  }));

const blockers = contractRows.filter((contract) => !contract.production_ready && !contract.cutover_excluded);
const report = {
  generated_at: new Date().toISOString(),
  source_files: {
    operations: operationsPath,
    safe_write_contracts: contractsPath,
    safe_write_evidence: evidencePath,
    rollback_smoke: existsSync(rollbackPath) ? rollbackPath : null,
  },
  summary: {
    contract_count: contractRows.length,
    production_ready_contracts: contractRows.filter((contract) => contract.production_ready).length,
    blocked_contracts: blockers.length,
    cutover_excluded_contracts: contractRows.filter((contract) => contract.cutover_excluded).length,
    covered_write_operations: writeOperations.size,
    uncovered_write_operations: uncoveredWriteOperations.length,
    rollback_evidence_status: rollbackEvidence.status,
    cutover_ready:
      blockers.length === 0 &&
      rollbackEvidence.status === "ok" &&
      uncoveredWriteOperations.every((item) => item.classification !== "cutover-write-needs-contract"),
  },
  contracts: contractRows,
  uncovered_write_operations: uncoveredWriteOperations,
  critical_blockers: blockers.map((contract) => ({
    id: contract.id,
    title: contract.title,
    reasons: contract.blocker_reasons,
    operations: contract.operations.map((operation) => ({
      operation: operation.operation,
      status: operation.contract_status,
      rollback_evidence: operation.rollback_evidence,
      evidence_status: operation.evidence_status,
    })),
  })),
  notes: [
    "This report is generated from frontend-next operation registries; it does not upgrade any operation status.",
    "A contract is production-ready only when its state is production-ready, requiredMode is live, all operations are ready, static evidence is verified, and rollback smoke evidence exists.",
    "databaseMigrate remains excluded from cutover by policy; only dry-run/check may be considered after separate operations approval.",
  ],
};

mkdirSync(resolve("../docs/reports"), { recursive: true });
writeFileSync(jsonReportPath, `${JSON.stringify(report, null, 2)}\n`);
writeFileSync(markdownReportPath, renderMarkdown(report));
console.log(JSON.stringify({ ok: report.summary.cutover_ready, reportPath: jsonReportPath, markdownReportPath, summary: report.summary }, null, 2));
if (strict && !report.summary.cutover_ready) process.exit(1);

function readOperations() {
  const source = parseSource(operationsPath);
  const object = findVariableObject(source, "apiOperations");
  const result = {};
  for (const property of object.properties) {
    if (!ts.isPropertyAssignment(property)) continue;
    const name = propertyName(property.name, source);
    if (!ts.isCallExpression(property.initializer)) continue;
    const call = property.initializer.expression.getText(source);
    const args = property.initializer.arguments;
    if (call === "http") {
      const options = parseObject(args[4], source);
      result[name] = {
        feature: literalText(args[0], source),
        method: literalText(args[1], source),
        path: literalText(args[2], source),
        backendOperationId: literalText(args[3], source),
        contractStatus: options.contractStatus ?? "ready",
        requiresAdmin: options.requiresAdmin === true,
      };
    }
    if (call === "shadow") {
      result[name] = {
        feature: literalText(args[0], source),
        method: "POST",
        path: literalText(args[1], source),
        contractStatus: literalText(args[2], source),
        requiresAdmin: false,
      };
    }
  }
  return result;
}

function readSafeWriteContracts() {
  const source = parseSource(contractsPath);
  const object = findVariableObject(source, "safeWriteContracts");
  const result = {};
  for (const property of object.properties) {
    if (!ts.isPropertyAssignment(property) || !ts.isObjectLiteralExpression(property.initializer)) continue;
    const contract = parseObject(property.initializer, source);
    result[contract.id] = {
      id: contract.id,
      title: contract.title,
      state: contract.state,
      operations: contract.operations ?? [],
      requiredRole: contract.requiredRole,
      requiredMode: contract.requiredMode,
      evidenceRequired: contract.evidenceRequired ?? [],
    };
  }
  return result;
}

function readSafeWriteEvidence() {
  const source = parseSource(evidencePath);
  const object = findVariableObject(source, "safeWriteEvidence");
  const result = {};
  for (const property of object.properties) {
    if (!ts.isPropertyAssignment(property) || !ts.isObjectLiteralExpression(property.initializer)) continue;
    const evidence = parseObject(property.initializer, source);
    const operations = {};
    for (const operation of evidence.operations ?? []) {
      if (operation?.operation) operations[operation.operation] = operation;
    }
    result[evidence.contractId] = {
      contractId: evidence.contractId,
      status: evidence.status,
      operations,
      notes: evidence.notes ?? "",
    };
  }
  return result;
}

function parseSource(path) {
  return ts.createSourceFile(path, readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
}

function findVariableObject(source, variableName) {
  let found;
  source.forEachChild((node) => {
    if (!ts.isVariableStatement(node)) return;
    for (const declaration of node.declarationList.declarations) {
      if (declaration.name.getText(source) !== variableName) continue;
      let initializer = declaration.initializer;
      if (initializer && ts.isSatisfiesExpression(initializer)) initializer = initializer.expression;
      if (initializer && ts.isAsExpression(initializer)) initializer = initializer.expression;
      if (initializer && ts.isObjectLiteralExpression(initializer)) found = initializer;
    }
  });
  if (!found) throw new Error(`Unable to find object variable ${variableName}`);
  return found;
}

function parseObject(node, source) {
  if (!node || !ts.isObjectLiteralExpression(node)) return {};
  const result = {};
  for (const property of node.properties) {
    if (!ts.isPropertyAssignment(property)) continue;
    result[propertyName(property.name, source)] = literalValue(property.initializer, source);
  }
  return result;
}

function literalValue(node, source) {
  if (ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return node.text;
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (ts.isArrayLiteralExpression(node)) return node.elements.map((element) => literalValue(element, source));
  if (ts.isObjectLiteralExpression(node)) return parseObject(node, source);
  return node.getText(source);
}

function literalText(node, source) {
  const value = literalValue(node, source);
  return typeof value === "string" ? value : String(value);
}

function propertyName(name, source) {
  if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) return name.text;
  return name.getText(source);
}

function readRollbackEvidence() {
  if (!existsSync(rollbackPath)) return { status: "missing", operationEvidence: {} };
  try {
    const payload = JSON.parse(readFileSync(rollbackPath, "utf8"));
    const operationEvidence = {};
    for (const item of payload.live_results ?? []) {
      if (!item.ok) continue;
      if (item.kind === "auth_mfa") {
        operationEvidence.authTotpSetup = item.coverage;
        operationEvidence.authTotpEnable = item.coverage;
        operationEvidence.authTotpDisable = item.coverage;
      }
      if (item.kind === "watchlist") {
        operationEvidence.watchlistUpsert = item.coverage;
        operationEvidence.watchlistRemove = item.coverage;
      }
      if (item.kind === "paper_order" && item.full_rollback !== "not-run-admin-token-missing") {
        operationEvidence.paperOrderCreate = item.coverage ?? "local-isolated-smoke";
        operationEvidence.paperOrderCancel = item.coverage ?? "local-isolated-smoke";
      }
      if (item.kind === "paper_account") {
        operationEvidence.paperAccountPause = item.coverage;
        operationEvidence.paperAccountResume = item.coverage;
        operationEvidence.paperAccountReconcile = item.coverage;
        operationEvidence.paperPositionsRefresh = item.coverage;
      }
      if (item.kind === "trade_journal") operationEvidence.tradeJournalCreate = item.coverage;
      if (item.kind === "feature_flag" && item.coverage !== "not-run-admin-token-missing") operationEvidence.featureFlagUpdate = item.coverage ?? "local-isolated-smoke";
      if (item.kind === "backtest_run") {
        operationEvidence.backtestRunCreate = item.coverage ?? "local-isolated-smoke";
        operationEvidence.backtestRunCancel = item.coverage ?? "local-isolated-smoke";
      }
      if (item.kind === "backtest_validation") operationEvidence.backtestValidationCreate = item.coverage;
      if (item.kind === "backtest_optimization") operationEvidence.backtestOptimizationCreate = item.coverage;
      if (item.kind === "settings_section") {
        operationEvidence.settingsUpdate = item.coverage;
        operationEvidence.sectorExclusionsUpdate = item.coverage;
        operationEvidence.factorWeightsUpdate = item.coverage;
      }
      if (item.kind === "playbook_lifecycle") {
        operationEvidence.lowBuyLifecycleUpdate = item.coverage;
        operationEvidence.lowBuyStrategyUpdate = item.coverage;
      }
      if (item.kind === "strategy_review") {
        operationEvidence.strategyReviewRecord = item.coverage;
        operationEvidence.strategyTrackingRefresh = item.coverage;
      }
      if (item.kind === "data_task") {
        operationEvidence.dataJobSubmit = item.coverage;
        operationEvidence.dataQualityBackfill = item.coverage;
        operationEvidence.runtimeTaskCreate = item.coverage;
      }
      if (item.kind === "data_repair") operationEvidence.dataQualityRepair = item.coverage;
      if (item.kind === "database_check") operationEvidence.databaseCheck = item.coverage;
    }
    return { status: payload.ok ? "ok" : "not-ok", operationEvidence };
  } catch (error) {
    return { status: `unreadable: ${error instanceof Error ? error.message : String(error)}`, operationEvidence: {} };
  }
}

function classifyUncoveredWrite(name, operation) {
  if (name.startsWith("auth") || operation.feature === "analysis") return "non-persistent-or-auth-flow";
  if (name === "databaseMigrate") return "cutover-excluded-maintenance";
  return "cutover-write-needs-contract";
}

function renderMarkdown(payload) {
  const rows = payload.contracts
    .map((contract) => {
      const status = contract.cutover_excluded ? "excluded" : contract.production_ready ? "ready" : "blocked";
      return `| ${contract.id} | ${contract.state} | ${contract.required_mode} | ${status} | ${contract.blocker_reasons.join("; ") || "-"} |`;
    })
    .join("\n");
  const blockerRows = payload.critical_blockers
    .map((contract) => `| ${contract.id} | ${contract.operations.map((item) => `${item.operation}:${item.status}`).join("<br>")} | ${contract.reasons.join("<br>")} |`)
    .join("\n");
  return `# Frontend Next Write Readiness - 2026-06-07

状态：${payload.summary.cutover_ready ? "ready" : "blocked"}
生成时间：${payload.generated_at}

## Summary

| 项 | 值 |
|---|---:|
| safe write contracts | ${payload.summary.contract_count} |
| production-ready contracts | ${payload.summary.production_ready_contracts} |
| blocked contracts | ${payload.summary.blocked_contracts} |
| cutover-excluded contracts | ${payload.summary.cutover_excluded_contracts} |
| covered write operations | ${payload.summary.covered_write_operations} |
| uncovered write operations | ${payload.summary.uncovered_write_operations} |

## Contract Status

| Contract | State | Required mode | Cutover status | Blocker |
|---|---|---|---|---|
${rows}

## Critical Blockers

| Contract | Operations | Reasons |
|---|---|---|
${blockerRows || "| - | - | - |"}

## Notes

- 本报告只读 frontend-next registry，不会发送写请求。
- 不得只改状态字符串来关闭阻断项；需要 OpenAPI/generated types、idempotency、audit、403、rollback 和读回一致证据。
- databaseMigrate 默认不纳入 cutover，除非用户另行授权运维变更。
`;
}
