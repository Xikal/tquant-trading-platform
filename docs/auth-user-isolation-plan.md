# 登录系统与用户数据隔离 V1 方案

## V1 目标

第一个版本只解决一个核心问题：登录后，App 和 Web 调用同一套后端服务，但用户只能读写自己的自选、持仓、策略配置、提醒和复盘数据。

市场行情、日线历史、全量扫描缓存、策略公共结果继续全局共享，不按用户复制，避免性能和存储成本暴涨。

## 推荐架构

```text
Android App / Web
        |
        | Authorization: Bearer access_token
        v
FastAPI Backend
        |
        | 解析 token -> current_user
        v
业务接口统一带 user_id 过滤
        |
        v
MySQL
```

## 核心设计

| 模块 | V1 设计 |
|---|---|
| 登录方式 | 手机号或用户名 + 密码 |
| 鉴权方式 | JWT Access Token + Refresh Token |
| 用户隔离 | 用户私有表全部加 `user_id` |
| 公共数据 | 行情、日线、策略全量缓存继续共享 |
| App / Web | 共用同一套后端 API |
| 权限 | V1 只有普通用户，不做复杂角色 |
| 安全 | 密码哈希存储，不存明文密码 |

## 数据库表设计

新增用户相关表：

| 表 | 用途 |
|---|---|
| `users` | 用户账号 |
| `user_sessions` | Refresh Token 与登录设备 |
| `user_watchlists` | 用户自选股 |
| `user_positions` | 用户持仓 |
| `user_strategy_settings` | 用户策略偏好 |
| `user_alerts` | 用户提醒 |
| `user_review_notes` | 用户复盘记录，后续可扩展 |

继续全局共享的公共数据：

| 数据 | 处理方式 |
|---|---|
| A 股日线历史 | 全局共享 |
| 实时行情缓存 | 全局共享 |
| 低吸全量扫描结果 | 全局共享 |
| 策略绩效统计 | 全局共享，后续可扩展用户自定义统计 |

## API 设计

认证接口：

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me
```

用户隔离接口示例：

```text
GET    /api/app/home
GET    /api/watchlist
POST   /api/watchlist
DELETE /api/watchlist/{symbol}

GET    /api/positions
POST   /api/positions
PATCH  /api/positions/{id}
DELETE /api/positions/{id}

GET    /api/user/strategy-settings
PATCH  /api/user/strategy-settings
```

关键规则：所有用户私有接口都必须从 token 中解析 `user_id`，不能允许前端传入 `user_id` 决定数据归属。

## V1 排期

如果只做用户隔离，不做复杂会员、支付、短信验证码：

| 阶段 | 内容 | 预计时间 |
|---|---|---:|
| 第 1 步 | 数据表、用户模型、密码哈希、JWT | 0.5 天 |
| 第 2 步 | 登录、注册、刷新 token、`me` 接口 | 0.5 天 |
| 第 3 步 | 自选、持仓、策略配置按 `user_id` 隔离 | 1 天 |
| 第 4 步 | App / Web 请求头接入 Bearer Token | 0.5-1 天 |
| 第 5 步 | 回归测试、越权测试、部署 | 0.5-1 天 |

合理排期：3-4 天。

如果增加短信验证码、设备管理、找回密码、后台用户管理，排期约 6-8 天。

## V1 明确不做

- 不做短信验证码。
- 不做微信、苹果登录。
- 不做会员系统。
- 不做复杂 RBAC 权限。
- 不做每个用户单独跑全量策略扫描。

## V1 必做

- 账号密码登录。
- App / Web 共用 Bearer Token。
- 自选、持仓、策略配置、提醒严格按用户隔离。
- 行情和策略全局结果共享，用户只保存自己的操作数据。

## 验收标准

- 未登录请求用户私有接口必须返回 `401`。
- 用户 A 无法读取、修改、删除用户 B 的自选、持仓、策略配置和提醒。
- 前端不能通过传 `user_id` 越权访问其他用户数据。
- App 和 Web 使用同一套认证方式和同一套后端接口。
- 公共行情、策略缓存、全量扫描结果不因用户增加而重复计算。
