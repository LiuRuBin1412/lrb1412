import os
from fastapi import FastAPI, Request, HTTPException
from fastmcp import FastMCP
from mangum import Mangum
import akshare as ak

# 从环境变量读取密钥，未设置则不鉴权（测试用）
API_KEY = os.getenv("MCP_API_KEY")

app = FastAPI()
mcp = FastMCP("AKShare金融数据")

# 鉴权中间件
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if API_KEY:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth.split(" ")[1] != API_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return await call_next(request)

# 工具1：个股日线行情
@mcp.tool(description="获取A股个股日线历史行情，前复权")
def stock_daily(symbol: str, start_date: str, end_date: str) -> str:
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start_date, end_date=end_date, adjust="qfq"
        )
        return df.head(30).to_markdown(index=False)
    except Exception as e:
        return f"查询失败: {str(e)}"

# 工具2：主要指数实时行情
@mcp.tool(description="获取上证指数、深证成指等主要指数实时行情")
def index_realtime() -> str:
    try:
        df = ak.stock_zh_index_spot_em()
        return df.to_markdown(index=False)
    except Exception as e:
        return f"查询失败: {str(e)}"

# 工具3：个股实时快照
@mcp.tool(description="获取单只股票实时行情数据")
def stock_spot(symbol: str) -> str:
    try:
        df = ak.stock_zh_a_spot_em()
        target = df[df["代码"] == symbol]
        return target.to_markdown(index=False)
    except Exception as e:
        return f"查询失败: {str(e)}"

# 挂载 MCP 服务
app.mount("/", mcp.streamable_http_app())

# Vercel 入口
handler = Mangum(app)
