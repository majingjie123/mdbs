# MDBS

基于 **FastAPI + Vue 3** 的现代 Web 数据库管理工具，支持通过 SSH 隧道安全访问远程 MySQL/MariaDB 和 PostgreSQL。集成了 SQL 编辑器、表结构管理、数据同步、多格式导出及 AI 智能助手。

---

## 核心特性

### 深度多库支持

- **MySQL / MariaDB**: 完美适配常用版本，支持库/表元数据快速拉取。
- **PostgreSQL**: 基于 `pg8000.native` 实现，支持 Schema 切换及复杂类型展示。

### 智能 SQL 工作台

- **语法高亮**: CodeMirror 6 实时高亮 SQL 关键字、字符串、数字及注释。
- **异步执行**: 所有 SQL 语句在后台异步执行，确保海量数据查询时前端依然响应灵敏。
- **多标签页**: 支持同时打开多个工作台标签页，独立管理查询上下文。
- **内联数据编辑**: 查询结果单元格可双击编辑，自动参数化 SQL 更新，支持批量保存修改。

### 数据库管理与表结构

- **数据库操作**: 支持快速创建新数据库及删除数据库。
- **表浏览**: 查看表结构、索引、DDL 定义、表数据。

### 企业级安全与隧道

- **SSH 隧道**: 支持密码认证及 OpenSSH 私钥认证。
- **字段加密**: 采用 AES (Fernet) 加密标准存储所有数据库密码及 SSH 私钥短语。

### AI 智能助手 (OpenAI v1.0+ 适配)

- **自然语言转 SQL**: 通过对话界面描述需求，自动生成高质量 SQL 脚本。
- **架构感知**: 自动提取当前数据库上下文（表名、列名、注释），实现精准回复。
- **SSE 流式回复**: AI 生成内容实时流式展示，无需等待完整响应。
- **SQL 诊断**: 提供查询性能优化建议及语法错误解析。

### 多格式导出

- 支持 **Excel (.xlsx), PDF, HTML, Markdown, CSV** 及 **Navicat (.ncx)** 配置导出。

### 数据库同步

- **跨库同步**: 支持表结构 + 数据同步，带完整日志记录。

---

## 安装与运行

### 环境要求

- Python 3.7+
- Node.js 18+ (仅前端开发时需要)
- 推荐使用 64 位操作系统

### 开发模式运行

```bash
# 1. 后端启动
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 18081 --reload

# 2. 前端启动 (新终端窗口)
cd frontend
npm install
npm run dev
```

打开浏览器访问 `http://localhost:5173`（Vite 开发服务器自动代理 API 到 18081 端口）。

### 生产模式运行（浏览器访问）

```bash
# 1. 构建前端
cd frontend
npm run build

# 2. 启动后端服务 (自动托管前端静态文件)
python scripts/run_backend.py
```

访问 `http://127.0.0.1:18081/`。

### 桌面原生模式（打包为独立可执行文件）

MDBS 使用 **PyInstaller** 将后端 + 前端打包为单个目录，同时嵌入 **pywebview** 原生桌面窗口，用户无需浏览器即可使用。

#### 环境准备

```bash
# 安装 Node.js 依赖（仅首次）
cd frontend
npm install

# 安装 Python 依赖（仅首次）
cd backend
pip install -r requirements.txt
pip install pywebview                         # 原生桌面窗口
```

#### 构建步骤

```bash
# 第 1 步：构建前端 SPA
cd frontend
npm run build
# 生成: frontend/dist/

# 第 2 步：打包后端 + 前端为独立 exe
cd ..
python scripts/build_backend_exe.py
```

#### 输出产物

```
dist/mdbs-server/
├── mdbs-server.exe          # 主程序入口（双击运行）
├── _internal/               # 依赖库运行环境
│   └── frontend/dist/       # 前端静态文件（已打包在内）
```

#### 使用方式

直接双击 `dist/mdbs-server/mdbs-server.exe` 启动，将弹出原生桌面窗口：

- **标题**: MDBS
- **默认尺寸**: 1280×800（最小 800×600）
- **窗口行为**: 可拖拽缩放，启动时自动最大化
- **托盘**: 关闭窗口不会终止后端进程

#### 传给其他用户

只需将 `dist/mdbs-server/` 整个目录压缩后分发，接收方解压后直接运行 `.exe` 即可（无需安装 Python / Node.js）。

#### 常见问题

**Q: 启动后窗口空白 / 白屏？**
A: 检查端口 18081 是否被占用，尝试设置环境变量 `MDBS_PORT=18082` 后重新启动。

**Q: 如何更换端口？**
A: 设置环境变量 `MDBS_PORT=新端口`，例如：
```cmd
set MDBS_PORT=19000
mdbs-server.exe
```

**Q: 如何以无窗口模式运行（仅作为 Web 服务）？**
A: 当前不支持从 exe 中剥离窗口。如需纯 Web 服务，请使用「生产模式运行（浏览器访问）」方式启动。

