# MDBS — AI 代理开发指南

> 本文件为 AI 编码助手（如 AtomCode）提供开发 MDBS 项目所需的上下文和约束。
> 用户可见的项目说明请在 `README.md` 中查找。

---

## 项目概述

MDBS 是一款 **FastAPI + Vue 3** 数据库管理桌面工具（通过 pywebview 封装为 Windows EXE），支持 SSH 隧道连接 MySQL/MariaDB 和 PostgreSQL。

---

## 架构速览

```
root/
├── backend/           # FastAPI + Uvicorn
│   ├── main.py        # 入口 + SPA 静态文件托管
│   ├── dependencies.py# 依赖注入 (DBStorage / DBOperations)
│   ├── schemas.py     # Pydantic 模型
│   ├── core/          # 业务逻辑 (db_operations, ssh_manager, syncer, exporter, etc.)
│   ├── models/        # SQLite 持久化层
│   ├── routers/       # API 路由 (connections, databases, tables, query, sync, ai...)
│   └── utils/         # 工具 (crypto.py — AES 加密)
├── frontend/          # Vue 3 + TypeScript + Vite + Naive UI
│   └── src/
│       ├── api/index.ts     # Axios 实例 + 所有 API 方法
│       ├── stores/app.ts    # Pinia 状态 (连接/标签页/主题)
│       ├── router/index.ts  # Hash 路由
│       ├── views/           # 页面
│       └── components/      # 布局/通用组件/dialogs
├── scripts/
│   ├── run_backend.py       # 生产模式启动
│   └── build_backend_exe.py # PyInstaller 构建
└── README.md          # 完整文档
```

---

## 开发规范

### API 开发

- FastAPI 路由统一在 `routers/` 下，Pydantic 模型在 `schemas.py`
- 统一返回格式：`{"success": bool, "data": ..., "message": "..."}`
- 连接信息通过 `dependencies.py` 的 `get_db_storage` / `get_db_ops` 注入
- 错误使用 `raise HTTPException` 或返回 `{"success": false, "message": str(e)}`

### 前端开发

- 使用 Vue 3 Composition API: `<script setup lang="ts">`
- **Naive UI** 组件库，不要引入其他 UI 库
- API 调用通过 `src/api/index.ts` 的 `api` 对象，不要直接使用 axios
- TypeScript 类型安全，`any` 仅在 API 响应类型不确定时使用

### 安全约束

- 所有密码/私钥 passphrase 必须用 `CryptoUtils.encrypt()` 加密后存储
- 日志中**严禁**明文打印密码或密钥
- SSH 私钥路径也必须加密存储

---

## 常见代码模式

### 新增 API 路由

```python
# backend/routers/xxx.py
from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage
from ..schemas import SomeModel

router = APIRouter(prefix="/api/xxx", tags=["标签"])

@router.post("/action")
def some_action(req: SomeModel, storage=Depends(get_db_storage)):
    try:
        # ...
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": str(e)}
```

### 新增前端 API 方法

```typescript
// frontend/src/api/index.ts
export const api = {
  // ...
  newAction: (params: SomeType) =>
    http.post('/api/xxx/action', params) as Promise<ApiResponse<ResultType>>,
}
```

### 新增对话框组件

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api'

const props = defineProps<{ ... }>()
const emit = defineEmits<{ (e: 'close'): void }>()
</script>
```

---

## 已知陷阱

| 陷阱 | 说明 |
|------|------|
| `pywebview` `maximized` 参数 | pywebview 6.x 的 `start()` 不支持 `maximized`，改为 `create_window(maximized=True)` + `start(webview.start())` |
| 请求体嵌套 | 后端 `ConnectionCreate` / `ConnectionUpdate` 接收 `{ data: ConnData }` 嵌套格式，前端发请求时需 `{ data: payload }` |
| SSH 隧道释放 | 更新/删除连接前必须先调用 `SSHTunnelManager().stop_tunnel(conn_id)` |
| PostgreSQL schema | PostgreSQL 的 schema 参数需单独从 `req.schema_name` 获取，MySQL 忽略 |
| vite.config.ts 端口 | 开发服务器用 5173（已从 3000 改为 5173 避免冲突） |
