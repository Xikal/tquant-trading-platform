# 主力模型生产运行手册

## 当前策略

- P0 已启用：生产只读展示 + Shadow 自动记录。
- P1 未放行：排序加权默认关闭，需 OOS 与 Shadow 双门禁通过。
- P2 未放行：模拟盘只读展示启用，小仓建议默认关闭，且不自动下单。

## 默认配置

```env
MAIN_FORCE_MODEL_ENABLED=true
MAIN_FORCE_MODEL_SHADOW_ENABLED=true
MAIN_FORCE_MODEL_DISPLAY_ENABLED=true
MAIN_FORCE_MODEL_RANKING_ENABLED=false
MAIN_FORCE_MODEL_PAPER_DISPLAY_ENABLED=true
MAIN_FORCE_MODEL_PAPER_SHADOW_ENABLED=true
MAIN_FORCE_MODEL_PAPER_SUGGESTION_ENABLED=false
MAIN_FORCE_MODEL_MAX_RANK_BONUS=4.0
MAIN_FORCE_MODEL_MIN_CONFIDENCE=0.58
MAIN_FORCE_MODEL_MIN_SCORE=55.0
MAIN_FORCE_MODEL_PAPER_MAX_POSITION_PCT=3.0
MAIN_FORCE_MODEL_PAPER_MIN_CONFIDENCE=0.62
MAIN_FORCE_MODEL_SHADOW_SAMPLE_MIN=300
MAIN_FORCE_MODEL_SHADOW_SETTLED_MIN=120
MAIN_FORCE_MODEL_MIN_SUCCESS_RATE_PCT=52.0
MAIN_FORCE_MODEL_MIN_PROFIT_FACTOR=1.35
```

## 验证入口

- Shadow/只读配置：`GET /api/settings/main-force-model`，需要管理员认证。
- 验收报告：`GET /api/backtests/main-force-model/readiness`，需要 research 权限。
- 闭环报告：`GET /api/backtests/strategy-improvement-report`，返回 `main_force_model_shadow`。

## 晋级规则

排序加权必须同时满足：

- `MAIN_FORCE_MODEL_RANKING_ENABLED=true`。
- OOS report `promotion_ready=true`。
- Shadow `record_count >= 300` 且 `settled_count >= 120`。
- Shadow 胜率、PF、fallback rate 达标。
- 候选 strategy 在 allowed strategies 中。
- 候选 data_quality 为 fresh/verified/ok，且无 fallback/risk_flags。

模拟盘小仓建议必须额外满足：

- `MAIN_FORCE_MODEL_PAPER_SUGGESTION_ENABLED=true`。
- 原模拟盘风控已放行。
- 不超过 `MAIN_FORCE_MODEL_PAPER_MAX_POSITION_PCT`。
- `order_intent` 仍为 `manual_import_only`，不创建自动委托。

## 回滚

1. 将 `MAIN_FORCE_MODEL_RANKING_ENABLED=false`。
2. 将 `MAIN_FORCE_MODEL_PAPER_SUGGESTION_ENABLED=false`。
3. 保留 `MAIN_FORCE_MODEL_DISPLAY_ENABLED=true` 可继续只读观察；如需完全隐藏，再设为 false。
4. 重启后端并检查 `/api/settings/main-force-model`。

## 不变量

- 不自动下单。
- 不覆盖硬止损。
- 不绕过现金、仓位、最大持仓数、日亏损暂停。
- 所有 blocked/fallback/data_quality 必须在 advice 或 Shadow payload 中可见。
