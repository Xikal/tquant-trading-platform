# 工程结构、命名与文件规模规范

状态：默认生效
适用范围：后续所有文档、后端、前端、脚本、测试与生成产物
最后核验日期：2026-05-31

## 1. 生效规则

1. 后续开发默认遵循本文，无需额外说明。
2. 优先级从高到低为：用户当轮明确要求、唯一权威计划文档、`AGENTS.md`、本文、局部代码惯例。
3. 本文不要求立即重构历史遗留文件；但新功能、新文档、新脚本必须按本文落位。
4. 修改已超限文件时，优先保持增量最小；如果新增超过 50 行或继续扩大职责，必须先拆分或写清楚豁免原因。
5. 生成产物、锁文件、OpenAPI 输出、回测大 JSON 不按人工代码行数考核，但必须放在指定目录，不能混入手写文档区。

## 2. 文档结构

### 2.1 顶层文档

顶层只保留长期入口和稳定说明：

| 目录/文件 | 用途 | 规则 |
|---|---|---|
| `README.md` | 项目入口 | 只放当前启动、主要模块、常用命令 |
| `DEVELOPMENT_GUIDE.md` | 开发环境与本地运行 | 不放一次性策略复盘 |
| `PRODUCTION_RUNBOOK.md` | 生产运行手册 | 只放生产相关流程 |
| `TRADING_QUANT_LEAD_PLAYBOOK.md` | 量化与交易方法约束 | 作为策略原则，不作为代码事实来源 |
| `AGENTS.md` | 多 Agent 与默认协作规则 | 必须链接本文 |

禁止在根目录新增一次性审查报告、临时计划、回测结果或截图说明。

### 2.2 `docs/` 分类

| 路径 | 放什么 | 不放什么 |
|---|---|---|
| `docs/engineering-conventions.md` | 本规范 | 一次性任务计划 |
| `docs/operations/` | Runbook、发布、观测、回滚、数据修复流程 | 回测明细 JSON |
| `docs/reports/` | 人读 Markdown 报告、审查结论、验收摘要 | 新增大型机器 JSON、zip 包 |
| `docs/superpowers/plans/` | 明确分批执行的权威计划 | 普通报告 |
| `docs/contracts/` | OpenAPI、接口契约、生成契约 | 手写说明长文 |
| `docs/archive/` | 明确不再作为当前依据的历史材料 | 当前 Runbook 或准入门槛 |

策略机制文档使用 `docs/strategy-<strategy-key>.md`。
执行计划使用 `docs/<topic>-execution-plan-YYYY-MM-DD.md`。
复盘报告使用 `docs/reports/<topic>-review-YYYY-MM-DD.md` 或 `docs/reports/<topic>-backtest-YYYY-MM-DD.md`。
Runbook 使用 `docs/operations/<topic>-runbook.md`。

## 3. 文件命名

### 3.1 通用规则

1. 文件名默认英文、全小写、kebab-case 或 snake_case；不使用空格。
2. 日期统一 `YYYY-MM-DD`，放在语义后面，例如 `strategy-24m-backtest-2026-05-31.md`。
3. 人读文档用 `.md`；机器交换用 `.json`；脚本输出不要伪装成文档。
4. 同一主题的 `.md` 和 `.json` 使用相同 basename。
5. 文件名必须表达业务含义，不能只写 `utils`、`common`、`misc`，除非目录内已有稳定惯例。
6. 不允许用 `final`、`new`、`copy`、`tmp`、`backup` 作为长期文件名。

### 3.2 后端

| 类型 | 命名 |
|---|---|
| Python 模块 | `snake_case.py` |
| Python 类 | `PascalCase` |
| 函数/变量 | `snake_case` |
| 常量/feature flag | `UPPER_SNAKE_CASE` |
| FastAPI 路由文件 | `resource_name.py`，按业务资源拆分 |
| SQL/Alembic migration | 保持 Alembic 生成前缀，slug 用 snake_case |
| 后端测试 | `backend/tests/test_<domain>_<behavior>.py` |

### 3.3 前端

| 类型 | 命名 |
|---|---|
| React 组件文件 | `PascalCase.tsx` |
| 页面组件 | `<Feature>Page.tsx` |
| Hook | `use<Thing>.ts` |
| store/slice | `<domain>Store.ts` 或 `<domain>Slice.ts` |
| 类型文件 | `<domain>.ts`，集中类型可放 `frontend/src/types/` |
| 测试 | `<Component>.test.tsx` 或 `<domain>.test.ts` |
| 样式 | 按现有目录分层，避免新增全局大 CSS |

新表格默认用 `DataTable`，长列表默认用 `VirtualCardList`。禁止新增 raw `<Table>` 或非业务 slice 截断，除非既有 guard 明确允许。

### 3.4 脚本

