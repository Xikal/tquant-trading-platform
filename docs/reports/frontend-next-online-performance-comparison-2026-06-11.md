# frontend-next 线上性能对比评估（2026-06-11）

## 结论

1. 新前端线上已接管根路径和 `/monitor`：`/` 与 `/monitor` 均返回 `200`，HTML 引用 `/next/assets/...`；旧前端历史 asset `/assets/index-D7MuDqMs.js` 与 `/__legacy/assets/index-D7MuDqMs.js` 均返回 `404`。因此当前不能做“同一线上环境中新旧前端实时 A/B 对比”，只能用线上新前端实测 + 旧前端当前 dist/历史报告基线对照。
2. 新前端 bundle 体积收益明确：当前 `frontend-next/dist` 首屏 JS gzip 为 `80,326 B`，旧 `frontend/dist` 首屏 JS gzip 为 `400,457 B`，下降 `79.9%`；总 JS gzip 从 `706,123 B` 降到 `214,416 B`，下降 `69.6%`。
3. 线上静态资源直连表现稳定：10 次 GET 采样下，HTML p50 `33 ms`，入口 JS p50 `36 ms`，最大 TanStack 分包 p50 `40 ms`，入口 CSS p50 `33 ms`。
4. 未登录状态下，受保护页面都会重定向到登录页；这轮没有自动注册线上 smoke 用户，也没有写生产数据。受保护路由冷启动中位 FCP `3.544 s`、LCP `4.188 s`；同一浏览器上下文暖缓存后中位 FCP `48 ms`、LCP `368 ms`。
5. 当前主要可优化点不是 bundle 体积，而是静态资源缓存头：`/next/assets/*` 已 gzip，但未返回 `Cache-Control`。建议对 hash 资源加 `Cache-Control: public, max-age=31536000, immutable`，HTML 保持短缓存或 no-cache。

## 评估范围

- 生产地址：`http://43.143.243.97:18090`
- 评估时间：2026-06-11
- 浏览器视口：`1440x900`
- 认证状态：未登录；`FRONTEND_NEXT_AUTO_AUTH=0`，不创建线上测试用户
- 线上路径：`/`、`/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking`、`/next/playbook`、`/next/analysis`、`/next/settings`、`/login`
- 原始线上采样文件：`/tmp/gupiao-frontend-online-perf-unauth-2026-06-11.json`

## 新旧前端体积对比

来源：当前仓库 `frontend-next/dist` 与 `frontend/dist`。

| 指标 | 新前端 | 旧前端 | 变化 |
| --- | ---: | ---: | ---: |
| 首屏 JS 文件数 | 5 | 13 | -61.5% |
| 首屏 JS raw | 261,581 B | 1,243,182 B | -79.0% |
| 首屏 JS gzip | 80,326 B | 400,457 B | -79.9% |
| 首屏 CSS gzip | 4,401 B | 12,850 B | -65.8% |
| 总 JS 文件数 | 22 | 55 | -60.0% |
| 总 JS raw | 654,274 B | 2,145,439 B | -69.5% |
| 总 JS gzip | 214,416 B | 706,123 B | -69.6% |
| ECharts gzip | 0 B | 168,998 B | -168,998 B |

旧前端历史报告基线可交叉验证：`docs/reports/frontend-performance-baseline-2026-06-05.md` 记录旧端 first screen JS gzip `319.76 KiB`、total gzip `807.12 KiB`；`docs/reports/legacy-frontend-optimization-acceptance-2026-06-06.md` 记录旧端优化后 first screen JS gzip `318 KiB`、total gzip `819.59 KiB`。按历史 first screen `318 KiB` 对比，新前端当前 `78.4 KiB` 约下降 `75.3%`。

## 线上新前端实测

受保护路由都会进入 `/next/login?redirect=...`，因此下表反映“真实线上新前端静态资源 + 登录重定向路径”，不是已登录业务页渲染性能。

| 范围 | 缓存状态 | 样本数 | elapsed 中位 | FCP 中位 | LCP 中位 | DCL 中位 | Long Tasks |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 受保护路由 | cold | 7 | 5.295 s | 3.544 s | 4.188 s | 3.525 s | 4 |
| 受保护路由 | warm | 7 | 1.497 s | 48 ms | 368 ms | 7 ms | 0 |
| 全部路由含 `/login` | cold | 8 | 5.295 s | 3.544 s | 4.188 s | 3.525 s | 4 |
| 全部路由含 `/login` | warm | 8 | 1.497 s | 48 ms | 360 ms | 6 ms | 0 |

`/login` cold 单次出现 CSS 请求长尾：`/next/assets/index-kWKDR8vD.css` duration `16.031 s`，导致该样本 LCP `18.644 s`。后续 curl 10 次直接采样同一 CSS p50 `33 ms`、p95 `34 ms`，暂按网络/连接长尾处理，建议后续用多轮 Playwright 复测确认。

## 线上静态资源 GET 采样

命令形态：`curl --compressed -D - -o /dev/null` 与 Node HTTP 10 次采样。

| 资源 | 状态 | gzip | Cache-Control | p50 | p95 | max |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| `/` | 200 | 否 | 无 | 33 ms | 61 ms | 61 ms |
| `/next/assets/index-BCr77DpN.js` | 200 | 是 | 无 | 36 ms | 60 ms | 60 ms |
| `/next/assets/tanstack-misc-2vkUcTec.js` | 200 | 是 | 无 | 40 ms | 48 ms | 48 ms |
| `/next/assets/index-kWKDR8vD.css` | 200 | 是 | 无 | 33 ms | 34 ms | 34 ms |

补充：服务对 `HEAD` 返回 `405 Method Not Allowed`，不影响浏览器正常访问，但会限制部分轻量监控探针。

## 和旧前端对比判断

- 体积：新前端明显优于旧端，首屏 JS gzip 下降约 `75%~80%`，总 JS gzip 下降约 `70%`。
- 图表依赖：旧端当前 dist 中 ECharts gzip 约 `169 KB`，新前端当前首屏和总 JS 检测均未发现 ECharts 资源。
- 线上访问：旧前端入口已退役，当前生产无法复测旧端 Web Vitals；旧端页面滚动帧耗时只能引用历史报告，不能作为当前线上状态。
- 缓存：新端 hash 资源缺少长缓存头，这会削弱重复访问和跨会话收益；暖缓存结果已证明缓存命中后渲染路径很轻。

## 建议

1. 为 `/next/assets/*` 增加一年 immutable 缓存；HTML 继续短缓存或 no-cache，避免发版后入口 HTML 粘滞。
2. 提供正式只读验收账号或短期 token，复跑已登录态 `/next/monitor`、`/next/monitor/market`、`/next/strategy-tracking` 的 FCP/LCP、API 数量、DOM 节点、long task。
3. 把 bundle gate 固化到 CI 或发布前检查：首屏 JS gzip `<=100 KB`、总 JS gzip `<=250 KB`、首屏 ECharts `0`、旧端 asset 不再被 HTML 引用。
4. 对 `/login` cold CSS 长尾做多轮复测；若可复现，再查服务端静态文件读取、连接复用和反向代理缓冲。
5. 如需外部用户体感优化，优先补缓存头；当前 bundle 拆分已经不是主要瓶颈。
