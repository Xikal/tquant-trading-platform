你在 /Users/j/Documents/gupiao 工作。目标：按 docs/frontend-next-platform-resource-optimization-requirements-2026-06-08.md 和 docs/frontend-next-platform-resource-optimization-development-doc-2026-06-08.md 落地 frontend-next 与平台资源优化；不加机器、不替换 MySQL、不自动 cutover。开始前执行：cd /Users/j/Documents/gupiao && git status --short。

必须阅读：AGENTS.md、docs/engineering-conventions.md、docs/platform-modular-architecture-uplift-execution-plan-2026-06-04.md、docs/frontend-next-platform-resource-optimization-requirements-2026-06-08.md、docs/frontend-next-platform-resource-optimization-development-doc-2026-06-08.md、docs/reports/frontend-next-optimization-plan-2026-06-07.md、docs/frontend-next-cutover-runbook-2026-06-05.md、frontend-next/package.json、scripts/deploy_cloud_server.sh、scripts/quick_cloud_deploy.sh、backend/app/core/config.py、backend/app/core/database.py、backend/app/services/analytics/*、backend/app/services/tasks/*。

硬边界：不改 strategy_policy.py；不改变生产策略语义、生产排序、production_score、priority_board；旧 frontend/ 不作为本轮改造对象；frontend-next 不换栈；K 线必须 Lightweight Charts；ECharts 只低频 lazy；Worker/WASM 只做显示层计算；DuckDB/Parquet 只做分析层，不做生产事实源；Web 主进程不得新增重任务；禁止直接删除 MySQL .ibd/binlog/Docker volumes；CSS 优化不得改变当前视觉；不部署、不切流，除非用户单独授权。

多 Agent 并行：A 前端性能做 strategy-tracking BFF 合包、paper 虚拟化、ECharts lazy、首屏 chunk；B CSS/UI 做 unused report、样式合并、!important 收敛、视觉一致性；C 平台资源做资源巡检、Docker/journal/build cache/deploy backup 上限；D MySQL 运维做 binlog 固化、slow log logrotate、备份/恢复 runbook、连接池预算；E 数据分层做 Parquet 导出、manifest、DuckDB 查询、热库保留窗口；F Worker 降载做并发、低优先级窗口、资源预算、健康检查；G QA/报告做测试、性能、资源验收、open-items。

执行顺序：
1. 采集 baseline：frontend-next build/perf/css/request/visual；云端只读 df/free/docker/journal/mysql/du；生成 docs/reports/platform-resource-baseline-2026-06-08.md。
2. Phase A：新增资源巡检脚本与测试；固化 binlog 3 天；新增 slow log logrotate；Docker log max-size=50m/max-file=3；journal 300M/7day；BuildKit cache 2G；部署脚本新增资源 gate，blocking 停止。
3. Phase B：/next/strategy-tracking 优先走 /api/bff/v1/workspace/strategy，请求 <=2 且 items 422=0；/next/paper 长列表接 shared VirtualList，DOM <150，机甲组件不改；CSS 先报告再无损合并，raw <=180KB 或说明原因，!important <=25；ECharts 首屏 0；shared/ui 去重。
4. Phase C：按 Web/runtime/scheduler/backtest/analytics 分角色收敛连接池和 worker 并发；重任务低优先级，开盘高峰/部署/cutover 验证降并发；Web 不跑重任务。
5. Phase D：daily_bar_snapshots、strategy_tracking_snapshots 等导出 Parquet，manifest 记录源表/日期/行数/hash/路径/质量；DuckDB 查询可复现；未校验前不清 MySQL 源数据。
6. Phase E/F：预构建镜像优先，云端 pull+restart；部署前资源 gate；补功能级 E2E/错误态/rollback；更新 reports、runbook、cutover runbook。

验收命令：frontend-next 下跑 npm run api:check && npm run typecheck && npm run lint && npm test -- --run && npm run build && npm run e2e && npm run request:trace && npm run screenshot:parity && npm run visual:consistency && npm run perf:compare && npm run css:budget && npm run css:unused-report。仓库根跑 backend 相关 pytest、python scripts/verify_go_rust_performance_acceptance.py、git diff --check、git status --short。资源验收需列 df/free/docker/mysql/binlog/slow log 结果。

最终报告必须写：新增/修改文件、Phase 完成度、before/after 指标、资源状态、MySQL 日志/备份状态、Worker 降载结果、Parquet manifest 状态、测试结果、旧 frontend 是否未改、后端改动原因、是否影响平台功能、回滚方式、未完成项、cutover 是否仍需用户单独授权。
