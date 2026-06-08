# Frontend Next CSS Optimization - 2026-06-07

状态：预算报告已生成；未执行破坏性删除。
生成时间：2026-06-08T03:33:24.322Z

## Budget Summary

| 项 | 值 | 状态 |
|---|---:|---|
| source CSS files | 29 | - |
| source CSS bytes | 299197 | needs-explanation |
| source CSS gzip bytes | 59727 | - |
| source CSS lines | 15682 | - |
| dist CSS files | 11 | built |
| dist CSS bytes | 240556 | - |
| dist CSS gzip bytes | 48132 | ok |
| !important count | 23 | ok |

## Largest Source CSS

| File | bytes | lines | !important |
|---|---:|---:|---:|
| src/features/backtest/backtest-slice.css | 24016 | 1343 | 0 |
| src/features/settings/settings-slice.css | 23791 | 1158 | 0 |
| src/features/paper/paper-page.css | 22995 | 1177 | 0 |
| src/features/strategy-tracking/strategy-tracking.css | 22694 | 1235 | 0 |
| src/features/monitor-action/monitor-action.css | 19121 | 1095 | 0 |
| src/features/monitor-market/monitor-market.css | 18282 | 949 | 0 |
| src/features/data-console/data-console-slice.css | 17805 | 968 | 0 |
| src/features/auth/LoginPage.css | 17343 | 880 | 4 |
| src/shared/styles/legacy-solid-adapter.css | 14691 | 809 | 5 |
| src/features/playbook/playbookSlice.css | 13383 | 769 | 0 |
| src/shared/styles/legacy-workspace/workspace-strategy-tracking.css | 12516 | 656 | 6 |
| src/shared/styles/legacy-workspace/workspace-paper-mecha.css | 11325 | 460 | 2 |
| src/shared/styles/legacy-workspace/workspace-login-scene.css | 10543 | 487 | 0 |
| src/shared/styles/legacy-workspace/workspace.css | 10388 | 563 | 3 |
| src/shared/styles/legacy-workspace/workspace-paper.css | 9600 | 500 | 2 |

## Largest Dist CSS

| File | bytes | gzip bytes |
|---|---:|---:|
| dist/assets/index-D1m2N8l9.css | 88546 | 17028 |
| dist/assets/SettingsPage-BEGsxa-y.css | 19996 | 3582 |
| dist/assets/BacktestPage-Bh0PnbqD.css | 19559 | 3766 |
| dist/assets/StrategyTrackingPage-BfcLV-3B.css | 18759 | 3605 |
| dist/assets/PaperPage-RihhV-yi.css | 18439 | 3741 |
| dist/assets/MonitorActionPage-CrG0_n4h.css | 15290 | 3331 |
| dist/assets/MonitorMarketPage-DxnU4VuE.css | 14757 | 2806 |
| dist/assets/LoginPage-qTpIqddy.css | 13823 | 3408 |
| dist/assets/DataConsolePage-CTQzT0Dp.css | 13769 | 2856 |
| dist/assets/PlaybookPage-mnH0OPyl.css | 10696 | 2282 |

## !important Hotspots

| File | !important | bytes |
|---|---:|---:|
| src/shared/styles/legacy-workspace/workspace-strategy-tracking.css | 6 | 12516 |
| src/shared/styles/legacy-solid-adapter.css | 5 | 14691 |
| src/features/auth/LoginPage.css | 4 | 17343 |
| src/shared/styles/legacy-workspace/workspace.css | 3 | 10388 |
| src/shared/styles/legacy-workspace/workspace-paper-mecha.css | 2 | 11325 |
| src/shared/styles/legacy-workspace/workspace-paper.css | 2 | 9600 |
| src/shared/styles/legacy-workspace/workspace-primitives-base.css | 1 | 6522 |

## Lossless Optimization Rule

- 本报告只做体积和债务统计，不删除 CSS。
- 禁止 PurgeCSS 批量删除；未引用选择器只能先进入候选报告。
- 任何 CSS 修改后必须运行截图/视觉一致性检查。
