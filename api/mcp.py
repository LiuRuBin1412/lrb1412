from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# 变量名必须是 app，Vercel自动识别为ASGI入口
app = FastAPI(redirect_slashes=False)

# 标准CORS中间件，自动处理OPTIONS预检请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内部根路由 对应外部访问路径 /api/mcp
@app.post("/")
async def test_post(request: Request):
    body = await request.json()
    return {"status": "ok", "received": body}
