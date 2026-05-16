# MDBS - 智能数据库连接管理工具

## 项目概述

**MDBS** 是一款基于 Python + Tkinter 构建的轻量级桌面数据库管理工具，专为需要通过 SSH 隧道安全访问远程 MySQL/MariaDB 和 PostgreSQL 数据库的开发者和 DBA 设计。该工具集成了 SQL 编辑器、表结构管理、数据同步、可视化导出和 AI 智能助手等核心功能。

### 技术栈

| 层级 | 技术/库 |
|------|---------|
| **GUI 框架** | Tkinter (Python 内置) |
| **数据库驱动** | pymysql (MySQL), pg8000 (PostgreSQL) |
| **SSH 隧道** | sshtunnel, paramiko |
| **AI 集成** | openai >= 1.0.0 |
| **数据导出** | openpyxl (Excel), fpdf2 (PDF), sqlparse |
| **加密** | cryptography (Fernet AES) |
| **打包** | PyInstaller |
| **系统托盘** | pystray, Pillow |

---

## 项目架构

```
DBConnectorManager/
├── app.py                    # 应用程序入口 (含 DPI 感知初始化)
├── build_exe.py              # PyInstaller 打包脚本
├── icon.ico                  # 应用图标 (16-256px 多尺寸 .ico)
├── requirements.txt          # 依赖清单
├── core/                     # 核心业务逻辑层 (解耦 UI)
│   ├── db_operations.py      # 数据库连接池与 CRUD 操作
│   ├── ssh_manager.py        # SSH 隧道生命周期管理
│   ├── exporter.py           # 多格式导出引擎 (Excel/PDF/HTML/Markdown/CSV/Navicat)
│   ├── importer.py           # SQL/CSV 数据导入引擎
│   ├── syncer.py             # 跨库同步核心逻辑
│   ├── metadata_cache.py     # 库表元数据缓存
│   ├── sql_completer.py      # SQL 智能补全引擎 (含 Navicat 风格策略)
│   ├── scratch_manager.py    # SQL 草稿自动保存
│   ├── backup_manager.py     # 备份/恢复管理
│   ├── theme.py              # 主题颜色配置
│   ├── ui_style.py           # UI 样式工具函数
│   └── ai/                   # AI 智能助手模块
│       ├── client.py         # OpenAI 协议兼容客户端 (支持流式)
│       ├── context_builder.py # 数据库上下文提取
│       └── markdown_renderer.py # AI 回复 Markdown 渲染
├── ui/                       # Tkinter 界面层
│   ├── main_window.py        # IDE 风格主窗体 (多文档界面)
│   ├── sql_workbench.py      # 高级 SQL 编辑器 (语法高亮/异步执行)
│   ├── table_manager.py      # 内联式表结构编辑器
│   ├── table_manager_dialog.py # 表结构管理对话框
│   ├── edit_dialog.py        # 连接属性编辑 (含 SSH 配置)
│   ├── settings_dialog.py    # 全局设置 (主题/字体/AI 密钥)
│   ├── sync_dialog.py        # 数据库同步向导
│   ├── sync_progress_dialog.py # 同步进度展示
│   ├── er_export_dialog.py   # ER 图导出配置
│   ├── export_dialog.py      # 数据导出对话框
│   ├── export_format_dialog.py # 导出格式选择
│   ├── import_dialog.py      # 数据导入对话框
│   ├── create_db_dialog.py   # 数据库创建对话框
│   ├── db_select_dialog.py   # 数据库选择对话框
│   ├── history_window.py     # 同步历史记录窗口
│   ├── progress_dialog.py    # 进度对话框
│   ├── backup_dialog.py      # 备份/恢复对话框
│   ├── view_manager_dialog.py # 视图管理
│   ├── function_manager_dialog.py # 函数/存储过程管理
│   └── ai/                   # AI 交互界面
│       ├── ai_settings_dialog.py # AI 设置对话框
│       ├── chat_panel.py     # AI 对话面板
│       └── session_wizard.py # AI 会话向导
├── models/                   # 数据访问层
│   ├── db_storage.py         # SQLite 持久化 (连接/设置/历史)
│   └── sync_history.py       # 同步任务日志管理
└── utils/                    # 通用工具
    └── crypto.py             # 安全加密模块 (AES-256)
```

---

## 快速开始

### 环境要求

