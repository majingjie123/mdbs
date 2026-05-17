"""MDBS FastAPI 后端入口

启动命令::
    cd backend && uvicorn main:app --host 127.0.0.1 --port 18080 --reload
"""

import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保能找到项目根目录下的 core / models / utils
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from routers import connections, databases, tables, query

app = FastAPI(
    title="MDBS API",
    description="数据库连接管理工具 - 后端 API",
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


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
