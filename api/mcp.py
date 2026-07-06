from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from mangum import Mangum
import json
import requests

app = FastAPI()

# 统一跨域响应头，增加GET方法支持
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept",
    "Cache-Control": "no-store"
}

# 工具定义
TOOLS = [
    {
        "name": "stock_technical_indicators",
        "description": "获取A股个股技术指标，包含EMA12、EMA50均线，MACD全套，RSI14",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "6位股票代码，例如 000001"}
            },
            "required": ["symbol"]
        }
    }
]

# 获取日线前复权数据
def get_kline_data(symbol: str, count: int = 80):
    secid = f"1.{symbol}" if symbol.startswith("6") else f"0.{symbol}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "end": "20500101",
        "lmt": str(count)
    }
    resp = requests.get(url, params=params, timeout=3)
    resp.raise_for_status()
    data = resp.json()["data"]["klines"]
    dates, closes = [], []
    for line in data:
        parts = line.split(",")
        dates.append(parts[0])
        closes.append(float(parts[2]))
    return dates, closes

# 计算EMA
def calc_ema(prices, period):
    ema = [prices[0]]
    k = 2 / (period + 1)
    for p in prices[1:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return ema

# 计算MACD
def calc_macd(prices):
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    dif = [ema12[i] - ema26[i] for i in range(len(prices))]
    dea = calc_ema(dif, 9)
    bar = [2 * (dif[i] - dea[i]) for i in range(len(prices))]
    return dif, dea, bar

# 计算RSI14
def calc_rsi(prices, period=14):
    rsi = [None] * period
    for i in range(period, len(prices)):
        gains, losses = 0, 0
        for j in range(i - period + 1, i + 1):
            diff = prices[j] - prices[j-1]
            if diff > 0:
                gains += diff
            else:
                losses -= diff
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(round(100 - 100 / (1 + rs), 2))
    return rsi

# 包装SSE事件格式
def sse_event(data: dict):
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# 跨域预检
@app.options("/api/mcp")
async def cors_preflight():
    return Response(status_code=204, headers=CORS_HEADERS)

# MCP主入口：SSE流式响应
@app.post("/api/mcp")
async def mcp_stream_handler(request: Request):
    try:
        body = await request.json()
    except:
        return Response(
            content=json.dumps({"error": "Invalid JSON"}),
            media_type="application/json",
            headers=CORS_HEADERS,
            status_code=400
        )

    rpc_method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    # 通知类请求（无id）按规范返回202
    if req_id is None:
        return Response(status_code=202, headers=CORS_HEADERS)

    # 1. 初始化握手
    if rpc_method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "行情指标MCP", "version": "1.0.0"}
        }
        response = {"jsonrpc": "2.0", "id": req_id, "result": result}

    # 2. 工具列表
    elif rpc_method == "tools/list":
        response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    # 3. 工具调用
    elif rpc_method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        try:
            if tool_name == "stock_technical_indicators":
                symbol = args["symbol"]
                dates, closes = get_kline_data(symbol)
                e12 = calc_ema(closes, 12)
                e50 = calc_ema(closes, 50)
                dif, dea, bar = calc_macd(closes)
                rsi = calc_rsi(closes, 14)

                lines = ["日期 | 收盘价 | EMA12 | EMA50 | DIF | DEA | MACD柱 | RSI14"]
                lines.append("---|---|---|---|---|---|---|---")
                for i in range(-10, 0):
                    lines.append(
                        f"{dates[i]} | {round(closes[i],2)} | {round(e12[i],3)} | {round(e50[i],3)} | "
                        f"{round(dif[i],4)} | {round(dea[i],4)} | {round(bar[i],4)} | {rsi[i] if rsi[i] else '-'}"
                    )
                text = "\n".join(lines)
            else:
                text = "未知工具"

            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]}
            }
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": f"查询失败: {str(e)}"}]}
            }

    # 未知方法
    else:
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Method not found"}
        }

    # 以SSE流格式返回响应
    def event_generator():
        yield sse_event(response)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=CORS_HEADERS
    )

handler = Mangum(app)
