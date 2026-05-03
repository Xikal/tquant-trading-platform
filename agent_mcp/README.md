# Agent MCP Server

提供标准 stdio MCP 入口。工具定义来自后端 `Tool Registry`，执行时只调用 `/api/agent/*`，不访问数据库、不 import 业务 service。

启动：

```bash
AGENT_API_BASE=http://127.0.0.1:18090/api \
AGENT_API_TOKEN=your-agent-token \
python agent_mcp/server.py
```

注册到 Hermes：

```bash
hermes mcp add weis-quant \
  --command /Users/j/Documents/gupiao/backend/.venv/bin/python \
  --env AGENT_API_BASE=http://127.0.0.1:18090/api \
  --env AGENT_API_TOKEN=your-agent-token \
  --env AGENT_TIMEOUT_SECONDS=10 \
  --args /Users/j/Documents/gupiao/agent_mcp/server.py
```

JSON-RPC 输入示例：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_priority_board","arguments":{"limit":12}}}
```

为了保留调试便利，仍兼容旧 JSONL 输入：

```json
{"method":"tools/list"}
{"tool_name":"get_priority_board","arguments":{"limit":12}}
```