| 类型 | 命名 |
|---|---|
| 后端分析脚本 | `backend/scripts/<domain>_<action>.py` |
| 根目录维护脚本 | `scripts/<domain>_<action>.py` 或 `.mjs` |
| 前端检查脚本 | `frontend/scripts/<domain>-<action>.mjs` |

脚本必须能从仓库根或所在 package 明确运行。需要长参数时，提供 `--help` 或在 Runbook 中写明示例命令。

## 4. 单文件行数

### 4.1 手写代码阈值

| 文件类型 | 目标上限 | 评审阈值 | 必须拆分阈值 |
|---|---:|---:|---:|
| 后端 service/module | 300 行 | 400 行 | 600 行 |
| 后端 route | 250 行 | 350 行 | 500 行 |
| 后端脚本 | 350 行 | 450 行 | 650 行 |
| 后端测试 | 350 行 | 500 行 | 800 行 |
| React 页面 | 300 行 | 400 行 | 600 行 |
| React 组件 | 220 行 | 300 行 | 450 行 |
| Hook/store | 220 行 | 300 行 | 450 行 |
| 前端测试 | 350 行 | 500 行 | 800 行 |
| CSS/SCSS 单文件 | 300 行 | 450 行 | 700 行 |
| 手写 Markdown | 500 行 | 800 行 | 1200 行 |

### 4.2 超限处理

1. 超过目标上限：允许合入，但必须确认职责单一。
2. 超过评审阈值：新增功能前先判断是否拆分；不拆必须在 PR/交付说明中写原因。
3. 超过必须拆分阈值：除紧急修复外，不再继续追加业务逻辑。
4. 旧文件已经超限时，不为了形式拆分；只有在新增职责、修 bug 需要大改、或影响测试可维护性时拆。

推荐拆分方式：

| 原文件问题 | 拆分方向 |
|---|---|
| route 同时做鉴权、查询、聚合、序列化 | route 保留入口，service/query/schema 分离 |
| service 同时做数据读取、评分、过滤、报告 | reader/scorer/filter/reporter 分离 |
| 页面同时做拉取、状态、布局、图表、表格 | page、hook、panel、table、chart 分离 |
| 测试文件覆盖太多场景 | 按 API、核心规则、异常路径、回归守卫拆 |
| 脚本参数和执行逻辑混杂 | cli、runner、report_writer、domain helper 分离 |

### 4.3 豁免文件

以下文件不按手写代码阈值处理，但要避免人工编辑：

1. `frontend/src/generated/*`
2. `docs/contracts/openapi.json`
3. `package-lock.json`
4. Alembic 自动生成迁移中的长 schema 片段
5. 回测、分析、验收生成的 `.json`、`.parquet`、manifest
6. 第三方或移动端构建产物

## 5. 模块边界

### 5.1 核心流程

核心流程默认保留并优先维护：

1. `monitor`
2. `emotion`
3. `analysis`
4. `playbook`
5. `strategy`
6. `backtest`
7. `paper`
8. `settings`

涉及这些流程的功能必须优先保证可运行、可回归、可解释。

### 5.2 研究与外围能力

以下能力默认按研究、管理或可选增强处理，除非用户明确要求进入主路径：

1. agent/Feishu 集成
2. factor mining
3. ML/RL 重任务
4. native/mobile 构建链
5. Go/Rust 性能实验
6. 自动化运营或 autopilot 类能力

处理原则：先 feature flag、路由隐藏、任务停用或懒加载，再考虑删除。不得把“维护成本高”直接等同于可删除。

### 5.3 生产与研究隔离

1. 生产排序、生产分、priority board 必须有明确门控。
2. research-only 策略不能因为前端展示或报告生成进入生产候选。
3. 缺数据必须显式标记 `blocked`、`research_only`、`no_data` 或等价状态，禁止空分、假分、TODO 占位。
4. 重计算任务只能由 runtime worker、backtest worker 或 analytics worker 消费；Web 默认不得新增后台 loop。

## 6. 十二条强制补充规则

### 6.1 分支与提交规范

1. 分支名默认使用 `codex/<topic>`；修复类可用 `fix/<topic>`，明确功能可用 `feature/<topic>`。
2. commit 信息必须表达任务编号或改动意图，例如 `Task A1: add decision context schema`、`docs: add engineering conventions`。
3. 禁止一个 commit 混合功能、大重构、格式化、生成产物和无关清理。
4. 若用户要求“一项任务一个 commit”，必须严格按 Task 拆分提交。

### 6.2 目录所有权

