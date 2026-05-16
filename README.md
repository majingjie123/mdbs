# MDBS

基于 Python + Tkinter 的轻量级桌面数据库管理工具，支持通过 SSH 隧道安全访问远程 MySQL/MariaDB 和 PostgreSQL。集成了 SQL 编辑器、表结构管理、数据同步及可视化导出。

---

## 核心特性

### 深度多库支持
- **MySQL / MariaDB**: 完美适配常用版本，支持库/表元数据快速拉取。
- **PostgreSQL**: 基于 `pg8000.native` 实现，支持 Schema 切换及复杂类型展示。

### 智能 SQL 工作台
- **语法高亮**: 实时高亮 SQL 关键字、字符串、数字及注释。
- **异步执行**: 所有 SQL 语句均在后台线程执行，确保海量数据查询时 UI 依然响应灵敏。
- **智能补全**: 基于本地元数据缓存，提供库名、表名及 SQL 关键字的实时建议。
- **结果编辑**: 支持直接在查询结果表格中双击修改数据（需满足可更新条件）。
- **草稿保护**: 每 30 秒自动保存编辑器内容，防止意外关闭导致进度丢失。

### 数据库管理与表结构
- **数据库操作**: 支持快速创建新数据库（自定义字符集/排序规则）及删除数据库。
- **标签页化管理**: 表结构管理集成在主工作区 Tab 中，支持多表并发编辑。
- **原地编辑 (Inline Edit)**: 双击单元格即可修改字段名、类型、默认值及注释。
- **变更预览**: 自动生成并展示 `ALTER TABLE` 语句，确保操作透明。

### 企业级安全与隧道
- **SSH 隧道**: 支持密码认证及 OpenSSH 私钥认证，配置变更自动重连。
- **字段加密**: 采用 AES (Fernet) 加密标准存储所有数据库密码及 SSH 私钥短语。

### AI 智能助手 (OpenAI v1.0+ 适配)
- **自然语言转 SQL**: 通过对话面板描述需求，自动生成高质量 SQL 脚本。
- **架构感知**: 自动提取当前数据库上下文（表名、列名、注释），实现精准回复。
- **SQL 诊断**: 提供查询性能优化建议及语法错误解析。

### 可视化与导出
- **ER 关系图**: 生成基于 Mermaid 的交互式 HTML 拓扑图，直观展现表间依赖。
- **多格式导出**: 支持 **Excel, PDF, HTML, Markdown, CSV** 及 **Navicat (.ncx)** 配置导出。

---

## 安装与运行

### 环境要求
- Python 3.7+
- 推荐使用 64 位操作系统（用于打包支持）

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动应用
```bash
python app.py
```

### 3. 打包可执行文件
```bash
pip install pyinstaller
python build_exe.py
```

---

## 项目结构

```
DBConnectorManager/
├── app.py                          # 应用程序入口
├── build_exe.py                    # PyInstaller 打包自动化脚本
├── icon.ico                        # 应用图标（多尺寸 .ico）
├── core/                           # 核心业务逻辑（解耦 UI）
│   ├── ai/                         # AI 模块
│   │   ├── client.py               # OpenAI 协议兼容客户端
│   │   ├── context_builder.py      # 数据库上下文提取器
│   │   └── markdown_renderer.py    # AI 回复 Markdown 渲染引擎
│   ├── db_operations.py            # 数据库 CRUD 与连接池管理
│   ├── ssh_manager.py              # SSH 隧道建立与生命周期维护
│   ├── exporter.py                 # 多格式数据/结构导出引擎
│   ├── importer.py                 # SQL/CSV 数据导入引擎
│   ├── syncer.py                   # 跨库同步核心逻辑
│   ├── backup_manager.py           # 数据库备份/恢复管理
│   ├── scratch_manager.py          # SQL 工作台草稿持久化
│   ├── metadata_cache.py           # 库表元数据缓存
│   ├── sql_completer.py            # 基于元数据的自动补全引擎
│   ├── theme.py                    # 主题颜色配置
│   └── ui_style.py                 # UI 样式工具函数
├── ui/                             # Tkinter 界面层
│   ├── ai/                         # AI 交互界面（对话面板、向导）
│   ├── main_window.py              # IDE 风格主窗体（多文档界面）
│   ├── sql_workbench.py            # 高级 SQL 编辑器组件
│   ├── table_manager.py            # 内联式表结构编辑器
│   ├── create_db_dialog.py         # 数据库创建对话框
│   ├── edit_dialog.py              # 连接属性编辑（含 SSH 配置）
│   ├── settings_dialog.py          # 全局设置（主题、字体、AI 秘钥）
│   ├── sync_dialog.py              # 数据库同步向导
│   ├── sync_progress_dialog.py     # 同步进度展示对话框
│   ├── import_dialog.py            # 数据导入对话框
│   ├── export_dialog.py            # 数据导出对话框
│   ├── export_format_dialog.py     # 导出格式选择对话框
│   ├── er_export_dialog.py         # ER 图导出配置
│   ├── view_manager_dialog.py      # 视图定义管理
│   ├── function_manager_dialog.py  # 函数与存储过程管理
│   ├── backup_dialog.py            # 备份/恢复对话框
│   ├── history_window.py           # 同步历史记录窗口
│   └── progress_dialog.py          # 通用进度对话框
├── models/                         # 数据访问层
│   ├── db_storage.py               # SQLite 持久化（连接、设置、历史）
│   └── sync_history.py             # 同步任务日志管理
└── utils/                          # 通用工具
    └── crypto.py                   # 安全加密模块 (CryptoUtils)
```

---

## 数据存储说明

| 文件/目录 | 说明 |
|------|----------|
| `connections.db` | 存储连接配置、SQL 历史、同步日志，数据库密码已加密 |
| `secret.key` | 本地加解密唯一根密钥（切勿分享或丢失） |
| `~/.db_connector_scratch/` | SQL 工作台自动保存的脚本草稿 |

---

## 快捷键参考

| 快捷键 | 功能 |
|--------|------|
| `F5` | 执行当前 SQL / 刷新资源树 |
| `Ctrl+S` | 保存当前工作台内容 |
| `Ctrl+Shift+S` | 一键保存所有打开的草稿 |
| `Ctrl+F` | 在当前编辑器内查找内容 |

---

## 开发与贡献

- **代码规范**: 请遵循 `AGENTS.md` 中定义的开发规约。
- **异步处理**: 任何涉及网络或 IO 的操作必须通过 `threading` 异步处理，禁止阻塞 UI 线程。
- **安全性**: 严禁在代码或日志中明文打印任何凭据。

---

## 许可证

本项目遵循 MIT 许可证。
