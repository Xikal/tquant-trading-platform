---
name: tquant-daily-research-workflow
description: Run the Hermes tquant_daily_research workflow from Feishu commands and return a concise Markdown report.
---

# TQuant Hermes Daily Research Workflow

Use this skill when a Feishu user asks for `研究`, `研报`, `今日研报`, or `tquant_daily_research`.

## Workflow

- Workflow name: `tquant_daily_research`
- Orchestration contract: `docs/hermes_orchestration.yaml`
- Role prompts: `docs/agent-role-prompts.md`
- Input symbols: optional, maximum 10. If omitted, use priority board TOP 10.

## Required Phases

1. `parallel_analysis`
   - `market_state_analyst`
   - `sector_heat_analyst`
   - `technical_analyst`
2. `cross_validation`
   - `strategy_validator`
3. `decision`
   - `portfolio_manager`

## Required Output

Return a JSON object with:

```json
{
  "ok": true,
  "workflow_name": "tquant_daily_research",
  "phase_results": [],
  "final_markdown": "",
  "errors": []
}
```

The `final_markdown` must include these sections:

- 市场概览
- 板块主线
- 持仓做T信号
- 选股宝典 TOP 10
- 风控检查
- 操作检查清单

## Safety

- Only call TQuant Agent Safe API / MCP tools.
- Do not access database directly.
- Do not execute shell.
- Do not modify strategy parameters.
- Do not create real orders.
- `recommend_orders` may be called only as a read-through recommendation if policy allows; otherwise record permission denied.
- Output is an auxiliary research report, not a trading promise.

## Feishu Command Contract

- `研究`: start workflow with priority board TOP 10.
- `研究 510300,300059`: start workflow with specified symbols.
- `研究状态`: show latest workflow status.
- `研究报告`: show latest workflow report.