**Q: 运行后闪退？**
A: 查看用户目录下的 `mdbs_debug.log` 文件获取详细错误信息：
```
%USERPROFILE%\mdbs_debug.log
```

---

## 项目结构

```
DBConnectorManager/
├── backend/                        # FastAPI 后端服务
│   ├── main.py                     # 应用入口 (API + SPA 静态托管)
│   ├── core/                       # 核心业务逻辑
│   │   ├── db_operations.py        # 数据库 CRUD 与连接管理
│   │   ├── ssh_manager.py          # SSH 隧道维护
│   │   ├── exporter.py             # 多格式导出引擎
│   │   ├── importer.py             # 数据导入引擎
│   │   ├── syncer.py               # 跨库同步逻辑
│   │   ├── backup_manager.py       # 备份/恢复管理
│   │   ├── metadata_cache.py       # 元数据缓存
│   │   └── ai/                     # AI 模块
│   │       ├── client.py           # OpenAI 客户端
│   │       ├── context_builder.py  # 数据库上下文提取
│   │       └── markdown_renderer.py # Markdown 渲染
│   ├── models/                     # 数据访问层
│   ├── routers/                    # API 路由
│   │   ├── connections.py          # 连接管理
│   │   ├── databases.py            # 数据库管理
│   │   ├── tables.py               # 表结构管理
│   │   ├── query.py                # SQL 查询
│   │   ├── queries.py              # 保存的查询 CRUD
│   │   ├── backup.py               # 备份/恢复
│   │   ├── export.py               # 数据导出
│   │   ├── import_routes.py        # 数据导入
│   │   ├── sync.py                 # 同步管理
│   │   └── ai.py                   # AI 对话 (SSE 流式)
│   └── utils/                      # 通用工具
│       └── crypto.py               # 加密模块
├── frontend/                       # Vue 3 前端 SPA
│   ├── index.html
│   ├── src/
│   │   ├── App.vue                 # 根组件 (Naive UI 全局配置)
│   │   ├── api/index.ts            # API 请求层 (Axios)
│   │   ├── components/             # 公共组件
│   │   │   ├── AppLayout.vue       # 主布局
│   │   │   ├── Sidebar.vue         # 侧边导航
│   │   │   ├── SqlEditor.vue       # CodeMirror 编辑器
│   │   │   ├── TabWorkspace.vue    # 标签页工作区
│   │   │   └── dialogs/            # 对话框组件
│   │   ├── router/index.ts         # 路由配置
│   │   ├── stores/app.ts           # Pinia 状态管理
│   │   └── views/                  # 页面
│   │       ├── ConnectionList.vue   # 连接列表
│   │       ├── ConnectionDetail.vue # 连接编辑
│   │       ├── SQLWorkbench.vue     # SQL 工作台
│   │       ├── TableBrowser.vue     # 表结构浏览
│   │       ├── AIChat.vue           # AI 对话
│   │       ├── AISettingsPage.vue   # AI 设置
│   │       └── SettingsPage.vue     # 全局设置
│   └── vite.config.ts
├── scripts/                        # 构建/运行脚本
│   ├── run_backend.py              # 启动脚本
│   └── build_backend_exe.py        # PyInstaller 打包脚本
├── icon.ico                        # 应用图标
└── sync_logs/                      # 同步日志目录
```

---

## 数据存储说明

| 文件/目录            | 说明                          |
| ---------------- | --------------------------- |
| `connections.db` | 存储连接配置、SQL 历史、同步日志，数据库密码已加密 |
| `secret.key`     | 本地加解密唯一根密钥（切勿分享或丢失）         |
| `sync_logs/`     | 数据库同步任务日志目录                 |

---

## API 路由

| 前缀                 | 说明             |
| ------------------ | -------------- |
| `/api/health`      | 服务健康检查         |
| `/api/connections` | 连接管理 (CRUD)    |
| `/api/databases`   | 数据库列表/创建/删除    |
| `/api/tables`      | 表结构、数据、索引      |
| `/api/query`       | SQL 执行与结果分页      |
| `/api/queries`     | 保存的查询 (CRUD)    |
| `/api/backup`      | 备份与恢复          |
| `/api/export`      | 数据导出           |
| `/api/import`      | 数据导入           |
| `/api/sync`        | 同步管理           |
| `/api/ai`          | AI 对话 (SSE 流式) |

---

## 快捷键参考

| 快捷键                 | 功能       |
| ------------------- | -------- |
| `F5` / `Ctrl+Enter` | 执行当前 SQL |
| `Ctrl+S`            | 保存当前草稿   |

---

## 开发与贡献

- **代码规范**: 请遵循 `AGENTS.md` 中定义的开发规约。
- **API 规范**: RESTful 风格，统一使用 Pydantic 模型校验。
- **前端规范**: Vue 3 Composition API + TypeScript + Naive UI。
- **安全性**: 严禁在代码或日志中明文打印任何凭据。

---

## 许可证

本项目遵循 MIT 许可证。