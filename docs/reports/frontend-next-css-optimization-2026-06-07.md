# Frontend Next CSS Optimization - 2026-06-07

状态：预算报告已生成；未执行破坏性删除。
生成时间：2026-06-08T23:50:24.521Z

## Budget Summary

| 项 | 值 | 状态 |
|---|---:|---|
| source CSS files | 29 | - |
| source CSS bytes | 306206 | needs-explanation |
| source CSS gzip bytes | 60728 | - |
| source CSS lines | 16073 | - |
| dist CSS files | 11 | built |
| dist CSS bytes | 181080 | - |
| dist CSS gzip bytes | 37708 | ok |
| !important count | 25 | ok |

## Largest Source CSS

| File | bytes | lines | !important |
|---|---:|---:|---:|
| src/features/backtest/backtest-slice.css | 24942 | 1406 | 0 |
| src/features/paper/paper-page.css | 24165 | 1231 | 2 |
| src/features/settings/settings-slice.css | 23791 | 1158 | 0 |
| src/features/strategy-tracking/strategy-tracking.css | 22694 | 1235 | 0 |
| src/features/monitor-action/monitor-action.css | 20592 | 1183 | 0 |
| src/features/data-console/data-console-slice.css | 18301 | 998 | 0 |
| src/features/monitor-market/monitor-market.css | 18282 | 949 | 0 |
| src/shared/styles/legacy-solid-adapter.css | 17641 | 969 | 5 |
| src/features/auth/LoginPage.css | 17343 | 880 | 4 |
| src/features/playbook/playbookSlice.css | 13383 | 769 | 0 |
| src/shared/styles/legacy-workspace/workspace-strategy-tracking.css | 12516 | 656 | 6 |
| src/shared/styles/legacy-workspace/workspace-paper-mecha.css | 11325 | 460 | 2 |
| src/shared/styles/legacy-workspace/workspace-login-scene.css | 10542 | 486 | 0 |
| src/shared/styles/legacy-workspace/workspace.css | 10388 | 563 | 3 |
| src/shared/styles/legacy-workspace/workspace-paper.css | 9600 | 500 | 2 |

## Largest Dist CSS

| File | bytes | gzip bytes |
|---|---:|---:|
| dist/assets/PaperPage-BjViCAjj.css | 28456 | 5606 |
| dist/assets/BacktestPage-WrHtBwat.css | 20288 | 3952 |
| dist/assets/SettingsPage-BEGsxa-y.css | 19996 | 3582 |
| dist/assets/StrategyTrackingPage-BfcLV-3B.css | 18759 | 3605 |
| dist/assets/index-Baaax_FR.css | 16758 | 4336 |
| dist/assets/MonitorActionPage-CSDf4FPa.css | 16483 | 3506 |
| dist/assets/MonitorMarketPage-DxnU4VuE.css | 14757 | 2806 |
| dist/assets/DataConsolePage-BL845ZW3.css | 14142 | 2898 |
| dist/assets/LoginPage-qTpIqddy.css | 13823 | 3408 |
| dist/assets/PlaybookPage-mnH0OPyl.css | 10696 | 2282 |

## !important Hotspots

| File | !important | bytes |
|---|---:|---:|
| src/shared/styles/legacy-workspace/workspace-strategy-tracking.css | 6 | 12516 |
| src/shared/styles/legacy-solid-adapter.css | 5 | 17641 |
| src/features/auth/LoginPage.css | 4 | 17343 |
| src/shared/styles/legacy-workspace/workspace.css | 3 | 10388 |
| src/features/paper/paper-page.css | 2 | 24165 |
| src/shared/styles/legacy-workspace/workspace-paper-mecha.css | 2 | 11325 |
| src/shared/styles/legacy-workspace/workspace-paper.css | 2 | 9600 |
| src/shared/styles/legacy-workspace/workspace-primitives-base.css | 1 | 6521 |

## Lossless Optimization Rule

- 本报告只做体积和债务统计，不删除 CSS。
- 禁止 PurgeCSS 批量删除；未引用选择器只能先进入候选报告。
- 任何 CSS 修改后必须运行截图/视觉一致性检查。
