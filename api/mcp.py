from fastapi import FastAPI, Request, Response
from mangum import Mangum

app = FastAPI()

# 统一跨域响应头
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept",
    "Cache-Control": "no-store"
}

# 显式处理OPTIONS跨域预检，彻底避免404
@app.options("/")
async def cors_preflight():
    return Response(status_code=204, headers=CORS_HEADERS)

# POST业务路由，对应外部路径 /api/mcp
@app.post("/")
async def handle_post(request: Request):
    try:
        body = await request.json()
    except:
        body = "invalid json"
    return Response(
        content='{"status": "ok", "echo": ' + repr(body) + '}',
        media_type="application/json",
        headers=CORS_HEADERS
    )

# Vercel标准入口：必须导出handler变量
handler = Mangum(app)
