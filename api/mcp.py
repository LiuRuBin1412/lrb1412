import json
import requests

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

# 包装标准SSE事件格式
def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# 行情数据获取
def get_kline_data(symbol: str, count: int = 80):
    secid = f"1.{symbol}" if symbol.startswith("6") else f"0.{symbol}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1",
        "fields2": "f51,f52,f53",
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

# 指标计算
def calc_ema(prices, period):
    ema = [prices[0]]
    k = 2 / (period + 1)
    for p in prices[1:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return ema

def calc_macd(prices):
    e12 = calc_ema(prices, 12)
    e26 = calc_ema(prices, 26)
    dif = [e12[i] - e26[i] for i in range(len(prices))]
    dea = calc_ema(dif, 9)
    bar = [2 * (dif[i] - dea[i]) for i in range(len(prices))]
    return dif, dea, bar

def calc_rsi(prices, period=14):
    rsi = [None] * period
    for i in range(period, len(prices)):
        gains, losses = 0.0, 0.0
        for j in range(i - period + 1, i + 1):
            diff = prices[j] - prices[j-1]
            if diff > 0:
                gains += diff
            else:
                losses += abs(diff)
        avg_g, avg_l = gains / period, losses / period
        if avg_l == 0:
            rsi.append(100.0)
        else:
            rsi.append(round(100 - 100 / (1 + avg_g / avg_l), 2))
    return rsi

# Vercel 原生入口函数（无任何框架）
def handler(event, context):
    http_method = event.get("httpMethod", "POST")
    # 统一基础响应头
    base_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Accept",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }

    # 1. 处理跨域预检请求
    if http_method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": base_headers,
            "body": ""
        }

    # 2. 仅允许POST请求
    if http_method != "POST":
        return {
            "statusCode": 405,
            "headers": base_headers,
            "body": json.dumps({"detail": "Method Not Allowed"})
        }

    # 3. 解析JSON请求体
    try:
        body = json.loads(event.get("body", "{}"))
    except:
        return {
            "statusCode": 400,
            "headers": {**base_headers, "Content-Type": "text/event-stream"},
            "body": sse({"error": "Invalid JSON"})
        }

    rpc_method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    # 4. 无id的通知类请求，返回空SSE事件
    if req_id is None:
        return {
            "statusCode": 200,
            "headers": {**base_headers, "Content-Type": "text/event-stream"},
            "body": sse({})
        }

    # 5. 处理MCP核心方法
    if rpc_method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "stock-mcp", "version": "1.0.0"}
        }
        rpc_resp = {"jsonrpc": "2.0", "id": req_id, "result": result}

    elif rpc_method == "tools/list":
        rpc_resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

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
            rpc_resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            rpc_resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": f"查询失败: {str(e)}"}]}}

    else:
        rpc_resp = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Method not found"}
        }

    # 6. 以标准SSE格式返回
    return {
        "statusCode": 200,
        "headers": {**base_headers, "Content-Type": "text/event-stream"},
        "body": sse(rpc_resp)
    }
