# A股短线做T量化 Web 应用

一个面向 A 股股票与 ETF 的短线做T量化系统，采用 `React + ECharts + FastAPI + SQLite` 架构，支持实时监控、量化信号、AI 补充分析、制度识别、风控配置、信号复盘与回测。

最终交付摘要见：[FINAL_DELIVERY.md](/Users/j/Documents/gupiao/FINAL_DELIVERY.md)

原生 App 开发说明见：[NATIVE_APP_SETUP.md](/Users/j/Documents/gupiao/frontend/NATIVE_APP_SETUP.md)

## 当前生产范围

- 生产选股与模拟盘默认覆盖主板股票与 ETF，剔除 ST、退市风险、创业板、科创板等高波动或权限要求更高的标的。
- 研究层策略、因子策略和灰度策略默认不进入普通用户入口、全策略优先榜和模拟盘自动交易。
- 回测结果会披露费用、滑点、涨跌停、同日止盈止损优先级、数据质量等执行假设；回测不代表未来收益或真实成交承诺。
- 外部行情与板块数据采用免费数据源优先，缺失或降级时会标记数据质量，不应把降级信号当作强执行依据。

## 已实现能力

- 支持 A 股股票与 ETF 的全市场标的同步
- 自选股实时监控面板
- 个股量化 + AI 分析页面
- 系统配置页面
- 交易制度识别（T+0 / T+1 / 底仓做T说明）
- 多周期做T量化引擎基础版
- VWAP / RSI / MACD / 均线 / ATR / 量比 / 板块代理联动
- 事件风险过滤与盘口增强降级逻辑
- AI 分析接口开放配置（OpenAI 兼容）
- 研究复盘页与 Walk-forward 回测接口
- 无 `akshare` 环境下自动使用内置种子库补齐全市场标的
- 自选监控接口异常降级（单标失败不影响整页）
- 策略护栏参数开放配置（成交额门槛、振幅区间、ATR 上限、开盘阶段阈值、最低目标盈利、滑点基线）
- 大模型 / 数据库 / 数据源配置双持久化（数据库 + `runtime.env`）

## 项目结构

```text
.
├── backend
│   ├── app
│   │   ├── api
│   │   ├── core
│   │   ├── models
│   │   ├── services
│   │   └── main.py
│   ├── data
│   ├── requirements.txt
│   └── .env.example
├── frontend
│   ├── src
│   │   ├── api
│   │   ├── components
│   │   ├── pages
│   │   ├── App.tsx
│   │   └── styles.css
│   ├── package.json
│   └── .env.example
├── PROJECT_PLAN.md
├── DEVELOPMENT_GUIDE.md
└── README.md
```

## 启动方式

也可以直接使用根目录 `Makefile`：

```bash
make qa
make ui-smoke
make prod-preflight
make version-sync
make version-check
make public-up
make public-down
```

### 1. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

后端默认地址：

- `http://127.0.0.1:8000`
- OpenAPI 文档：`http://127.0.0.1:8000/docs`
- 基础存活检查：`http://127.0.0.1:8000/healthz`
- 就绪检查：`http://127.0.0.1:8000/readyz`

### 2. 启动前端

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

前端默认地址：

- `http://127.0.0.1:5173`

前端开发模式默认通过 Vite 代理把 `/api` 请求转发到 `http://127.0.0.1:8000`，所以本地联调时不需要额外改接口地址。

### 3. 单端口运行

现在后端也可以直接托管 `frontend/dist`，因此生产化运行时只需要启动后端：

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器直接访问：

- `http://127.0.0.1:8000`

## 默认配置

### 数据源

- 默认标的同步：`akshare + Eastmoney`
- 默认实时行情与分钟线：Eastmoney 免费接口

### 数据库

- 默认：`SQLite`
- 默认位置：`backend/data/t_quant.db`
- Vercel 预览部署默认复制种子库到 `/tmp/t_quant.db`
- 正式长期部署建议改为外部数据库，例如 `PostgreSQL / MySQL`
- 现已内置 `MySQL + PyMySQL` 支持，适合本地用 Navicat 管理

### 大模型

在系统配置页填写以下内容即可启用：

- `API Key`
- `Base URL`
- `Model`

