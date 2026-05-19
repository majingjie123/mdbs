# MDBS - 智能数据库连接管理工具

## 项目概述

**MDBS** 是一款基于 **FastAPI + Vue 3** 构建的现代 Web 数据库管理工具，专为需要通过 SSH 隧道安全访问远程 MySQL/MariaDB 和 PostgreSQL 数据库的开发者和 DBA 设计。该工具集成了 SQL 编辑器、表结构管理、数据同步、可视化导出和 AI 智能助手等核心功能。

### 技术栈

| 层级          | 技术/库                                    |
| ----------- | --------------------------------------- |
| **后端框架**    | FastAPI (Uvicorn)                       |
| **前端框架**    | Vue 3 + TypeScript + Vite               |
| **UI 组件库**  | Naive UI                                |
| **状态管理**    | Pinia                                   |
| **路由**      | Vue Router (Hash 模式)                    |
| **SQL 编辑器** | CodeMirror 6 + vue-codemirror           |
| **数据库驱动**   | pymysql (MySQL), pg8000 (PostgreSQL)    |
| **SSH 隧道**  | sshtunnel, paramiko                     |
| **AI 集成**   | openai >= 1.0.0                         |
| **数据导出**    | openpyxl (Excel), fpdf2 (PDF), sqlparse |
| **加密**      | cryptography (Fernet AES)               |
| **打包**      | PyInstaller (后端 Server EXE)             |

---

## 项目架构

```
DBConnectorManager/
├── backend/                    # FastAPI 后端服务
│   ├── main.py                 # FastAPI 应用入口 (含 SPA 静态文件托管)
│   ├── dependencies.py         # 依赖注入 (连接会话管理)
│   ├── schemas.py              # Pydantic 请求/响应模型
│   ├── requirements.txt        # Python 依赖清单
│   ├── core/                   # 核心业务逻辑层
│   │   ├── db_operations.py    # 数据库连接池与 CRUD 操作
│   │   ├── ssh_manager.py      # SSH 隧道生命周期管理
│   │   ├── exporter.py         # 多格式导出引擎 (Excel/PDF/HTML/Markdown/CSV/Navicat)
│   │   ├── importer.py         # SQL/CSV 数据导入引擎
│   │   ├── syncer.py           # 跨库同步核心逻辑
│   │   ├── metadata_cache.py   # 库表元数据缓存
│   │   ├── backup_manager.py   # 备份/恢复管理
│   │   └── ai/                 # AI 智能助手模块
│   │       ├── client.py       # OpenAI 协议兼容客户端 (支持流式)
│   │       ├── context_builder.py # 数据库上下文提取
│   │       └── markdown_renderer.py # AI 回复 Markdown 渲染
│   ├── models/                 # 数据访问层
│   │   ├── db_storage.py       # SQLite 持久化 (连接/设置/历史)
│   │   └── sync_history.py     # 同步任务日志管理
│   ├── routers/                # API 路由
│   │   ├── connections.py      # 连接管理 API
│   │   ├── databases.py        # 数据库管理 API
│   │   ├── tables.py           # 表结构管理 API
│   │   ├── query.py            # SQL 查询执行 API
│   │   ├── queries.py          # 保存的查询 CRUD API
│   │   ├── backup.py           # 备份/恢复 API
│   │   ├── export.py           # 数据导出 API
│   │   ├── import_routes.py    # 数据导入 API
│   │   ├── sync.py             # 同步管理 API
│   │   └── ai.py               # AI 对话 API (SSE 流式)
│   └── utils/                  # 通用工具
│       └── crypto.py           # 安全加密模块 (AES-256)
├── frontend/                   # Vue 3 前端 SPA
│   ├── index.html              # HTML 入口
│   ├── vite.config.ts          # Vite 构建配置
│   ├── package.json            # Node 依赖清单
│   ├── tsconfig.json           # TypeScript 配置
│   └── src/                    # 源码目录
│       ├── main.ts             # Vue 应用入口
│       ├── App.vue             # 根组件 (Naive UI 全局配置)
│       ├── env.d.ts            # 类型声明
│       ├── api/                # API 请求层 (Axios)
│       │   └── index.ts
│       ├── components/         # 组件
│       │   ├── AppLayout.vue   # 主布局 (侧边栏 + 内容区)
│       │   ├── Sidebar.vue     # 侧边导航栏
│       │   ├── SqlEditor.vue   # CodeMirror SQL 编辑器
│       │   ├── TabWorkspace.vue # 标签页工作区
│       │   └── dialogs/        # 对话框组件
│       │       ├── BackupDialog.vue
│       │       ├── ExportDialog.vue
│       │       ├── ImportDialog.vue
│       │       ├── SyncDialog.vue
│       │       └── SyncProgressDialog.vue
│       ├── router/             # 路由配置
│       │   └── index.ts
│       ├── stores/             # Pinia 状态管理
│       │   └── app.ts
│       └── views/              # 页面视图
│           ├── ConnectionList.vue    # 连接列表
│           ├── ConnectionDetail.vue  # 连接详情/编辑
│           ├── SQLWorkbench.vue      # SQL 工作台
│           ├── TableBrowser.vue      # 表结构浏览
│           ├── AIChat.vue            # AI 对话
│           ├── AISettingsPage.vue    # AI 设置
│           └── SettingsPage.vue      # 全局设置
├── scripts/                    # 构建/运行脚本
│   ├── run_backend.py          # 开发启动脚本 (生产模式加载前端静态文件)
│   └── build_backend_exe.py    # PyInstaller 打包为独立 EXE
├── icon.ico                    # 应用图标
├── sync_logs/                  # 同步日志目录
├── connections.db              # SQLite 数据库 (自动生成)
└── secret.key                  # AES 加密根密钥 (自动生成)
```

