# Agent MCP Server

第一阶段提供轻量 MCP 兼容入口：工具定义来自后端 `Tool Registry`，执行时只调用 `/api/agent/*`，不访问数据库、不 import 业务 service。

启动：

```bash
AGENT_API_BASE=http://127.0.0.1:18090/api python agent_mcp/server.py
```

标准输入示例：

```json
{"method":"tools/list"}
{"tool_name":"get_priority_board","arguments":{"limit":12}}
```

后续如引入正式 MCP SDK，只需要替换传输层，工具定义仍从 `Tool Registry` 读取。
