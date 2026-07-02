from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from mangum import Mangum
import requests

app = FastAPI()

# 关键修复：全开跨域，处理OPTIONS预检请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mcp = FastMCP("行情指标MCP")

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

# 注册工具
@mcp.tool(description="获取A股个股技术指标，包含EMA12、EMA50均线，MACD全套，RSI14")
def stock_technical_indicators(symbol: str) -> str:
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
    return "\n".join(lines)

# 挂载MCP流式服务到根路径，适配Vercel路由
app.mount("/", mcp.streamable_http_app())

# Vercel 入口
handler = Mangum(app)
