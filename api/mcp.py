from fastmcp import FastMCP
from mangum import Mangum
import akshare as ak

mcp = FastMCP("AKShare金融数据")

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

# 直接生成 ASGI 应用并交给 Mangum 适配 Vercel
app = mcp.streamable_http_app()
handler = Mangum(app)