---

## 快速开始

### 环境要求

- Python 3.7+
- Node.js 18+ (仅前端开发时需要)
- Windows 10/11 (64 位推荐)

### 开发模式运行

```bash
# 1. 后端启动
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 18081 --reload

# 2. 前端启动 (新终端)
cd frontend
npm install
npm run dev

# 访问: http://localhost:5173 (Vite 开发服务器自动代理 API 到 18081)
```

### 生产模式运行 (后端打包前端静态文件)

```bash
# 1. 构建前端
cd frontend
npm run build

# 2. 启动后端 (自动加载 frontend/dist)
cd ..
python scripts/run_backend.py

# 访问: http://127.0.0.1:18081/
```

### 打包为独立 EXE

```bash
python scripts/build_backend_exe.py
# 输出: dist/mdbs-server/
```

### 数据存储

| 文件/目录            | 说明                                    |
| ---------------- | ------------------------------------- |
| `connections.db` | SQLite 数据库，存储连接配置、SQL 历史、同步日志 (密码已加密) |
| `secret.key`     | 本地唯一根密钥 (AES Fernet)                  |
| `sync_logs/`     | 同步任务日志目录                              |

---

## 核心功能模块

### 1. 数据库连接管理

- **支持类型**: MySQL / MariaDB, PostgreSQL
- **SSH 隧道**: 密码认证 + OpenSSH 私钥认证
- **加密存储**: 所有密码和 SSH 私钥短语使用 AES-256 加密
- **连接测试**: 智能错误检测与诊断

### 2. SQL 工作台

- **语法高亮**: CodeMirror 6 实时高亮 SQL 关键字、字符串、数字、注释
- **异步执行**: 后端异步执行，不阻塞前端 UI
- **智能补全**: 基于元数据的表名/列名建议
- **多标签页**: 支持同时打开多个工作台标签页
- **内联数据编辑**: 查询结果单元格可双击编辑，自动参数化 SQL 更新，支持批量保存修改
- **查询保存**: 支持保存常用查询，跨会话复用

