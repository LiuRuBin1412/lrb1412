import json
from fastapi import FastAPI, Request
from mangum import Mangum

app = FastAPI()

# MCP 工具定义
TOOLS = [
    {
        "name": "add",
        "description": "加法测试工具，计算两个整数的和",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"}
            },
            "required": ["a", "b"]
        }
    }
]

@app.post("/api/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    # 初始化握手
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "AKShare-MCP",
                    "version": "1.0.0"
                }
            }
        }

    # 工具列表
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        }

    # 工具调用
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        if name == "add":
            result = args["a"] + args["b"]
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(result)}]
                }
            }

    # 心跳
    elif method == "notifications/initialized":
        return {}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": "Method not found"
        }
    }

handler = Mangum(app)
