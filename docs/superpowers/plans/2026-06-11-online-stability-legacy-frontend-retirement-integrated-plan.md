# 线上稳定性与旧前端退役融合开发计划（2026-06-11）

状态：待实施  
性质：开发计划与执行提示词，不代表已部署、不代表已切流  
适用项目：`/Users/j/Documents/gupiao`

## 1. 背景与事实基线

本计划融合三条线：

1. 线上服务状态审计发现的稳定性问题：MySQL cgroup OOM、runtime-worker 内存贴边、域名外部 reset、低吸物化失败、provider/BFF 超时。
2. 模拟盘当前状态修正：active 模拟盘入口已下线，不能再按“新增模拟盘暂停开关”处理；真正需要处理的是已移除功能的历史任务残留。
3. 旧前端退役未完成项：运行链路已切到 `frontend-next/`，但旧 `frontend/` 源码未物理删除，仍需完成归档/删除前置门槛。

关键证据：

- `docs/reports/online-service-status-audit-2026-06-11.md`：记录 MySQL OOM、worker 重启、域名 reset、低吸物化失败和 provider/BFF timeout。
- `docs/reports/legacy-frontend-retirement-execution-2026-06-10.md`：旧 `frontend/` 已从运行入口、镜像构建、分离 nginx、部署 scope 和 CI artifact 链路退役。
- `docs/reports/legacy-frontend-retirement-decision-2026-06-11.md`：旧 `frontend/` 可标记为 `retired-source / archive_candidate`，但本轮不得物理删除。
- `frontend-next/src/app/routeTree.tsx`：`/next/paper` 跳转到 `/next/monitor`。
- `frontend/src/app/router/webRouteDefinitions.tsx`：旧 `/paper` 跳转到 `/monitor`。
- `backend/app/workers/runtime_worker.py`：`paper_*` 或 paper task 当前会报 `paper trading feature has been removed`。
- `backend/app/services/ml_signal/schedule_info.py` 和 `backend/app/runtime/strategy_evolution_scheduler.py`：模拟盘相关自动训练/自进化任务已停用或跳过。

## 2. 总目标

在不影响核心行情、低吸榜、推荐榜、priority board、watchdog、生产策略语义的前提下，完成：

1. 线上稳定性整改开发方案落地。
2. 已移除模拟盘功能的残留任务安全收口。
3. 旧前端退役未完成项的归档/删除前置准备。
4. 前端入口、部署脚本、CI、文档和线上观测口径一致。

## 3. 硬边界

本开发计划默认只做本地代码、测试、文档和只读核查。以下动作必须单独获得用户授权：

- 线上部署、切流、容器重启/重建。
- `docker restart/down/up/stop/start`、Docker prune、磁盘清理。
- `systemctl restart`、nginx 配置修改或 reload。
- 修改线上 `.env`、compose、生效配置。
- 数据库写操作、生产任务批量重跑、队列清理。
- 物理删除 `frontend/` 源码目录。

策略硬边界：

- 不改 `strategy_policy.py`。
- 不改变 `production_score`。
- 不改变 priority board 排序和口径。
- 不停核心行情刷新、日线刷新、低吸榜/推荐榜刷新、priority board 物化、watchdog、数据新鲜度检查。
- 不把 research/shadow/paper 历史口径绕过门控接入生产排序。

## 4. 范围调整：模拟盘不是暂停对象

前一版“新增 `PAPER_RUNTIME_TASKS_ENABLED` 暂停开关”的方向应废弃。

当前正确口径：

| 项 | 当前事实 | 本计划处理 |
|---|---|---|
| `/next/paper` | 已跳转 `/next/monitor` | 不恢复入口 |
| 旧 `/paper` | 已跳转 `/monitor` | 不恢复入口 |
| paper 后端模型/表 | 仍保留 | 作为历史数据、回测费用/成交语义复用，不删除 |
| paper runtime task | 已移除功能仍可能有历史残留 | 改为安全 skipped，不计失败、不重试 |
| paper 自动训练/自进化 | 已停用或跳过 | 保持停用 |

## 5. 分阶段计划

### G0：只读复核与任务分级

目标：确认部署后最新状态，并避免误把旧问题当新需求。

只读检查：

```bash
cd /Users/j/Documents/gupiao
git status --short
rg -n "paper|模拟盘|frontend/dist|frontend-legacy|frontend-hot|__legacy|low_buy_materialization|priority_board|runtime_worker|RuntimeTask" \
  backend frontend frontend-next deploy scripts docs .github Makefile
```

线上只读复核仅在授权连接信息可用时执行，不做写操作：

