from fastapi import FastAPI, Request
from mangum import Mangum

app = FastAPI()

# 工具定义
TOOLS = [
    {
        "name": "index_realtime",
        "description": "获取上证指数、深证成指等A股主要指数的实时行情",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "stock_spot",
        "description": "获取单只A股的实时行情快照，输入6位股票代码",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "6位股票代码，例如 000001"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "stock_daily",
        "description": "获取A股个股日线历史行情（前复权）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "6位股票代码"},
                "start_date": {"type": "string", "description": "开始日期，格式 20250101"},
                "end_date": {"type": "string", "description": "结束日期，格式 20250630"}
            },
            "required": ["symbol", "start_date", "end_date"]
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
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "AKShare-MCP", "version": "1.0.0"}
            }
        }

    # 工具列表
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS}
        }

    # 工具调用（延迟导入 AKShare）
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        try:
            import akshare as ak

            if name == "index_realtime":
                df = ak.stock_zh_index_spot_em()
                text = df.head(10).to_markdown(index=False)

            elif name == "stock_spot":
                df = ak.stock_zh_a_spot_em()
                target = df[df["代码"] == args["symbol"]]
                text = target.to_markdown(index=False) if not target.empty else "未找到对应股票"

            elif name == "stock_daily":
                df = ak.stock_zh_a_hist(
                    symbol=args["symbol"],
                    period="daily",
                    start_date=args["start_date"],
                    end_date=args["end_date"],
                    adjust="qfq"
                )
                text = df.head(30).to_markdown(index=False)

            else:
                text = "未知工具"

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]}
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"查询失败: {str(e)}"}]}
            }

    # 心跳通知
    elif method == "notifications/initialized":
        return {}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "Method not found"}
    }

handler = Mangum(app)