### 3. 表结构管理

- **表浏览**: 查看表结构、索引、DDL 定义
- **数据浏览**: 分页查看表数据，支持排序与筛选

### 4. AI 智能助手

- **自然语言转 SQL**: 描述需求自动生成 SQL
- **架构感知**: 自动提取数据库上下文
- **SQL 诊断**: 性能优化建议与语法错误解析
- **SSE 流式回复**: 实时展示 AI 生成内容
- **多会话管理**: 支持创建多个独立对话，按连接/数据库分组
- **表选择上下文**: 可指定表范围的上下文，提高回复精准度
- **消息操作**: 支持复制、二次提问、导出对话内容

### 5. 数据导出

- **格式**: Excel (.xlsx), PDF, HTML, Markdown, CSV, Navicat (.ncx)

### 6. 数据库同步

- **跨库同步**: 表结构 + 数据同步
- **历史记录**: 完整同步日志

---

## 开发规范

### API 设计规范

- **RESTful 风格**: 所有 API 路径以 `/api` 开头
- **请求/响应**: 统一使用 Pydantic 模型进行校验
- **错误处理**: 统一返回 `{"detail": "错误信息"}`
- **连接状态**: 通过 `dependencies.py` 中的依赖注入管理活跃连接

### 前端规范

- **组件**: 使用 Vue 3 Composition API (`<script setup lang="ts">`)
- **状态管理**: 使用 Pinia store 管理全局状态
- **UI 组件**: 优先使用 Naive UI 组件库
- **API 调用**: 统一通过 `src/api/index.ts` 中的 Axios 实例发起
- **类型安全**: 所有代码使用 TypeScript 编写

### 安全规范

1. **凭据保护**: 严禁在代码或日志中明文打印任何凭据
2. **加密存储**: 密码必须通过 `backend/utils/crypto.py` 中的 `CryptoUtils` 加密后存储
3. **SSH 密钥**: 私钥路径和 passphrase 需加密存储

### 数据库操作规范

- 使用 `backend/core/db_operations.py` 中的 `DBOperations` 统一管理连接
- 每次 API 请求使用独立的数据库连接，操作后关闭
- 所有数据库操作需捕获异常并返回有意义的错误信息

---

## API 路由一览

| 前缀                 | 功能               |
| ------------------ | ---------------- |
| `/api/health`      | 健康检查             |
| `/api/connections` | 连接管理 CRUD        |
| `/api/databases`   | 数据库列表/创建/删除      |
| `/api/tables`      | 表结构/数据/索引        |
| `/api/query`       | SQL 执行与结果分页      |
| `/api/queries`     | 保存的查询 (CRUD)    |
| `/api/backup`      | 备份与恢复            |
| `/api/export`      | 多格式数据导出          |
| `/api/import`      | 数据导入             |
| `/api/sync`        | 同步任务管理           |
| `/api/ai`          | AI 智能对话 (SSE 流式) |

---

## 快捷键参考 (前端)

| 快捷键                 | 功能       |
| ------------------- | -------- |
| `F5` / `Ctrl+Enter` | 执行当前 SQL |
| `Ctrl+S`            | 保存草稿     |

---

## 常见问题排查

### 1. 后端启动报错

```bash
# 确保已安装依赖
pip install -r backend/requirements.txt
```

### 2. 前端开发服务器无法连接后端

- 确认后端已在 `127.0.0.1:18081` 启动
- Vite 配置已自动代理 `/api` 到后端

### 3. SSH 隧道连接失败

- 确认目标服务器 SSH 端口是否开放
- 检查私钥格式 (仅支持 OpenSSH 格式)
- 验证防火墙规则

### 4. AI 对话无响应

- 检查 API Key 是否正确配置
- 确认网络可以访问 OpenAI API
- 查看后端日志确认 SSE 连接状态

---

## 许可证

MIT License