```bash
ssh -i /Users/j/Downloads/gupiao.pem ubuntu@43.143.243.97 '
cd /home/ubuntu/gupiao-upload
sudo docker compose -f docker-compose.mysql.yml ps
sudo docker stats --no-stream
curl -fsS http://127.0.0.1:18090/readyz
free -m
'
```

产出：

- 当前任务清单：核心任务、已移除任务、研究/低优先级任务。
- 当前旧前端引用清单：运行依赖、历史引用、native/mobile 引用、可删除候选。
- 不执行任何线上写操作。

### G1：已移除 paper 任务残留安全收口

目标：已移除功能的历史任务不再污染 failed 统计、不再 retry storm、不再占用 worker。

开发项：

1. 增加明确的 removed-feature task 分类，例如：
   - `paper_review_report`
   - `paper_portfolio_execution_preview`
   - `paper_ledger_reconcile_preview`
   - 所有 `paper_` 前缀 runtime task
2. 在 runtime worker 执行前识别 removed-feature task。
3. 为 `RuntimeTaskQueue` 增加终态 `skipped` 或等价 `mark_skipped()`：
   - `status="skipped"`。
   - `result.reason="removed_feature"`。
   - `result.feature="paper_trading"`。
   - 清空 `active_idempotency_key`。
   - 不进入 `failed`。
   - 不再 retry。
4. `TERMINAL_STATUSES` 增加 `skipped`。
5. runtime task summary 增加 skipped 计数展示；若已有 status_counts 可自然展示，也要补测试锁住。
6. 保留历史 paper 表和只读样本，不做表删除和数据迁移。

