# Frontend Next Chunk Profile - 2026-06-08

状态：PASS
生成时间：2026-06-07T19:10:08.097Z

## Summary

| 项 | 值 | 状态 |
|---|---:|---|
| initial JS raw bytes | 282841 | ok |
| initial JS gzip bytes | 85336 | - |
| initial CSS raw bytes | 88546 | - |
| initial CSS gzip bytes | 17028 | - |
| initial ECharts assets | 0 | ok |
| ECharts lazy assets | 3 | - |
| ECharts raw bytes | 457660 | lazy |

## Initial Assets

| Asset | type | raw bytes | gzip bytes |
|---|---|---:|---:|
| index-eR4fswIZ.js | js | 68594 | 20662 |
| solid-vendor-Ch9Uoa8e.js | js | 33188 | 12471 |
| tanstack-B8c36lUu.js | js | 181059 | 52203 |
| index-D1m2N8l9.css | css | 88546 | 17028 |

## ECharts Assets

| Asset | raw bytes | gzip bytes |
|---|---:|---:|
| echarts-charts-BhDYVetR.js | 284021 | 94407 |
| echarts-components-DE1kHsW9.js | 160792 | 53304 |
| echarts-renderers-BmNxWEn8.js | 12847 | 4576 |

## 结论

- 首屏 JS raw 目标：<= 350000 bytes。
- 首屏 ECharts chunk 目标：0。
- ECharts chunk 可以存在，但必须保持 lazy，不得出现在 HTML script/modulepreload 初始资产中。
