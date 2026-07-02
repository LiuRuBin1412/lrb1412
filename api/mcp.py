import json
from http.server import BaseHTTPRequestHandler
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

# 获取日线前复权数据
def get_kline_data(symbol: str, count: int = 80):
    secid = f"1.{symbol}" if symbol.startswith("6") else f"0.{symbol}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1",
        "fields2": "f51,f52,f53",
        "klt": "101",
        "fqt": "1",
        "lmt": str(count),
        "end": "20500101"
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
    ef = calc_ema(prices, 12)
    es = calc_ema(prices, 26)
    dif = [ef[i]-es[i] for i in range(len(prices))]
    dea = calc_ema(dif, 9)
    bar = [2*(dif[i]-dea[i]) for i in range(len(prices))]
    return dif, dea, bar

# 计算RSI14
def calc_rsi(prices, period=14):
    rsi = [None]*period
    for i in range(period, len(prices)):
        gains, losses = 0.0, 0.0
        for j in range(i-period+1, i+1):
            diff = prices[j]-prices[j-1]
            if diff > 0:
                gains += diff
            else:
                losses += abs(diff)
        avg_g = gains / period
        avg_l = losses / period
        if avg_l == 0:
            rsi.append(100.0)
        else:
            rsi.append(round(100 - 100/(1 + avg_g/avg_l), 2))
    return rsi

# Vercel 原生入口
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            msg = json.loads(body)
        except:
            self.send_error(400)
            return

        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params", {})

        # 通知类请求（无id）：严格按规范返回 202 Accepted，无响应体
        if req_id is None:
            self.send_response(202)
            self.end_headers()
            return

        # 1. 初始化握手
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "行情指标MCP", "version": "2.0.0"}
            }
            self._send_json_result(req_id, result)

        # 2. 工具列表
        elif method == "tools/list":
            self._send_json_result(req_id, {"tools": TOOLS})

        # 3. 工具调用
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            try:
                if name == "stock_technical_indicators":
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

                self._send_json_result(req_id, {"content": [{"type": "text", "text": text}]})
            except Exception as e:
                self._send_json_result(req_id, {"content": [{"type": "text", "text": f"查询失败: {str(e)}"}]})

        # 未知方法
        else:
            self._send_json_error(req_id, -32601, "Method not found")

    def _send_json_result(self, req_id, result):
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json_error(self, req_id, code, message):
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message}
        }
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # 禁用默认日志输出，减少耗时
    def log_message(self, format, *args):
        return
