# TanStack Chunk 评估报告（2026-06-10）

状态：不拆  
范围：`frontend-next` 构建产物与 `chunk:profile`  
结论时间：2026-06-10

## 结论

本轮不继续拆分 TanStack chunk。

依据：

1. `npm run build && npm run chunk:profile` 通过。
2. `chunk:profile` 输出 `ok=true`，首屏 JS raw `261581` bytes、gzip `80326` bytes。
3. 首屏 ECharts 资产为 `0`，低频大依赖未进入首屏。
4. 当前 `tanstack-misc` 构建产物 gzip 约 `40.12KB`，总预算状态为 `ok`；继续拆分的工程复杂度高于可见收益。

## 本轮不做

1. 不增加新的 lazy 边界。
2. 不拆 `@tanstack/solid-router`、`@tanstack/solid-query` 或 `tanstack-misc`。
3. 不调整页面加载语义和路由入口。

## 后续触发条件

只有出现以下任一情况，才重新评估拆分：

1. `chunk:profile` 首屏 JS gzip 超过预算。
2. TanStack 相关 chunk 明确进入非使用页面首屏并造成可测延迟。
3. Playwright 或线上性能报告显示首屏交互延迟主要由该 chunk 导致。
