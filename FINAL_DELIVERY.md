# 最终交付说明

## 1. 当前可用实例

- 推荐主实例（MySQL 持久化）：`http://127.0.0.1:18090`
- 演示实例（SQLite 开箱即用）：`http://127.0.0.1:18080`

## 2. 已完成能力

- A 股股票与 ETF 全市场标的同步
- 自选股实时监控
- 日内正T / 反T 智能建议
- 最低目标盈利阈值可配置，默认 `3%`
- 风控参数、策略护栏、滑点参数开放配置
- 大模型配置持久化保存
- 数据库配置持久化保存
- SQLite / MySQL 双部署形态
- 研究复盘与 Walk-forward 回测

## 3. 配置持久化

- 设置页保存后，配置会同时写入系统数据库
- 同时写入运行时覆盖文件：`backend/data/runtime.env`
- 后端重启后会自动恢复最近一次保存的模型、数据库和数据源配置

## 4. 已通过验证

- 前端生产构建
- 后端编译检查
- 接口与策略冒烟
- 研究回测接口验证
- SQLite 实例健康检查
- MySQL 实例健康检查
- 浏览器级 UI 冒烟

## 5. 常用命令

```bash
make qa
make ui-smoke
make docker-sqlite-up
make docker-mysql-up
./scripts/runtime_snapshot.sh http://127.0.0.1:18090
```

## 6. 建议使用方式

- 日常使用优先进入 `18090` MySQL 实例
- 若需填写 AI，进入系统配置页补充 `API Key / Base URL / Model`
- 若只做量化研究，不配 AI 也可以正常运行

