# Frontend Next Chunk Profile - 2026-06-08

状态：PASS
生成时间：2026-06-08T13:14:45.195Z

## Summary

| 项 | 值 | 状态 |
|---|---:|---|
| initial JS raw bytes | 284862 | ok |
| initial JS gzip bytes | 86555 | - |
| initial CSS raw bytes | 16758 | - |
| initial CSS gzip bytes | 4336 | - |
| initial ECharts assets | 0 | ok |
| ECharts lazy assets | 0 | - |
| ECharts raw bytes | 0 | lazy |

## Initial Assets

| Asset | type | raw bytes | gzip bytes |
|---|---|---:|---:|
| index-CmrZ_oi2.js | js | 71086 | 21098 |
| tanstack-misc-DpKFfoky.js | js | 160251 | 45683 |
| solid-vendor-Ch9Uoa8e.js | js | 33188 | 12471 |
| tanstack-router-BLsFFlgG.js | js | 18005 | 6099 |
| tanstack-query-xRvKldof.js | js | 2332 | 1204 |
| index-Baaax_FR.css | css | 16758 | 4336 |

## ECharts Assets

| Asset | raw bytes | gzip bytes |
|---|---:|---:|
| - | - | - |

## 结论

- 首屏 JS raw 目标：<= 350000 bytes。
- 首屏 ECharts chunk 目标：0。
- ECharts chunk 可以存在，但必须保持 lazy，不得出现在 HTML script/modulepreload 初始资产中。
