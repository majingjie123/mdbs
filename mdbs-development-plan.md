# MDBS 完整开发计划

> 全面对比 Navicat，列出所有模块的开发计划、测试标准和指导细节
> 基于实际代码审查 (2026-06-13)，更新已完成功能状态

---

## 目录

1. [SQL 编辑器模块](#1-sql-编辑器模块)
2. [数据编辑模块](#2-数据编辑模块)
3. [表结构管理模块](#3-表结构管理模块)
4. [数据库对象管理模块](#4-数据库对象管理模块)
5. [查询分析模块](#5-查询分析模块)
6. [用户权限管理模块](#6-用户权限管理模块)
7. [导入导出模块](#7-导入导出模块)
8. [备份恢复模块](#8-备份恢复模块)
9. [数据同步模块](#9-数据同步模块)
10. [UI/UX 优化模块](#10-uiux-优化模块)
11. [其他高级功能模块](#11-其他高级功能模块)

---

## 1. SQL 编辑器模块

### 1.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| SQL 智能提示/自动补全 | P0 | ✅ 完成 | CodeMirror 6 autocompletion + 表/列/视图/函数缓存 |
| SQL 格式化/美化 | P0 | ✅ 完成 | sql-formatter (MySQL/PostgreSQL) |
| 查询历史 | P0 | ✅ 完成 | localStorage + 搜索 + 收藏 |
| 内联编辑数据 | P0 | ✅ 完成 | 双击编辑 + 批量保存 |
| 数据筛选/过滤 | P1 | ✅ 完成 | 全局文本过滤 |
| 列头排序 | P1 | ✅ 完成 | n-data-table sorter |
| EXPLAIN 执行计划 | P1 | ✅ 完成 | 弹窗展示 |
| 常用 SQL 片段收藏 | P0 | ❌ 待开发 | localStorage 存储 |
| 多个查询结果分屏 | P1 | ❌ 待开发 | 多结果标签页 |
| 结果中新增/删除行 | P0 | ❌ 待开发 | 行操作按钮 |
| 自动保存草稿 | P0 | ❌ 待开发 | localStorage 自动保存 |
| 括号匹配高亮 | P2 | ❌ 待开发 | CodeMirror 插件 |
| JOIN 智能补全 | P2 | ❌ 待开发 | 解析 SQL 上下文 |

### 1.2 开发细节

#### 1.2.1 SQL 智能提示 (已完成)

SqlEditor.vue 中使用 CodeMirror 6：
- `@codemirror/lang-sql` — SQL 语法高亮
- `@codemirror/autocomplete` — 自定义补全函数
- `sqlCompletions()` — 返回表名/列名/视图名/函数名/关键字
- `parseTablePrefix()` — 支持 `表名.列名` 补全
- `loadSchema()` — 异步加载所有表的列元数据（分批 5 个并发）

#### 1.2.2 SQL 片段收藏（待开发）

**方案**: 使用 localStorage 存储常用 SQL 片段，SqlEditor 或 SQLWorkbench 中嵌入片段面板。

```typescript
// 片段数据结构
interface SqlSnippet {
  id: string
  name: string
  sql: string
  description: string
  createdAt: string
}

// 存储 key
const SNIPPETS_KEY = 'mdbs_sql_snippets'

// 在 SQL 工具栏添加片段按钮，点击弹出片段选择器
// 选中的片段插入到编辑器光标位置
```

**测试用例:**
- 保存当前 SQL 为片段
- 从片段列表选择插入编辑器
- 删除片段
- 搜索片段

#### 1.2.3 多个查询结果分屏（待开发）

**方案**: SQLWorkbench 中维护 `results` 数组，每次查询追加新结果，支持切换查看。

```typescript
// 多结果状态
const results = ref<ExecResult[]>([])
const activeResultIndex = ref(0)

// 执行时追加
async function runQuery() {
  const res = await execute(...)
  results.value.push(res)
  activeResultIndex.value = results.value.length - 1
}
```

**测试用例:**
- 连续执行多个 SQL，所有结果保留
- 切换查看不同结果
- 关闭单个结果

---

## 2. 数据编辑模块

### 2.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 单元格直接编辑 | P0 | ✅ 完成 | SQLWorkbench.vue + TableBrowser.vue |
| 批量数据修改 | P1 | ✅ 完成 | 选中行→批量操作 |
| 新增/删除行 | P0 | ❌ 待开发 | 结果表格底部添加 |
| 数据筛选/过滤 | P1 | ✅ 完成 | filterText + filteredRows |
| 列头排序 | P1 | ✅ 完成 | sorter |
| 分页查看 | P1 | ✅ 完成 | 后端分页 + 前端翻页 |
| 内联编辑保存 | P0 | ✅ 完成 | 批量生成 UPDATE SQL |

### 2.2 开发细节

#### 2.2.1 单元格编辑 (已完成)

SQLWorkbench.vue `startEdit()` / `commitEdit()` / `saveEdits()`:
- 双击进入编辑模式
- Enter 保存 / ESC 取消
- 跟踪修改的单元格，批量生成 UPDATE
- 自动识别主键列用于 WHERE 条件
- 修改未保存时显示 "💾 保存修改 (N)" 按钮

#### 2.2.2 新增/删除行（待开发）

**前端 SQLWorkbench.vue 扩展：**

```typescript
// 新增空行
function addEmptyRow() {
  if (!result.value?.columns) return
  const emptyRow: Record<string, any> = {}
  result.value.columns.forEach(col => { emptyRow[col] = null })
  // 插入到表格底部
  allRows.value.push(emptyRow)
}

// 删除选中行
async function deleteSelectedRows() {
  const sql = `DELETE FROM ${tableName} WHERE ${pkColumn} IN (${selectedPks.join(',')})`
  await api.executeSQL(connId, sql)
  // 重新查询
}
```

**测试用例:**
- 点击"新增行"按钮出现空行
- 编辑空行数据后保存
- 勾选行→删除确认→执行 DELETE
- 新增行后取消

---

## 3. 表结构管理模块

### 3.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 可视化创建表 | P0 | ✅ 完成 | TableBrowser 对话框 |
| 列管理(添加/修改/删除) | P0 | ✅ 完成 | 内联编辑 + ALTER SQL |
| 索引管理 | P1 | ✅ 完成 | 添加/删除索引 |
| 索引管理可视化 | P1 | ✅ 完成 | 弹窗编辑索引 |
| 外键关系管理 | P2 | ❌ 待开发 | 可视化外键编辑 |
| 列拖拽排序 | P2 | ❌ 待开发 | 拖拽排序替代按钮 |
| 表/字段注释管理 | P1 | ✅ 完成 | 编辑注释 |
| 修改预览 SQL | P1 | ✅ 完成 | ALTER 预览 |

### 3.2 开发细节

#### 3.2.1 创建表对话框 (已完成)

TableBrowser.vue `doCreateTable()`:
- 字段名称/类型/可空/主键/自增/默认值/注释
- 引擎选择(MySQL) / 字符集 / 表注释
- 生成 CREATE TABLE SQL 并执行

API: `POST /tables/{conn_id}/create`

#### 3.2.2 外键关系管理（待开发）

**后端 API 扩展:**

```python
# backend/routers/tables.py

@router.get("/{conn_id}/foreign-keys")
def get_foreign_keys(conn_id: int, database: str = "", schema: str = "",
                     storage=Depends(get_db_storage), ops=Depends(get_db_ops)):
    """获取所有外键关系"""
    conn_data = _get_conn_data(conn_id, storage)
    db_type = conn_data.get("db_type", "MySQL")
    
    if db_type == "MySQL":
        sql = """
            SELECT 
                kcu.TABLE_NAME, kcu.COLUMN_NAME, kcu.CONSTRAINT_NAME,
                kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME,
                rc.UPDATE_RULE, rc.DELETE_RULE
            FROM information_schema.KEY_COLUMN_USAGE kcu
            JOIN information_schema.TABLE_CONSTRAINTS tc 
                ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
                ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            WHERE kcu.TABLE_SCHEMA = %s 
                AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
        """
    ...
```

**测试用例:**
- 列出表的所有外键
- 添加外键约束
- 删除外键约束
- 更新 ON DELETE / ON UPDATE 规则

---

## 4. 数据库对象管理模块

### 4.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 视图管理 | P1 | ✅ 完成 | ViewManager.vue |
| 存储过程/函数管理 | P2 | ✅ 完成 | FunctionManager.vue |
| 触发器管理 | P1 | ❌ 待开发 | TriggerManager.vue (新建) |
| 事件管理 (MySQL Events) | P2 | ❌ 待开发 | EventManager.vue (新建) |

### 4.2 开发细节

#### 4.2.1 触发器管理（待开发 - 当前最高优先级）

**后端 API (`backend/routers/triggers.py`):**

```python
"""触发器管理 API"""
from fastapi import APIRouter, Depends
from ..dependencies import get_db_storage, get_db_ops

router = APIRouter(prefix="/api/triggers", tags=["触发器管理"])

@router.get("/{conn_id}")
def list_triggers(conn_id: int, database: str = "", schema: str = "",
                  storage=Depends(get_db_storage), ops=Depends(get_db_ops)):
    """列出所有触发器"""
    conn_data = _get_conn_data(conn_id, storage)
    db_type = conn_data.get("db_type", "MySQL")
    
    if db_type == "MySQL":
        sql = """
            SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE,
                   ACTION_TIMING, DEFINER, CREATED
            FROM information_schema.TRIGGERS
            WHERE TRIGGER_SCHEMA = %s
            ORDER BY TRIGGER_NAME
        """
        # 执行并返回列表
    else:
        sql = """
            SELECT tgname AS TRIGGER_NAME,
                   pg_catalog.pg_get_triggerdef(t.oid) AS TRIGGER_BODY
            FROM pg_catalog.pg_trigger t
            JOIN pg_catalog.pg_class c ON t.tgrelid = c.oid
            JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname = 'public' AND NOT t.tgisinternal
            ORDER BY tgname
        """
    ...

@router.get("/{conn_id}/{trigger_name}/ddl")
def get_trigger_ddl(...):
    """获取触发器定义"""
    if db_type == "MySQL":
        sql = f"SHOW CREATE TRIGGER `{trigger_name}`"
    ...

@router.post("/{conn_id}")
def create_trigger(...):
    """创建触发器"""
    # 接收 SQL 定义，直接执行

@router.delete("/{conn_id}/{trigger_name}")
def drop_trigger(...):
    """删除触发器"""
    sql = f"DROP TRIGGER IF EXISTS `{trigger_name}`"
    ...
```

**前端 (`frontend/src/views/TriggerManager.vue`):**
- 与 ViewManager.vue / FunctionManager.vue 风格一致
- 显示触发器列表（名称/事件/表/时机/定义者）
- 查看 DDL 定义
- 创建/删除触发器

**测试用例:**
- 列出所有触发器（MySQL/PostgreSQL）
- 查看触发器 DDL
- 创建触发器（BEFORE INSERT / AFTER UPDATE 等）
- 删除触发器

#### 4.2.2 事件管理（待开发）

**后端 API:** 类似触发器，管理 MySQL Events

**前端:** EventManager.vue

---

## 5. 查询分析模块

### 5.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| EXPLAIN 执行计划 | P1 | ✅ 完成 | 弹窗展示原始输出 |
| 慢查询日志 | P3 | ❌ 待开发 | 需要后端收集 |
| 索引建议 | P3 | ❌ 待开发 | 解析 EXPLAIN 输出 |
| 执行计划图形化 | P2 | ❌ 待开发 | 树形/图形展示 |

### 5.2 开发细节

#### 5.2.1 执行计划图形化（待开发）

**前端增强:** SQLWorkbench.vue 中增强 EXPLAIN 结果展示
- JSON 格式化展示 → 树形组件展示
- 颜色标记：全表扫描(红)、索引扫描(黄)、走索引(绿)
- 展示预计行数/耗时

---

## 6. 用户权限管理模块

### 6.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 用户列表 | P3 | ❌ 待开发 | 从 mysql.user / pg_roles 读取 |
| 角色管理 | P3 | ❌ 待开发 | MySQL SHOW GRANTS |
| 权限授予/回收 | P3 | ❌ 待开发 | GRANT / REVOKE |
| 数据库授权 | P3 | ❌ 待开发 | GRANT ON db.* |

---

## 7. 导入导出模块

### 7.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 导出表结构 | P1 | ✅ 完成 | Excel/PDF/HTML/MD |
| 导出数据 | P1 | ✅ 完成 | CSV/Excel |
| ER 图导出 | P1 | ✅ 完成 | HTML(Mermaid)/PDF/MD/Excel |
| 导出 Navicat 配置 | P1 | ✅ 完成 | NCX 1.5 格式 |
| 导入 CSV | P1 | ✅ 完成 | 预览+映射+三种模式 |
| 导入 SQL 脚本 | P1 | ✅ 完成 | 上传即执行 |
| 批量导入/导出 | P2 | ❌ 待开发 | 多表选择批量操作 |
| 导入导出模板 | P2 | ❌ 待开发 | 保存配置模板 |

---

## 8. 备份恢复模块

### 8.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 手动备份 | P1 | ✅ 完成 | 纯 Python + CLI 回退 |
| 手动恢复 | P1 | ✅ 完成 | 含进度回调 |
| 备份文件管理 | P1 | ✅ 完成 | 列表/删除 |
| 备份选项(结构/数据/视图/函数/触发器/事件) | P2 | ✅ 完成 | 可选项 |
| 定时自动备份 | P2 | ❌ 待开发 | APScheduler + 后端服务 |
| 备份计划管理 | P2 | ❌ 待开发 | 创建/编辑/启用/禁用计划 |
| 备份文件预览 | P2 | ❌ 待开发 | 查看备份文件内容 |

### 8.2 开发细节

#### 8.2.1 备份计划管理（待开发）

**后端:**

```python
# backend/routers/backup_plan.py (新建)

# 存储计划到 SQLite (connections.db 中建 backup_plans 表)
# 字段: id, conn_id, database, options, cron_expr, enabled, created_at

# 启动定时任务 (APScheduler)
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()

@scheduler.scheduled_job('cron', id='backup_check')
def check_backup_plans():
    """每分钟检查是否有需要执行的备份计划"""
    plans = load_due_plans()
    for plan in plans:
        execute_plan(plan)

# API 端点
@router.post("/plans")    # 创建计划
@router.get("/plans")     # 列出计划
@router.put("/plans/{id}") # 更新计划
@router.delete("/plans/{id}") # 删除计划
@router.post("/plans/{id}/toggle") # 启用/禁用
```

**前端:** 在 BackupDialog 中增加"备份计划"标签页

**测试用例:**
- 创建每小时的备份计划
- 列出所有计划
- 启用/禁用计划
- 删除计划
- 计划到期执行备份并记录

---

## 9. 数据同步模块

### 9.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 跨库同步 | P1 | ✅ 完成 | 源→目标，支持不同数据库 |
| 结构同步 | P1 | ✅ 完成 | CREATE/ALTER TABLE |
| 数据同步 | P1 | ✅ 完成 | 批量写入 + 冲突策略 |
| 同步进度 | P1 | ✅ 完成 | 实时进度 + 日志 |
| 同步历史 | P1 | ✅ 完成 | 存储到 SQLite |
| 数据对比 | P2 | ✅ 完成 | 表/行级差异 |
| 选择性同步 | P1 | ✅ 完成 | 选表/结构/数据/冲突策略 |
| 同步预览 | P2 | ✅ 完成 | 对比结果展示 |
| 定时同步 | P2 | ❌ 待开发 | 类似备份计划 |

---

## 10. UI/UX 优化模块

### 10.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 7 种主题 | P0 | ✅ 完成 | CSS 变量 + data-theme |
| 菜单栏 | P1 | ✅ 完成 | 5 个主菜单 |
| 侧栏折叠 | P1 | ✅ 完成 | 折叠/展开 |
| 侧栏多连接 | P1 | ✅ 完成 | 树形展示 |
| 侧栏搜索表 | P1 | ✅ 完成 | 每个数据库独立搜索框 |
| 右键菜单 | P1 | ✅ 完成 | 连接树 + 标签页 |
| 快捷键 | P1 | ✅ 完成 | Ctrl+Enter/F5/S/W/Shift+F |
| 全局工具栏 | P0 | ❌ 待开发 | 图标按钮工具栏 |
| 收藏夹/快捷方式 | P1 | ❌ 待开发 | 收藏连接和表 |
| 最近使用记录 | P1 | ❌ 待开发 | localStorage 存储 |
| 状态栏丰富 | P1 | ❌ 待开发 | 显示连接状态/耗时/行数 |
| 拖放操作 | P2 | ❌ 待开发 | 表拖入编辑器生成 SQL |
| 自定义快捷键 | P2 | ❌ 待开发 | 用户可配置 |

### 10.2 开发细节

#### 10.2.1 快捷键 (已有基础)

当前支持的快捷键：
- `Ctrl+Enter` / `F5` — 执行 SQL
- `Ctrl+Shift+F` — 格式化 SQL
- `Ctrl+S` — 保存查询
- `Ctrl+N` — 新建标签
- `Ctrl+W` — 关闭标签
- `Ctrl+F` — 查找

#### 10.2.2 全局工具栏（待开发）

在 AppLayout.vue 菜单栏和主区域之间添加工具栏：

```vue
<div class="toolbar">
  <n-button-group size="tiny">
    <n-tooltip trigger="hover"><template #trigger>
      <n-button quaternary @click="newQuery">📝 查询</n-button>
    </template>新建查询</n-tooltip>
    
    <n-tooltip trigger="hover"><template #trigger>
      <n-button quaternary @click="showTableDesigner">📐 设计表</n-button>
    </template>表设计器</n-tooltip>
    
    <n-tooltip trigger="hover"><template #trigger>
      <n-button quaternary @click="showExport">📤 导出</n-button>
    </template>导出数据</n-tooltip>
    
    <n-tooltip trigger="hover"><template #trigger>
      <n-button quaternary @click="showImport">📥 导入</n-button>
    </template>导入数据</n-tooltip>
    
    <n-tooltip trigger="hover"><template #trigger>
      <n-button quaternary @click="showBackup">💾 备份</n-button>
    </template>备份/恢复</n-tooltip>
    
    <n-tooltip trigger="hover"><template #trigger>
      <n-button quaternary @click="showSync">🔄 同步</n-button>
    </template>数据同步</n-tooltip>
  </n-button-group>
</div>
```

#### 10.2.3 状态栏丰富（待开发）

在 AppLayout.vue 底部显示：
- 连接状态（已连接/未连接 + 图标）
- 当前数据库名
- 服务器版本（如果支持）
- 查询耗时（已做）
- 记录行数（已做）

---

## 11. 其他高级功能模块

### 11.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| ER 图导出 | P2 | ✅ 完成 | Mermaid.js → HTML/PDF |
| 连接池管理 | P2 | ✅ 部分 | 5min TTL 连接缓存 |
| 交互式 ER 图查看器 | P3 | ❌ 待开发 | 前端 d3.js / vis.js |
| 用户权限管理 | P3 | ❌ 待开发 | GRANT/REVOKE |
| 数据库性能监控 | P3 | ❌ 待开发 | SHOW STATUS / pg_stat |
| SQL 任务计划 | P3 | ❌ 待开发 | APScheduler |
| 数据生成器 | P3 | ❌ 待开发 | 模拟数据填充 |
| 数据透视图 | P3 | ❌ 待开发 | 图表展示 |

---

## 测试标准

### 通用测试
- [ ] 功能测试：每个 API 端点的成功/失败场景
- [ ] 边界测试：空数据、超大数据量、特殊字符
- [ ] 异常测试：网络中断、服务端错误、超时

### 测试用例模板
```python
# pytest 测试模板
def test_api_success():
    """正常场景"""
    response = client.get("/api/...")
    assert response.status_code == 200
    assert response.json()["success"] == True

def test_api_failure():
    """异常场景"""
    response = client.get("/api/...")
    assert response.status_code in (400, 404, 500)
```

---

## 代码规范

### 前端 (Vue 3 + TypeScript)
- 使用 `script setup lang="ts"` 组合式 API
- 组件名 PascalCase，文件名 kebab-case
- Props 使用 `withDefaults(defineProps<...>())` 模式
- 使用 `computed` 代替方法（除非有参数）
- 模板中使用 `n-` 前缀的 Naive UI 组件

### 后端 (Python FastAPI)
- 路由函数使用类型注解
- 使用 Pydantic 模型做请求校验
- 所有端点返回 `{"success": bool, "data": ..., "message": ...}` 格式
- 异常拦截在路由层，不向上抛

---

## 开发流程

1. 确认当前分支最新：`git pull`
2. 创建功能分支：`git checkout -b feat/模块名`
3. 实现功能（先后端 API，再前端 UI）
4. 自测功能
5. 提交：`git commit -m "feat: 功能描述"`
6. 合并到主分支

---

## 文件命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 后端路由 | 小写+下划线 | `routers/tables.py` |
| 后端核心 | 小写+下划线 | `core/backup_manager.py` |
| 前端视图 | PascalCase.vue | `views/TableBrowser.vue` |
| 前端组件 | PascalCase.vue | `components/SqlEditor.vue` |
| 前端对话框 | PascalCase.vue | `components/dialogs/SyncDialog.vue` |
| 前端 API | 小写+驼峰 | `api/index.ts` |
| 前端 Store | 小写 | `stores/app.ts` |

---

## 提交规范

```
<type>: <简短描述>

<详细说明（可选）>

Co-Authored-By: AtomCode (deepseek-v4-flash) <noreply@atomgit.com>
```

| 类型 | 说明 |
|------|------|
| feat | 新功能 |
| fix | 修复 Bug |
| refactor | 重构 |
| docs | 文档更新 |
| style | 样式/格式化 |
| perf | 性能优化 |

---

*生成时间: 2026-06-13 (v2 - 基于实际代码审查)*
