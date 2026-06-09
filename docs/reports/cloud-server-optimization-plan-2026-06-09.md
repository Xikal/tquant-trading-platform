# 线上服务器优化方案（43.143.243.97 · weisilianghua.cloud · 2026-06-09）

> 性质：**方案/建议，不代执行、不部署、不切流、不改生产代码**。所有动作均为待运维在服务器执行的 ops/配置规格（含命令、预期、风险、回滚）。
> 依据：用户只读 SSH 巡检结果（4C / 3723 MiB / 60G）。
> 硬边界：不动 `strategy_policy.py`/生产排序/`production_score`；不停核心数据刷新发布；不动 MySQL 主写与数据；不破核心闭环。

---

## 0. 一句话诊断与结论

**这台机器 CPU 几乎闲置（load 0.5 / 4 核 ≈ 12%），真正的瓶颈是内存——3.18G/3.7G 已用、Swap 1.74G/1.99G 重度使用，性能正被 Swap 拖垮。** 根因是**内存过度承诺**：4 个 Python 大进程（app 713M + runtime-worker 530M + runtime-scheduler 472M + mysql 519M ≈ 2.2G）+ **一套并行运行但不对外服务的"分离验证栈"** + OS，超过物理内存 → 落 Swap。

**结论**：不用升配。按本方案 P0+P1 释放约 **700M–1G 内存**即可**脱离 Swap、机器恢复健康**；同时 `docker builder prune` 一把释放 **~11.8G 磁盘**。全程不动生产链路。

---

## 1. 现状盘点（实测）

| 维度 | 现状 | 判断 |
|---|---|---|
| CPU | 4 vCPU，load 0.39/0.47/0.54 | **闲置**，非瓶颈，勿加 CPU |
| 内存 | 3723 总 / 3184 用 / 539 余 | **偏紧** |
| Swap | **1736 / 1987 已用** | **重度 Swap，性能杀手** |
| 磁盘 | 35G/59G（62%） | 够用，但 build cache 11.8G 可清 |
| Docker | 镜像 14.23G + 卷 6.95G + **build cache 11.81G** | cache 立即可清 |
| 双栈并存 | 主栈（18090 单体）**+ 分离验证栈**（18080/18091/18000，**公网未代理**） | 分离栈白占内存/容器 |

**内存大头**：app 713M、runtime-worker 530M、runtime-scheduler 472M、mysql 519M、backtest-worker 43M、analytics-worker 19M、Go 各 5–8M、分离栈 ~33M。

**全栈无资源上限**（compose 无 `mem_limit`/`deploy.resources`）→ 容器可挤占至 Swap。

---

## 2. 优化分级（按"立即/风险/收益"，含具体数值）

### P0 立即零风险（磁盘 + 停冗余栈 + 内核参数）

| # | 动作 | 命令（服务器执行） | 预期 | 风险/回滚 |
|---|---|---|---|---|
| P0-1 | **清 Docker build cache** | `docker builder prune -af` | **磁盘 −11.8G**（62%→~42%） | 零；cache 下次构建自动重建 |
| P0-2 | **清悬空镜像** | `docker image prune -f`（确认无在用旧 tag 后可 `-a`） | 磁盘再 −数 G | 低；保留在用镜像 |
| P0-3 | **停分离验证栈**（未对外服务） | `docker compose -f docker-compose.separated.yml down` | 释放 ~33M + 3 容器开销；端口 18080/18091/18000 释放 | 零；保留 compose 文件，需要时 `up` 重起。**确认 nginx 仍 → 18090**（现状即是） |
| P0-4 | **降 swappiness**（默认 60→10） | `sysctl vm.swappiness=10` + 写 `/etc/sysctl.d/99-swappiness.conf` | 内核减少过早换出，**Swap 抖动立降**、响应变快 | 零；改回 60 即回滚 |

> P0 不动任何生产容器，先把磁盘和 Swap 抖动压下去。

### P1 低风险内存右调（核心：消掉冗余的 Python 大进程）

