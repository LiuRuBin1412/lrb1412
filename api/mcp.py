from fastapi import FastAPI, Request
from mangum import Mangum

app = FastAPI()

# 匹配所有路径、所有HTTP方法，返回真实的请求信息
@app.api_route("/{full_path:path}", methods=["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH"])
async def debug_all_requests(request: Request, full_path: str):
    return {
        "http_method": request.method,
        "actual_path": request.url.path,
        "matched_path_param": full_path
    }

handler = Mangum(app)