兼容任意 OpenAI 风格接口。

配置保存后会同时写入系统数据库和 `backend/data/runtime.env`，重启后仍可保留。

## 主要页面

### 1. 实时监控页

- 左侧主监控台，右侧紧凑底仓录入
- 自选股列表、底仓/可卖/成本价回显
- 实时行情、正T/反T/观望信号
- 质量分、建议仓位、预计价差、制度识别、阻断原因

### 2. 量化分析页

- 证券搜索
- 持仓/可卖数量输入
- 分时K线图表
- 量化建议
- 风控说明
- AI 补充结论

### 3. 研究复盘页

- 信号日志
- 回测运行
- 胜率、收益、回撤、Walk-forward 结果

### 4. 系统配置页

- 大模型配置
- 数据源配置
- 数据库配置
- 风控参数配置
- 策略护栏参数配置
- 最低目标盈利阈值配置
- 运行时持久化与诊断快照

## 测试方式

- 接口与策略冒烟：`./scripts/qa_smoke.sh`
- 浏览器级 UI 冒烟：`./scripts/ui_smoke.sh http://127.0.0.1:18080`
- 版本同步：`./scripts/version_sync.py`
- 版本一致性检查：`./scripts/version_sync.py --check`
- Makefile 快捷入口：`make qa`、`make ui-smoke`

`qa_smoke.sh` 会额外覆盖 `分析 / 设置持久化 / 自选信号 / 最低盈利阈值 / 回测接口`。

`ui_smoke.sh` 会临时插入测试标的、校验研究回测接口、抓取 `监控 / 分析 / 研究 / 配置` 四张页面截图，并在结束后自动清理测试自选。
截图会按实例地址分别写到 `.runtime/ui-smoke/<host_port>/`，避免 SQLite / MySQL 互相覆盖。

## 版本管理

项目现在使用根目录的 [VERSION.json](/Users/j/Documents/gupiao/VERSION.json) 作为单一版本源，统一管理：

- `version`：对外版本号，同时同步到 Web、后端 App bootstrap、Android `versionName`、iOS `MARKETING_VERSION`
- `build_number`：同步到 Android `versionCode` 和 iOS `CURRENT_PROJECT_VERSION`
- `min_supported_version`：同步到后端 App bootstrap 的最低支持版本

常用命令：

```bash
./scripts/version_sync.py --check
./scripts/version_sync.py
./scripts/version_sync.py --set-version 1.0.1 --set-build-number 2
./scripts/version_sync.py --set-min-supported 1.0.0
```

`prod_preflight.sh` 现在会先检查版本是否一致；如果 `VERSION.json` 和各端配置漂移，会直接失败。

## 关键接口