| # | 动作 | 规格 | 预期释放 | 风险/回滚 |
|---|---|---|---|---|
| P1-1 | **`APP_WORKERS` 2 → 1** | `app` 服务 env `APP_WORKERS=1`（少用户、CPU 闲，1 worker 足够） | **app 713M → ~480M，省 ~200–230M** | 低；并发降一半但远超现需求；回滚改回 2。注意 SEC2 限流口径随并发推导，确认限流配置一致 |
| P1-2 | **合并 `runtime-scheduler` 进 `runtime-worker`** | 让 worker 容器同时承担 scheduler 角色（`RUNTIME_BACKGROUND_ROLE=worker` + 开启其调度入队），停掉独立 scheduler 容器 | **省 ~450M（一个满载 Python 进程）** —— 单项最大内存收益 | 中：长任务可能延后定时入队 → 少用户可接受；**先验证定时刷新/收盘发布仍按时**；回滚=重起独立 scheduler 容器 |
| P1-3 | **`analytics-worker`/`backtest-worker` 改按需（profile）** | compose `profiles: [heavy]`，默认不启动；跑 24M 报告/导出/权威回测时 `--profile heavy up` 拉起，跑完 `down` | 省 ~62M + 两份 Python 基线 | 低：重任务前需拉起（写进 runbook）；回滚=改回常驻 |
| P1-4 | **MySQL buffer pool 上限** | `innodb_buffer_pool_size=256M`（按小机右调）+ 连接数右调 | mysql RSS 受控、防膨胀 | 低：仅缓存，**不丢数据**；命中率略降；回滚改回 |

**P1 合计预期**：P1-1（−210M）+ P1-2（−450M）+ P1-3（−62M）≈ **释放 ~720M**。叠加 P0-3（−33M）→ 内存用量 3184M → **~2430M**，**Swap 从 1.7G 排空到接近 0**，余量回到 ~1.2G。

### P2 防膨胀（资源上限）

| # | 动作 | 规格 |
|---|---|---|
| P2-1 | **每容器设 `mem_limit`** | 按右调后峰值×1.3：mysql 700M、app 600M、runtime-worker（含 scheduler）700M、redis 128M、go 各 64M、heavy worker 各 512M | 防任一容器挤占至 Swap；OOM 即上调 |
| P2-2 | **容器日志限制** | compose 加 `logging: { options: { max-size: "10m", max-file: "3" } }` | 防日志无限增长占磁盘/IO |

### P3 架构决策（需你定，非必须）

| 方向 | 说明 | 取舍 |
|---|---|---|
| **完成"分离栈"切换** | 公网 nginx 改 → 静态前端 nginx(4.9M) + backend-api，单体 app(713M) 不再兼服静态 | 长期更省内存，但需 cutover 验证（当前 backend-api 仅 27M 疑为无流量空载）→ **暂不切，先停冗余栈**（P0-3） |
| **维持单体 18090** | 现状，主入口稳定 | 推荐：先按 P0–P2 右调单体，不引入 cutover 风险 |

---

## 3. 量化目标（M0 → 目标）

| 指标 | M0（现状） | 目标（P0+P1+P2 后） |
|---|---|---|
| 内存已用 | 3184 MiB | **~2400–2600 MiB** |
| Swap 已用 | **1736 MiB** | **< 300 MiB（接近 0）** |
| 空闲内存 | 539 MiB | **~1100–1300 MiB** |
| 磁盘使用 | 62%（35G） | **~40%（~23G）** |
| 常驻容器 | 主栈 10 + 分离 3 = 13 | **7–8**（停分离 3、合并 scheduler、heavy 按需） |
| 容器资源上限 | 无 | **每容器有 mem_limit** |
| CPU load | 0.5 | 不变（本就闲） |
| `/readyz` | 全 true | **全 true 不变** |
| 生产策略/排序/数据发布 | 基线 | **不变** |

---

## 4. 实施顺序