1. `backend/app/services/` 放业务逻辑，不放前端展示文案和页面拼装。
2. `backend/app/api/routes/` 只做 API 入口、参数解析、权限和响应编排，不堆复杂计算。
3. `frontend/src/features/` 放页面和业务 UI，不放后端聚合逻辑。
4. `frontend/src/ui/` 放通用 UI 组件，不放 A 股策略业务规则。
5. `docs/reports/` 放人读摘要和审查结论，不放新增大型机器 JSON。
6. `backend/data/` 放本地数据、分析产物和回测明细，不作为手写文档区。
7. `scripts/` 与 `backend/scripts/` 放可重复执行工具，不放一次性草稿。

### 6.3 Feature Flag 规则

1. 新增非核心、研究型、重任务、管理型能力默认 feature flag 关闭。
2. 新 flag 必须同时具备配置声明、默认值、测试覆盖、回退说明。
3. 后端配置必须在对应 settings 中声明；禁止依赖未声明环境变量。
4. 前端入口必须尊重后端状态或本地配置，不能只隐藏按钮但保留自动执行。
5. 关闭 flag 时，核心流程必须回到既有行为，不得出现空列表、假分或静默失败。
6. 生产排序、生产分、后台重任务、外部通知、自动化执行必须单独门控。

### 6.4 API 与数据契约规范

1. 新接口必须先明确 request/response schema，再写业务实现。
2. 禁止前端依赖后端临时字段、未声明字段或样例 JSON 字段。
3. OpenAPI、generated types、接口测试必须同步更新。
4. 后端内部字段默认 `snake_case`；前端使用生成类型时不手工改名。
5. 破坏兼容的字段变更必须提供迁移说明或兼容层。
6. API 返回的收益、评分、状态字段必须带口径或来源字段，避免前端误读。

### 6.5 测试最低要求

1. 后端核心 service、route、缺数据、权限、门控必须有测试。
2. 前端关键页面必须覆盖加载态、空数据、错误态、禁用态和核心交互。
3. 策略、回测、生产分、组合执行相关改动必须有口径守卫测试。
4. 修改缺数据处理时，必须覆盖 market-level 和 symbol-level 两类场景。
5. 修改生成报告时，必须测试候选池收益、真实组合收益、观察池收益不会混表。
6. 删除、隐藏、默认关闭功能时，必须确认路由、任务、前端入口、文档索引同步。

### 6.6 报告口径规范

1. 所有收益报告必须写明样本范围、时间范围、交易成本、滑点、成交假设、持仓规则。
2. 报告必须区分候选池收益、每日信号等权收益、真实组合收益、观察池收益。
3. 报告必须展示样本留存、成交留存、信号日留存、最长无票、最大回撤、PF、平均单笔。
4. `near_entry`、观察池、生产排行必须分表展示，禁止混入生产收益排行。
5. front_row_only、研究过滤器、实验分层只能作为对照时，必须标注“非生产硬过滤”。
6. 禁止只用总收益率作为结论依据；必须写明是否 OOS、是否 walk-forward、是否存在样本筛选风险。

### 6.7 生成产物清理规则

1. 新增大型机器可读结果默认进入 `backend/data/analytics/reports/`、`backend/data/reports/` 或外部 `artifacts/`。
2. `docs/reports/` 默认只放 Markdown 摘要；必须提交 JSON 时，需要同名 Markdown 解释口径。
3. zip、parquet、截图、录屏、批量窗口回测明细默认不提交。
4. 超过 5MB 的新文件必须在交付说明中解释用途、保留周期和替代方案。
5. 生成产物必须可追溯到脚本、命令、数据范围和生成日期。
6. 清理产物前必须用 `rg --fixed-strings <basename> .` 检查引用。

### 6.8 大文件治理

1. 现有超长文件不强制立即拆分，但不得继续无节制追加职责。
2. 已超过评审阈值的文件，只允许小修；新增功能优先拆到新模块。
3. 已超过必须拆分阈值的文件，除紧急修复外不得继续追加业务逻辑。
4. `MonitorPage.tsx`、大型 backtest 脚本、巨大测试文件等遗留文件按“只小修，不扩写”处理。
5. 拆分必须保持行为等价，并配套测试或快照校验。
6. 不允许为了降行数制造无意义的薄包装文件。

### 6.9 生产/研究边界

1. 生产排序、生产分、paper/shadow、观察池必须有明确状态边界。
2. 研究策略不能因为前端展示、报告排行、回测脚本误进入生产路径。
3. 缺数据必须降级并显式给出原因，禁止空分、假分、静默跳过。
4. 生产评分只能接入已明确允许的信号状态。
5. 观察信号只能进入观察池或 watch score，不能进入生产收益排行。
6. 任何生产边界变化必须有回归测试和报告口径说明。

### 6.10 废弃与保留机制