- `GET /api/instruments`
- `POST /api/instruments/sync`
- `GET /api/quote/{symbol}`
- `GET /api/kline/{symbol}`
- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{symbol}`
- `GET /api/watchlist/signals`
- `POST /api/analyze`
- `GET /api/settings`
- `GET /api/settings/runtime`
- `PUT /api/settings`
- `GET /api/replays`
- `POST /api/backtests`
- `GET /healthz`
- `GET /readyz`

## 重要说明

1. 股票和 ETF 的日内回转规则并不完全一致，系统已加入制度识别逻辑。
2. 股票的正T/反T默认按“底仓做T”理解，分析页可填写 `底仓数量` 与 `可卖数量`。
3. 免费数据下“盘口增强”使用的是近似估计；如果你后续接入逐笔或五档盘口源，可以直接替换数据服务。
4. 行业板块联动当前使用“板块代理 / 市场代理”方案，后续可扩展为真实行业映射。
5. 本系统仅用于研究与辅助决策，不构成投资建议。

## 部署方式

### Vercel 预览部署

项目根目录已经包含：

- `vercel.json`
- `api/index.py`
- `requirements.txt`

部署后：

- 前端静态资源由 Vercel 直接托管
- FastAPI 通过 `api/[...path].py` 统一挂载在 `/api/*`
- 预览环境默认使用 `/tmp/t_quant.db`，首次冷启动会从 `backend/data/t_quant.db` 复制种子数据库

如果要长期在线使用，建议在系统配置或环境变量中改成外部数据库。

### Docker 持久部署

项目根目录已经提供：

- `Dockerfile`
- `.dockerignore`
- `docker-compose.sqlite.yml`
- `docker-compose.mysql.yml`
- `.env.docker.example`

#### 方案 A：SQLite 单容器

默认保留 SQLite，适合单机或轻量云主机：

```bash
cp .env.docker.example .env
APP_PORT=18080 docker compose -f docker-compose.sqlite.yml up -d --build
```

特点：

- 后端统一托管前端静态资源
- SQLite 数据持久化到 Docker volume
- Compose 项目名固定为 `tquant-sqlite`，可与 MySQL 方案并行运行
- 默认访问 `http://127.0.0.1:18080`

#### 方案 B：MySQL 生产编排

适合更长期、更稳的持久部署：

```bash
cp .env.docker.example .env
APP_PORT=18090 docker compose -f docker-compose.mysql.yml up -d --build
```

特点：

- MySQL 8.4 独立持久化
- 应用容器自动连接 `mysql` 服务
- Web 容器默认只处理 HTTP 请求，低吸扫描、预热、归档和模拟盘自动交易由 `runtime-worker` 单独执行，避免多 Gunicorn worker 重复跑后台任务
- 回测任务由 `backtest-worker` 独立消费，避免长任务阻塞 Web 请求
- Compose 项目名固定为 `tquant-mysql`，可与 SQLite 方案并行运行
- 更适合云端长期运行

部署前建议先执行：

```bash
./scripts/prod_preflight.sh
```

## Navicat / MySQL 生产化

如果你要“使用本地 Navicat”，正确的落地方式是：

- 本机运行 `MySQL / MariaDB`
- 用 `Navicat` 管理数据库
- 在系统配置页填写 MySQL 连接串

推荐连接串：

```text
mysql+pymysql://root:你的密码@127.0.0.1:3306/t_quant?charset=utf8mb4
```

系统已经支持：

- 数据库连接检测
- 从 SQLite 迁移到 MySQL
- 把目标数据库写入 `backend/data/runtime.env`
- 后端重启后自动切换到新的数据库

详细步骤见：

- [生产化手册](./PRODUCTION_RUNBOOK.md)

## 一键公网发布脚本

项目根目录已提供：

- `scripts/run_public_app.sh`
- `scripts/stop_public_app.sh`
- `scripts/run_local_prod.sh`
- `scripts/prod_preflight.sh`
- `scripts/runtime_snapshot.sh`
- `Makefile`

用途：

- `run_local_prod.sh`
  构建前端并以前台方式启动单端口生产模式
- `prod_preflight.sh`
  执行发布前预检查：前端构建、后端编译、API 冒烟、单端口页面验活
- `runtime_snapshot.sh`
  拉取当前实例的 `healthz / readyz / runtime diagnostics`
- `Makefile`
  收敛常用构建、预检、临时发布和 Docker 命令
- `run_public_app.sh`
  构建前端并启动后端，再建立临时公网隧道（优先 `localhost.run`，失败自动回退 `localtunnel`）
- `stop_public_app.sh`
  停止脚本方式启动的后台进程

公网脚本成功后会把访问地址写入：

- `.runtime/public_url.txt`
- `.runtime/tunnel_provider.txt`

## 当前验证情况

- 后端 Python 代码已通过编译级语法检查
- 前端 `npm run build` 已验证通过
- 全市场标的同步已验证通过，当前库内约 `6974` 个标的
- `POST /api/analyze` 与 `POST /api/backtests` 已完成本地真实链路验证
- `./scripts/qa_smoke.sh` 可执行端到端冒烟检查
- `./scripts/prod_preflight.sh` 可执行发布前单端口生产预检查
- 已补充 Docker 持久部署文件，可直接用于 SQLite / MySQL 两种生产形态

## 文档

- [多 Agent 编排](./AGENTS.md)
- [策略负责人手册](./TRADING_QUANT_LEAD_PLAYBOOK.md)
- [产品阶段验收清单](./PRODUCT_STAGE_ACCEPTANCE.md)
- [整体计划](./PROJECT_PLAN.md)
- [优化方案](./OPTIMIZATION_PLAN.md)
- [开发文档](./DEVELOPMENT_GUIDE.md)