1. **P0（5 分钟，立即）**：`docker builder prune -af` + `image prune` + 停分离栈 + swappiness=10。→ 磁盘 −11.8G，Swap 抖动立降。
2. **P1-1 + P1-3 + P1-4（低风险）**：APP_WORKERS=1、analytics/backtest profile 化、mysql buffer pool 上限。→ 再释放 ~270M。
3. **P1-2（合并 scheduler，需观察）**：合并入 worker，**观察一个交易日**确认定时刷新/收盘发布正常。→ 释放 ~450M，彻底脱离 Swap。
4. **P2（防回潮）**：设 mem_limit + 日志限制。
5. 跑完后取新基线，确认 Swap 接近 0、`/readyz` 全 true、生产闭环正常。

---

## 5. 验收标准

- `free -m`：Swap 已用 < 300M、空闲内存 > 1G。
- `docker stats --no-stream`：常驻容器内存之和较 M0 显著下降；无容器顶到 mem_limit。
- `df -h`：磁盘使用 ~40%。
- `curl -fsS https://weisilianghua.cloud/readyz`：`database/frontend_dist/frontend_next_dist/analytics_dependencies` 全 true。
- **生产不变**：`/monitor→/playbook→/backtest→/paper→/settings` 可用；priority board 排序/`production_score`/低吸语义/交易日发布口径不变；盘中数据刷新与收盘发布按时；按需拉起的 analytics/backtest 能正常完成 24M 报告/权威回测。
- nginx/HTTPS/HSTS/CSP/限流不变（仍 → 18090）。

---

## 6. 风险与回滚

| 动作 | 回滚 | 生产保护 |
|---|---|---|
| build cache / image prune | 自动重建/重拉 | 不影响运行容器 |
| 停分离栈 | `compose -f separated up -d` | 它本不对外服务 |
| swappiness | 改回 60 | 纯内核参数 |
| APP_WORKERS=1 | 改回 2 | 少用户足够；限流口径核对 |
| 合并 scheduler | 重起独立 scheduler 容器 | **先观察一个交易日**，定时入队/发布异常立即回滚 |
| analytics/backtest profile | 改回常驻 | 不改任务逻辑/回测口径，仅启动方式 |
| mem_limit | 移除/上调 | OOM 即上调 |
| mysql buffer pool | 改回 | 仅缓存，不丢数据 |

**绝对不动**：`strategy_policy.py`、生产排序、`production_score`、priority board、低吸生产语义、paper 账本写、MySQL 主写与数据、daily bar/quote cache/物化/收盘发布、核心 `runtime-worker`（数据刷新）、`go-bff/go-market-read`、nginx/HTTPS、OpenAPI 契约。

---

## 7. 优先级总结

| 优先级 | 动作 | 收益 | 风险 |
|---|---|---|---|
| **立即** | build cache 清理（−11.8G 磁盘） | 高 | 零 |
| **立即** | 停分离验证栈 + swappiness=10 | 中（Swap 立降） | 零 |
| **高** | APP_WORKERS 2→1 + heavy worker 按需 + mysql buffer pool | 中（−270M） | 低 |
| **高（观察后）** | 合并 runtime-scheduler 进 worker | **高（−450M，脱离 Swap）** | 中 |
| **稳态** | 每容器 mem_limit + 日志限制 | 防回潮 | 低 |
| 可选 | 完成分离栈 cutover | 长期省 | 中（需 cutover）|

**一句话**：先 `docker builder prune` 拿回 11.8G 磁盘、停掉那套没对外服务的分离栈、把 swappiness 调到 10；再把 `APP_WORKERS` 降到 1、analytics/backtest 改按需、合并 scheduler——**释放约 700M–1G 内存即可让这台 4C/4G 机器彻底脱离 Swap、健康运行，无需升配、不动任何生产链路。**

---

## 交付说明（合规）
- 未修改任何代码、未部署、未切流、未删旧前端、未改生产策略/排序/`production_score`。
- 本报告为服务器 ops/配置建议；命令需运维在服务器执行，本轮仅出方案。
