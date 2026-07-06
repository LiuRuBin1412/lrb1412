from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

app = FastAPI()

# 标准CORS配置，自动处理OPTIONS预检
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 根路由对应外部 /api/mcp 路径
@app.post("/")
async def test_post():
    return {"status": "ok", "message": "POST请求正常"}

handler = Mangum(app)