验收测试建议：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_independent_runtime_components.py -q
```

必须新增或更新测试：

- paper removed task 被 worker 领取后标记 skipped。
- skipped 是 terminal，不会被再次 claim。
- skipped 不计入 failed，不触发 retry。
- 非 paper 核心任务仍正常执行。

### G2：低吸物化失败隔离

目标：解决 `low_buy_materialization_refresh` 持续失败，不改变生产排序。

开发项：

1. 提取并归类 `missing_strategies`：
   - 生产必需策略缺失：任务失败。
   - 禁用/研究/历史归档策略缺失：标记 skipped/incomplete，不导致整批失败。
2. 物化结果必须显式记录：
   - `required_strategies`
   - `skipped_strategies`
   - `missing_required_strategies`
   - `is_partial`
   - `stale_reason`
3. 不伪造候选、不补假分、不改变 `production_score`。
4. 连续失败增加退避，避免高频重试放大 MySQL/worker 压力。

验收：

- priority board 排序和生产分不变。
- 核心策略缺失仍能阻断发布。
- 非生产策略缺失不再让整批任务失败。
- failed task 增速下降。

### G3：provider/BFF/readyz 降级隔离

目标：外部行情源或慢源异常时，页面可用、核心热读不被拖垮。

开发项：

1. EastMoney/AkShare 返回 HTML、超时、断连时进入 provider 熔断。
2. 热接口读取本地缓存或最近快照，返回 stale 标记，不同步等待外部 provider。
3. BFF 每个 source 独立 timeout，慢源降级，不拖垮整页。
4. `/healthz` 和 `/readyz` 分层：
   - `/healthz` 只代表进程活着。
   - `/readyz` 使用短超时依赖检查，DB 卡住时快速失败，不挂 10s+。

验收：

- `/api/bff/v1/workspace/monitor` 在单个慢源失败时仍返回主 payload。
- provider 异常时页面显示 stale/degraded，不白屏。
- `/readyz` 不出现长时间挂起。
- monitor BFF 和 priority board p95 回到既有目标区间后再进入线上观察。

### G4：旧前端退役未完成项

目标：把旧 `frontend/` 从“运行链路退役”推进到“可归档/可删除”，但物理删除必须后置授权。

已完成事实：

- backend 静态入口已使用 `frontend-next/dist`。
- 主 Dockerfile、分离前端 Dockerfile、CI artifact、deploy scope 已退役旧前端。
- `/__legacy/*` 已返回退役 404。
- `frontend-hot` / `frontend-legacy` 显式部署 scope 已阻断。

未完成项：

1. 旧 `frontend/` 源码目录未物理删除。
2. `frontend/android`、`frontend/ios` 相关 native/mobile 脚本仍需 owner review：
   - `scripts/version_sync.py`
   - `scripts/harden_native_release_config.py`
3. delta 打包、清理脚本仍有旧路径保护/忽略引用，需要归档完成后再收口。
4. 大量历史 docs/reports 仍引用旧前端，不能批量改写，只能归档说明。
5. 线上 `frontend-web` 分离验证栈仍常驻，但它使用的是 `frontend-next`，不是旧前端；是否停用属于运维授权事项。

开发项：

1. 新增旧前端退役状态文档或更新当前决策报告，明确：
   - `frontend/` = retired source。
   - 不再作为运行入口。
   - 不再作为 CI/Docker/deploy 产物。
   - 仅用于历史追溯/native owner review/回滚资料。
2. 补/保留 guard 测试：
   - 禁止 `frontend-hot` / `frontend-legacy` 进入 deploy scope。
   - 禁止 Docker/CI 重新构建 `frontend/dist`。
   - 禁止 backend 重新启用 `/__legacy/*` 静态资源。
   - 禁止旧 `/paper` 页面恢复。
3. 设计物理删除前置检查脚本或清单：
   - `frontend-next` 线上稳定观察 1-2 个交易日。
   - native/mobile owner 确认。
   - `rg` 引用复扫只剩历史文档和删除保护项。
   - 旧源码已 tag/branch/压缩包归档。
   - 用户明确授权删除。

物理删除批次不得和稳定性修复混在同一批执行。

### G5：线上资源与运维整改（授权后）

这些不是本地开发默认动作，必须单独授权：

1. MySQL OOM：
   - 评估 buffer pool 与 cgroup limit 配比。
   - 先复核峰值，再调整。
   - 避免单纯放大容器 limit 造成整机 swap 抖动。
2. runtime-worker 内存：
   - 通过 G1/G2/G3 减少失败重试和慢源阻塞。
   - 再评估是否需要内存 limit 或任务分片。
3. 域名 reset：
   - 只读检查 nginx server block。
   - 去重 `server_name`、证书/SNI/安全组修复必须授权后执行。
4. Docker cache：
   - 只允许受控清理 build cache/image cache。
   - 禁止 `volume prune`。
5. scheduler 合并：
   - 必须 feature flag + leader lock + 一个交易日观察。
   - 不得直接停独立 scheduler。

## 6. 推荐批次顺序

| 批次 | 内容 | 是否需要线上授权 | 风险 |
|---|---|---:|---|
| B0 | 只读复核、任务/引用清单 | 否 | 低 |
| B1 | paper removed task skipped 终态 | 否，本地开发 | 低 |
| B2 | 低吸物化失败隔离与退避 | 否，本地开发；部署需授权 | 中 |
| B3 | provider/BFF/readyz 降级 | 否，本地开发；部署需授权 | 中 |
| B4 | 旧前端退役 guard 和归档清单 | 否 | 低 |
| B5 | 线上部署与观察 | 是 | 中 |
| B6 | MySQL/nginx/Docker/scheduler 运维整改 | 是 | 中到高 |
| B7 | `frontend/` 物理删除 | 是，且必须单独批次 | 中 |

## 7. 验收矩阵

| 领域 | 验收标准 |
|---|---|
| 策略语义 | `strategy_policy.py` 无修改；`production_score` 和 priority board 排序不变 |
| 核心任务 | 行情、日线、低吸榜、推荐榜、priority board、watchdog 正常 |
| paper 残留 | removed paper task 被 skipped，不 retry、不计 failed |
| 低吸物化 | 非生产策略缺失不拖垮整批；核心策略缺失仍阻断 |
| BFF/provider | 慢源/外部失败时返回 degraded/stale，不白屏 |
| readyz | 短超时返回，不长时间挂起 |
| 旧前端 | CI/Docker/deploy/backend 不再依赖 `frontend/`；旧入口不恢复 |
| 线上稳定 | MySQL/runtime-worker restart count 不增长；swap 不持续上升 |
| 文档 | 新增报告说明改动、测试、线上启用步骤、授权项 |

## 8. 建议测试命令

先按实际改动选择，不要盲目全量运行：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_runtime_task_queue.py \
  backend/tests/test_phase4_runtime_worker_tasks.py \
  backend/tests/test_independent_runtime_components.py \
  backend/tests/test_frontend_next_level1_cutover.py \
  backend/tests/test_deploy_scope.py \
  backend/tests/test_cloud_deploy_scripts.py -q
```

如果改到 BFF/provider：

```bash
PYTHONPATH=backend:. backend/.venv/bin/python -m pytest \
  backend/tests/test_bff_monitor_workspace.py \
  backend/tests/test_low_buy_read_paths.py \
  backend/tests/test_market_routes.py -q
```

如果改到 `frontend-next`：

```bash
cd frontend-next
npm run api:check
npm run lint
npm test -- --run
npm run build
```

最后必须：

```bash
git diff --check
git status --short
```

## 9. 需要用户授权的操作清单

以下只写建议，不在开发批次中执行：

1. 部署 B1-B3 代码到线上。
2. 重启或重建 app/runtime-worker/mysql/nginx。
3. 修改 MySQL buffer pool、容器内存 limit、线上 `.env`。
4. 修复 nginx server block 并 reload。
5. Docker cache/image prune。
6. 停用 `frontend-web` 分离验证栈。
7. scheduler 合并灰度后停止独立 scheduler。
8. 物理删除 `frontend/`。

## 10. 可直接使用的执行提示词

```text
你在 /Users/j/Documents/gupiao 项目中工作。目标：按照 docs/superpowers/plans/2026-06-11-online-stability-legacy-frontend-retirement-integrated-plan.md，实施“线上稳定性整改 + 已移除模拟盘残留任务收口 + 旧前端退役未完成项”的本地开发批次。只做本地代码、测试和报告；不部署、不切流、不重启线上服务、不清理线上资源、不改线上配置、不写生产数据库。

开始前必须：
1. 执行 cd /Users/j/Documents/gupiao && git status --short，保护未提交文件。
2. 阅读 AGENTS.md、docs/engineering-conventions.md。
3. 阅读 docs/superpowers/plans/2026-06-11-online-stability-legacy-frontend-retirement-integrated-plan.md。
4. 阅读 docs/reports/online-service-status-audit-2026-06-11.md。
5. 阅读 docs/reports/legacy-frontend-retirement-execution-2026-06-10.md 和 docs/reports/legacy-frontend-retirement-decision-2026-06-11.md。
6. 用 rg 复核 paper、runtime task、low_buy_materialization、priority_board、frontend/dist、frontend-legacy、frontend-hot、__legacy 相关代码，不要凭印象改。

硬边界：
- 不改 strategy_policy.py。
- 不改变 production_score。
- 不改变 priority_board 排序和口径。
- 不停、不降级核心行情刷新、日线刷新、低吸榜、推荐榜、priority board 物化、watchdog、数据新鲜度检查。
- 不恢复 /paper 或 /next/paper 模拟盘入口。
- 不新增 PAPER_RUNTIME_TASKS_ENABLED 暂停开关，因为 active 模拟盘功能已经下线。
- 不物理删除 frontend/，旧前端源码删除必须作为单独授权批次。
- 不执行 docker restart/down/up/stop/start、systemctl restart、nginx reload、Docker prune、线上 .env 修改、compose 修改生效、数据库写操作。
- 不部署、不切流。

本轮优先开发任务：
1. 修复已移除 paper runtime task 的残留处理：
   - 识别 paper_review_report、paper_portfolio_execution_preview、paper_ledger_reconcile_preview 以及 paper_ 前缀任务；
   - 增加 skipped 或等价终态；
   - removed paper task 被 worker 领取后标记 skipped_removed_feature；
   - 不计入 failed，不 retry，不再次 claim；
   - summary/status_counts 能展示 skipped；
   - 保留历史 paper 表和只读样本，不删表、不迁移数据。
2. 修复 low_buy_materialization_refresh 失败隔离：
   - 区分生产必需策略缺失和非生产/禁用/研究策略缺失；
   - 非生产缺失只标记 skipped/incomplete，不导致整批失败；
   - 生产必需策略缺失仍失败；
   - 不伪造数据，不改分数，不改排序；
   - 增加退避或避免 retry storm。
3. 修复 provider/BFF/readyz 降级：
   - EastMoney/AkShare HTML/超时/断连走缓存或 stale；
   - 热接口不同步等待外部 provider；
   - BFF 各 source 独立 timeout，慢源降级；
   - readyz 使用短超时，不长时间挂起。
4. 旧前端退役未完成项：
   - 不删除 frontend/；
   - 补充或保持 guard，防止 CI/Docker/deploy/backend 重新依赖旧 frontend/dist、frontend-hot、frontend-legacy、__legacy；
   - 输出旧前端物理删除前置清单：线上稳定观察、native/mobile owner review、引用复扫、归档 tag/branch、用户授权。

测试要求：
- 根据实际改动运行相关测试，不要伪造全绿。
- 至少覆盖 runtime task queue/worker 的 skipped removed feature 行为。
- 如果改 low_buy/BFF/provider，运行对应后端测试。
- 如果改 frontend-next，运行 api:check、lint、test、build。
- 最后运行 git diff --check 和 git status --short。

输出要求：
1. 写一份实施报告到 docs/reports/，说明改动、测试、未执行的线上操作、线上启用步骤、回滚方案。
2. 最终回复列出修改文件、测试结果、核心任务保护情况、需要用户授权的线上动作。
3. 明确说明本轮未执行部署、重启、清理、线上配置修改、数据库写操作、旧前端物理删除。
```
