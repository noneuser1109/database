from fastapi import Request
from fastapi.responses import JSONResponse
from backend_app.app import app

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # 这里可以统一记录日志 (Logging)
    print(f"全局捕获到异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后再试", "error_type": type(exc).__name__},
    )