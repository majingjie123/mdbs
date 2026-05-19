"""MDBS FastAPI 后端入口

启动命令::
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 18081 --reload

生产部署 (打包后):
    run_backend.py  (自动加载同目录下的 frontend/dist 静态文件)
"""

import sys
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# core / models / utils 现在位于 backend/ 下
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from .routers import connections, databases, tables, query, backup, export, import_routes  # type: ignore[import-not-found]
from .routers import sync as sync_router  # type: ignore[import-not-found]
from .routers import ai as ai_router  # type: ignore[import-not-found]

app = FastAPI(
    title="MDBS",
    description="数据库连接管理工具",
    version="1.0.0",
)

# CORS —— 允许 Vue 开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(connections.router)
app.include_router(databases.router)
app.include_router(tables.router)
app.include_router(query.router)
app.include_router(backup.router)
app.include_router(export.router)
app.include_router(import_routes.router)
app.include_router(ai_router.router)
app.include_router(sync_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# 挂载 Vue ️  Vue 前端静态文件托管 (生产模式)
# ---------------------------------------------------------------------------
def _get_frontend_dist() -> Path:
    """定位 Vue 构建产物 frontend/dist 的路径。

    优先级:
      1. 环境变量 MDBS_FRONTEND_DIST (由 run_backend.py 设置)
      2. PyInstaller 打包后的临时目录 (sys._MEIPASS)
      3. 项目根目录下的 frontend/dist
    """
    env_dist = os.environ.get("MDBS_FRONTEND_DIST")
    if env_dist:
        return Path(env_dist)

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "frontend" / "dist"

    # 开发模式：相对于 backend/main.py 的兄弟目录
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


_frontend_dist = _get_frontend_dist()
# ---------------------------------------------------------------------------
# SPA 回退中间件：非 API 路径的 404 响应 → 返回 index.html
# ---------------------------------------------------------------------------
from fastapi.responses import JSONResponse

if _frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.middleware("http")
    async def spa_fallback(request, call_next):
        response = await call_next(request)
        if response.status_code == 404 and not request.url.path.startswith("/api"):
            index_file = _frontend_dist / "index.html"
            if index_file.exists():
                from fastapi.responses import FileResponse
                return FileResponse(str(index_file))
        return response
else:
    print(f"[MDBS] 前端静态目录不存在: {_frontend_dist}，仅 API 模式运行。")
