# Frontend Next Chunk Profile - 2026-06-08

状态：PASS
生成时间：2026-06-10T14:55:34.525Z

## Summary

| 项 | 值 | 状态 |
|---|---:|---|
| initial JS raw bytes | 261581 | ok |
| initial JS gzip bytes | 80326 | - |
| initial CSS raw bytes | 16899 | - |
| initial CSS gzip bytes | 4401 | - |
| initial ECharts assets | 0 | ok |
| ECharts lazy assets | 0 | - |
| ECharts raw bytes | 0 | lazy |

## Initial Assets

| Asset | type | raw bytes | gzip bytes |
|---|---|---:|---:|
| index-BCr77DpN.js | js | 69076 | 20814 |
| tanstack-misc-2vkUcTec.js | js | 138980 | 39740 |
| solid-vendor-Ch9Uoa8e.js | js | 33188 | 12471 |
| tanstack-router-Br280CGz.js | js | 18005 | 6097 |
| tanstack-query-CBFy7FHV.js | js | 2332 | 1204 |
| index-kWKDR8vD.css | css | 16899 | 4401 |

## ECharts Assets

| Asset | raw bytes | gzip bytes |
|---|---:|---:|
| - | - | - |

## 结论

- 首屏 JS raw 目标：<= 350000 bytes。
- 首屏 ECharts chunk 目标：0。
- ECharts chunk 可以存在，但必须保持 lazy，不得出现在 HTML script/modulepreload 初始资产中。
