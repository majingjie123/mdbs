# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## MDBS 简介

基于 FastAPI + Vue 3 的现代 Web 数据库管理工具，通过 pywebview 封装为 Windows 桌面应用。支持 MySQL/MariaDB 和 PostgreSQL 连接（含 SSH 隧道）、SQL 编辑、数据同步/导出/导入、备份恢复及 AI 智能助手。

## 常用命令

```bash
# 后端 (Python 3.7+)
cd backend && pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 18081 --reload

# 前端 (Node.js 18+)
cd frontend && npm install
npm run dev        # 开发服务器 :5173 (代理 API 到 :18081)
npm run build      # 类型检查 + 生产构建 → frontend/dist/

# 打包独立 Windows exe
cd frontend && npm run build
cd .. && python scripts/build_backend_exe.py
# 输出: dist/mdbs-server/mdbs-server.exe
```

## 架构

```
root/
├── backend/           # FastAPI + Uvicorn (Python)
│   ├── main.py        # 应用入口，SPA 静态文件托管
│   ├── dependencies.py# 依赖注入: get_db_storage / get_db_ops
│   ├── schemas.py     # Pydantic 模型
│   ├── routers/       # API 路由 (connections, databases, tables, query, sync, ai...)
│   ├── core/          # 业务逻辑 (db_operations, ssh_manager, syncer, exporter, ai/)
│   ├── models/        # SQLite 持久化层
│   └── utils/crypto.py# AES (Fernet) 加密
├── frontend/          # Vue 3 + TypeScript + Vite + Naive UI
│   └── src/
│       ├── api/index.ts    # Axios 实例 + 所有 API 方法
│       ├── stores/app.ts   # Pinia 状态管理
│       ├── router/index.ts # Hash 路由
│       ├── views/          # 页面组件
│       └── components/     # 通用组件、对话框
├── scripts/           # run_backend.py, build_backend_exe.py
└── README.md          # 完整文档
```

## 关键模式与约定

- **API 响应格式**: 统一返回 `{"success": bool, "data": ..., "message": "..."}`
- **前端 API 调用**: 通过 `src/api/index.ts` 的 `api` 对象，不要直接使用 axios
- **UI 组件**: 只使用 Naive UI，不引入其他 UI 库
- **状态管理**: Pinia store 位于 `src/stores/app.ts`
- **SSH 隧道清理**: 更新或删除连接前必须先调用 `SSHTunnelManager().stop_tunnel(conn_id)`
- **凭证加密**: 所有密码和 SSH 私钥口令必须用 `CryptoUtils.encrypt()` 加密后存储，严禁明文记录
- **PostgreSQL schema**: 通过 `req.schema_name` 传入，MySQL 忽略此参数
- **请求体嵌套**: 后端 `ConnectionCreate`/`ConnectionUpdate` 接收 `{ data: ConnData }` 格式，前端发送 `{ data: payload }`
- **路由文件**: FastAPI 路由在 `backend/routers/` 下，Pydantic 模型在 `backend/schemas.py`

## 开发说明

- 项目目前没有测试、lint 或格式化工具
- TypeScript 严格性仅在 `npm run build` 时通过 `vue-tsc` 检查
- 后端端口 18081，Vite 开发服务器端口 5173
- 调试日志位于 `%USERPROFILE%\mdbs_debug.log`
- 详细开发规范请参考 `AGENTS.md`

## 已知陷阱

| 陷阱 | 说明 |
|------|------|
| pywebview maximized | pywebview 6.x 的 `start()` 不支持 `maximized`，改为 `create_window(maximized=True)` + `start(webview.start())` |
| 请求体嵌套 | 后端 `ConnectionCreate`/`ConnectionUpdate` 接收 `{ data: ConnData }` 嵌套格式 |
| SSH 隧道释放 | 更新/删除连接前必须先调用 `SSHTunnelManager().stop_tunnel(conn_id)` |
| PostgreSQL schema | PostgreSQL 的 schema 参数需单独从 `req.schema_name` 获取，MySQL 忽略 |