- Python 3.7+
- Windows 10/11 (64 位推荐)

### 安装与运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
python app.py

# 3. 打包为 EXE (可选)
pip install pyinstaller
python build_exe.py
# 输出: dist/database.exe
```

### 数据存储

| 文件/目录 | 说明 |
|----------|------|
| `connections.db` | SQLite 数据库，存储连接配置、SQL 历史、同步日志 (密码已加密) |
| `secret.key` | 本地唯一根密钥 (AES Fernet) |
| `~/.db_connector_scratch/` | SQL 草稿自动保存目录 |

---

## 核心功能模块

### 1. 数据库连接管理

- **支持类型**: MySQL / MariaDB, PostgreSQL
- **SSH 隧道**: 密码认证 + OpenSSH 私钥认证
- **加密存储**: 所有密码和 SSH 私钥短语使用 AES-256 加密
- **连接测试**: 智能错误检测与诊断

### 2. SQL 工作台

- **语法高亮**: 关键字、字符串、数字、注释实时着色
- **异步执行**: 后台线程执行，不阻塞 UI
- **智能补全**: 基于元数据的表名/列名建议
- **草稿保护**: 每 30 秒自动保存
- **结果编辑**: 双击修改数据 (需满足条件)

### 3. 表结构管理

- **标签页化**: 多表并发编辑
- **原地编辑**: 双击修改字段名、类型、默认值、注释
- **变更预览**: 自动生成 ALTER TABLE 语句

### 4. AI 智能助手

- **自然语言转 SQL**: 描述需求自动生成 SQL
- **架构感知**: 自动提取数据库上下文
- **SQL 诊断**: 性能优化建议与语法错误解析

### 5. 数据导出

- **格式**: Excel (.xlsx), PDF, HTML, Markdown, CSV, Navicat (.ncx)
- **ER 图**: Mermaid 交互式 HTML 拓扑图

### 6. 数据库同步

- **跨库同步**: 表结构 + 数据同步
- **历史记录**: 完整同步日志

---

## 开发规范

### 异步处理原则

> **关键规则**: 任何涉及网络或 I/O 的操作必须通过 `threading` 异步处理，**禁止阻塞 UI 线程**。

```python
# 正确示例
def _execute_query(self):
    thread = threading.Thread(target=self._run_query_thread)
    thread.start()

def _run_query_thread(self):
    # 耗时操作在后台线程执行
    result = self.db_ops.execute(...)
    self.after(0, lambda: self._update_ui(result))

# 错误示例 (阻塞 UI)
def _execute_query(self):
    result = self.db_ops.execute(...)  # ❌ 不要这样做
    self._update_ui(result)
```

### 安全规范

1. **凭据保护**: 严禁在代码或日志中明文打印任何凭据
2. **加密存储**: 密码必须通过 `utils.crypto.CryptoUtils` 加密后存储
3. **SSH 密钥**: 私钥路径和 passphrase 需加密存储

### UI 组件规范

- 使用 `ttk` 组件以获得原生外观
- 统一使用 `core.theme.get_theme_colors()` 获取主题色
- 所有对话框需继承 `tk.Toplevel` 或使用 `tk.simpledialog`
- 长时间操作必须显示 `ui.progress_dialog.ProgressDialog`

### 数据库操作规范

- 使用 `core.db_operations.DBOperations` 统一管理连接
- 必须使用连接池或每次操作后关闭连接
- 所有数据库操作需捕获异常并返回有意义的错误信息

---

## 快捷键参考

| 快捷键 | 功能 |
|--------|------|
| `F5` | 执行当前 SQL / 刷新资源树 |
| `Ctrl+S` | 保存当前工作台内容 |
| `Ctrl+Shift+S` | 一键保存所有草稿 |
| `Ctrl+F` | 在编辑器内查找 |

---

## 常见问题排查

### 1. 打包后运行报错

```bash
# 检查是否缺少隐藏导入
pyinstaller --hidden-import=pg8000.native app.py
```

### 2. SSH 隧道连接失败

- 确认目标服务器 SSH 端口是否开放
- 检查私钥格式 (仅支持 OpenSSH 格式)
- 验证防火墙规则

### 3. AI 对话无响应

- 检查 API Key 是否正确配置
- 确认网络可以访问 OpenAI API
- 查看 `ui/ai/chat_panel.py` 日志

---

## 许可证

MIT License