import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const defaultStoresRoot = new URL("../src/stores", import.meta.url).pathname;
const storesRoot = resolve(readArg("--stores-root") ?? defaultStoresRoot);

const serverFieldPatterns = [
  /^(account|adminMetrics|adminTasks|anomaly|attribution|autoTradingRuns|batchResults|blackLitterman|bootstrap|capacity|correlation|currentUser|dataQuality|detail|equity|factorWeights|factors|featureFlagAudits|featureFlags|healthItems|home|hypothesisItems|instrumentSyncStatus|keyLevelAlerts|latest|marketBreadth|marketPulse|markowitz|monthlyReturns|operationAudits|optimizations|pairedHedge|payload|playbook|playbookCache|policy|priorityActionItem|priorityBoard|repairDraft|result|researchResult|reviewReports|reviewStatus|runtime|sectorEtfT0|sectorEtfT0Performance|sectorExclusions|sectorRelativeStrength|selectedOptimization|selectedRun|selectedValidation|settings|strategyGovernance|strategyMeta|trades|validation|validations|watchlist|watchlistSignals)$/i,
  /(Response|Result|Snapshot|Payload|Board|Trade|Position|Order|Metric|Report|Audit|Runtime|Governance|Performance|Capacity|Validation|Optimization|Attribution|Correlation|Universe|Watchlist|Instrument|Holding|Account|User|Signal|Quote|Event|Factor|StrategyMeta)\b/,
];

const allowedFieldPatterns = [
  /^(active|activeTab|activeFamilyDetailKey|activeStrategyLane|aiDialogOpen|aiOpen|authDraft|authReady|availableSectors|boardFilter|commandOpen|commandQuery|compareRunIds|compareSortKey|confirmHighRisk|description|draft|draftOverrides|editingWatchSymbol|error|expanded|expandedKeys|filter|form|formError|holdingEditor|hypothesisError|hypothesisLoading|hypothesisTopic|loading|message|mode|name|notice|offline|open|page|pageSize|pulseTime|quantity|range|repairCategory|repairName|repairSymbol|rollbackVersion|savedSection|sectorDraft|sectorQuery|selectedDatasetKey|selectedItemId|selectedKey|selectedOptimizationId|selectedStock|selectedValidationId|signalState|signalToastVisible|sort|stopped|strategy|strategyFamily|strategyFilter|strategyKey|strategyVariant|tab|tabLoading|topbarPulse|useLlm|userStatus|version|viewMode)$/i,
  /(Draft|Loading|Error|Notice|Message|Open|Tab|Mode|Filter|Query|Selected|Selection|Expanded|Sort|Page|Lane|Key|Id|Text|Status|Saving|Visible|Pulse|Version)$/i,
];

const violations = [];

for (const file of walk(storesRoot)) {
  if (!file.endsWith(".ts")) continue;
  const text = readFileSync(file, "utf8");
  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    const field = fieldName(line);
    if (!field || field.startsWith("set") || allowedFieldPatterns.some((pattern) => pattern.test(field))) {
      return;
    }
    if (isPrimitiveUiField(line)) {
      return;
    }
    if (serverFieldPatterns.some((pattern) => pattern.test(line) || pattern.test(field))) {
      violations.push(`${relative(storesRoot, file)}:${index + 1} server state field '${field}': ${line.trim()}`);
    }
  });
}

if (violations.length) {
  console.error("State separation guard failed. Move server state to TanStack Query and keep Zustand stores UI-only.");
  console.error(violations.join("\n"));
  process.exit(1);
}

console.log("State separation guard passed.");

function readArg(name) {
  const index = process.argv.indexOf(name);
  if (index === -1) return null;
  return process.argv[index + 1] ?? null;
}

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

function fieldName(line) {
  const match = line.match(/^\s*([A-Za-z_$][\w$]*)\??\s*:/);
  return match?.[1] ?? null;
}

function isPrimitiveUiField(line) {
  const trimmed = line.trim();
  return (
    /:\s*(string|number|boolean)\s*;?$/.test(trimmed) ||
    /:\s*["'`][^"'`]*["'`]\s*,?$/.test(trimmed) ||
    /:\s*(true|false|null|\d+(?:\.\d+)?)\s*,?$/.test(trimmed) ||
    /:\s*String\([^)]*\)\s*,?$/.test(trimmed)
  );
}