1. 不直接删除低收益模块，先做状态标记。
2. 可用状态为：`active`、`default_off`、`research_only`、`deprecated`、`remove_candidate`。
3. 删除前必须检查 route、任务、测试、前端入口、文档、数据迁移和用户数据。
4. 低收益但仍有审计价值的模块优先归档、隐藏或默认关闭。
5. 标记 `deprecated` 后必须写明替代路径和计划移除条件。
6. 标记 `remove_candidate` 后必须至少保留一次引用检查记录。

### 6.11 验收命令分层

1. 小范围文档改动：无需跑测试，但交付说明必须写明未运行测试。
2. 后端小改：跑相关 pytest 定向用例。
3. 后端核心改动：跑相关 pytest、契约测试和受影响路由测试。
4. 前端改动：至少跑 lint、相关测试和 build；涉及类型生成时跑 API check。
5. 策略、回测、生产分改动：必须跑口径守卫、样本报告或指定回测验收。
6. 数据库迁移：必须跑 upgrade、downgrade、upgrade 冒烟。
7. 高风险合入前必须跑全量回归，不能只写“通过”。

### 6.12 例外审批规则

1. 允许临时超限、临时放错目录、临时不拆分，但必须显式记录。
2. 例外说明必须包含：为什么例外、影响范围、后续清理条件、是否需要单独计划。
3. 例外不能突破生产/研究边界、缺数据处理、未来函数、自动执行和收益展示口径底线。
4. 同一例外连续出现两次后，第三次必须治理，不能继续延期。
5. 用户明确要求的临时交付，也要在最终说明中标记技术债。

### 6.13 前端性能预算与热路径规则

1. 前端构建必须保留 bundle budget 门：`frontend/scripts/check-bundle-budget.mjs` 校验 `first_screen_js_gzip_kb`、总 gzip 和单 chunk gzip，CI build 后必须执行。
2. 任何单 JS chunk gzip 超过 150KB 必须在预算脚本或 allowlist 中给出明确理由；首屏预算以 `docs/superpowers/plans/2026-06-03-frontend-stability-final-hardening.md` 为准。
3. 禁止 `<=1000ms` 定时器写 Zustand/global store；高频心跳、行情 tick 等真实热路径只能写 `frontend/src/state/realtime/` 下的 signals。
4. signals 不替代 TanStack Query，不外溢到普通页面组件；服务端数据仍以 Query 为唯一真源。
5. 热接口默认使用 stale-while-revalidate：保留上一版数据、reconnect 自动刷新、mount 不强制清空重取。

## 7. 新功能落位规则

新增功能先回答四个问题：

1. 属于核心流程、研究能力、管理能力还是一次性工具？
2. 是否需要 feature flag，默认是否关闭？
3. 数据与报告产物落在哪个目录，是否会进入版本库？
4. 对应测试放在哪里，是否有回归守卫？

默认落位：

| 功能类型 | 后端 | 前端 | 文档 |
|---|---|---|---|
| 核心业务 API | `backend/app/api/routes/` + `backend/app/services/` | `frontend/src/features/<feature>/` | `docs/operations/` 或机制文档 |
| 分析/回测脚本 | `backend/scripts/` | 无 | `docs/reports/` 摘要 |
| 后台任务 | `backend/app/workers/`、`backend/scripts/analytics_worker.py`、任务 handler | 只展示状态 | Runbook |
| 研究能力 | 对应 research service，默认 flag off | 懒加载或隐藏入口 | 研究报告 |
| 契约/类型 | schema、OpenAPI、generated types | generated types | `docs/contracts/` |

## 8. 文档写作规则

新文档必须包含：

1. 标题
2. 状态
3. 适用范围或目标
4. 最后核验日期
5. 结论或执行入口

报告类文档还必须写清楚：

1. 数据范围
2. 口径定义
3. 不可信或限制条件
4. 是否可作为生产依据
5. 后续动作

计划类文档还必须写清楚：

1. 硬边界
2. 分批范围
3. 验收命令
4. 回退方式
5. 不做什么

## 9. 提交前检查

每次开发结束前按改动类型检查：

1. 新文件路径是否符合本文目录规则。
2. 文件名是否符合命名规则。
3. 手写代码是否超过目标上限，超限是否解释。
4. 是否新增生成产物到错误目录。
5. 是否误把研究能力接入生产主路径。
6. 是否新增 Web 后台 loop。
7. 是否复用既有核心实现，而不是新建并行引擎。
8. 是否更新 `docs/README.md` 或对应 Runbook。

## 10. 后续默认执行

后续开发默认按以下方式执行：

1. 先确认任务属于哪个目录和模块边界。
2. 新文件按本文命名。
3. 新增代码保持在目标上限内。
4. 已超限文件只做小修；大改先拆。
5. 研究、外围、低收益功能默认 flag off 或懒加载。
6. 报告和回测优先输出 Markdown 摘要，大型数据进入数据产物目录。
7. 交付说明中列出任何偏离本文的地方。
