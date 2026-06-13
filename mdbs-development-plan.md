# MDBS 完整开发计划

> 全面对比 Navicat，列出所有模块的开发计划、测试标准和指导细节
> 生成时间: 2026-06-13

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
| SQL 智能提示增强 | P0 | 已有基础 | CodeMirror 6 autocompletion |
| SQL 格式化/美化 | P0 | 待开发 | sql-formatter |
| 查询历史搜索 | P1 | 已有基础 | localStorage 增强 |
| 常用 SQL 片段收藏 | P1 | 待开发 | 后端 SQLite 存储 |
| 多个查询结果分屏 | P1 | 待开发 | CSS Grid 布局 |
| 代码片段模板 | P2 | 待开发 | 内置模板 + 自定义 |
| 括号匹配高亮 | P2 | 待开发 | CodeMirror matchbrackets |
| 列名补全（完整加载） | P0 | 待优化 | 优化 loadSchema |
| JOIN 智能补全 | P1 | 待开发 | 解析 SQL 上下文 |

### 1.2 开发细节

#### 1.2.1 SQL 格式化

```bash
# 依赖安装
npm install sql-formatter
```

```typescript
// frontend/src/components/SqlEditor.vue
import { format } from 'sql-formatter'

function formatSQL() {
  const formatted = format(sqlText.value, {
    language: 'mysql',
    tabWidth: 2,
    keywordCase: 'upper',
  })
  sqlText.value = formatted
}
```

**测试用例:**
- 格式化简单 SELECT 语句
- 格式化复杂 JOIN 查询
- 格式化嵌套子查询
- 格式化 INSERT/UPDATE/DELETE
- 格式化存储过程
- 快捷键 Ctrl+Shift+F 生效
- 不同语言方言(MySQL/PostgreSQL)

#### 1.2.2 智能提示增强

**当前问题:** 只加载前 10 个表的列名

**优化方案:**
```typescript
async function loadSchema() {
  // 完整加载所有表的列名（带缓存）
  const allTables = [...tables, ...views]
  for (const t of allTables) {
    const colRes = await api.getTableColumns(connId, t, dbName)
    columns[t] = colRes.data.map(c => c.Field)
  }
}
```

**测试用例:**
- 输入 `SELECT * FROM user` 后提示 user 表的列名
- 输入 `user.` 提示该表的所有列
- 输入 `JOIN ` 提示可关联的表
- 输入 `WHERE u` 提示 users 表列名

### 1.3 代码规范

- SQL 编辑器组件: `frontend/src/components/SqlEditor.vue`
- 使用 CodeMirror 6 API
- 保持响应式，监听 connId/dbName 变化自动刷新补全

---

## 2. 数据编辑模块

### 2.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 单元格直接编辑 | P0 | 部分实现 | 双击单元格触发编辑 |
| 批量数据修改 | P0 | 待开发 | 选中多行批量更新 |
| 新增行功能 | P0 | 待开发 | 添加空行可编辑 |
| 删除行功能 | P0 | 待开发 | 选中行删除 |
| 数据筛选/过滤 | P1 | 待开发 | 表头筛选器 |
| 列头点击排序 | P1 | 待开发 | 点击列头排序 |
| 列冻结 | P2 | 待开发 | 固定列不滚动 |
| 列宽拖拽调整 | P2 | 待开发 | 拖拽调整列宽 |

### 2.2 开发细节

#### 2.2.1 单元格编辑

```typescript
// 数据编辑状态
const editingCell = ref<{ row: number, col: string } | null>(null)
const cellValue = ref('')

// 双击进入编辑
function onCellDoubleClick(row: number, col: string, value: any) {
  editingCell.value = { row, col }
  cellValue.value = value
}

// 保存修改
async function saveCellEdit() {
  const sql = `UPDATE ${tableName} SET ${col} = ? WHERE ${pkColumn} = ?`
  await api.executeSQL(connId, sql, [cellValue.value, pkValue])
}
```

**测试用例:**
- 双击单元格进入编辑模式
- 输入新值后回车保存
- 按 ESC 取消编辑
- 编辑 NULL 值
- 编辑特殊字符
- 编辑后数据刷新

#### 2.2.2 批量修改

```typescript
// 选中多行
const selectedRows = ref<Set<number>>(new Set())

// 批量更新
async function batchUpdate(column: string, value: any) {
  const pks = Array.from(selectedRows.value).map(i => rows[i][pkColumn])
  const sql = `UPDATE ${tableName} SET ${column} = ? WHERE ${pkColumn} IN (${pks.map(() => '?').join(',')})`
  await api.executeSQL(connId, sql, [value, ...pks])
}
```

**测试用例:**
- 选中多行（Ctrl+点击）
- 选中连续多行（Shift+点击）
- 批量设置某列值
- 批量删除选中行

---

## 3. 表结构管理模块

### 3.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 可视化创建表 | P0 | 待开发 | 弹窗表单 + 动态字段 |
| 可视化修改表 | P0 | 待开发 | 表设计器界面 |
| 字段类型选择 | P0 | 待开发 | 下拉选择常见类型 |
| 索引管理 | P1 | 待开发 | 索引列表 + 创建 |
| 外键管理 | P1 | 待开发 | 外键关系配置 |
| 表/字段注释 | P1 | 待开发 | 注释编辑框 |
| 表设计器拖拽 | P2 | 待开发 | 拖拽排序字段 |
| DDL 预览 | P0 | 已有 | 显示建表 SQL |

### 3.2 开发细节

#### 3.2.1 创建表对话框

```vue
<!-- 创建表对话框 -->
<template>
  <n-modal v-model="show" title="创建表">
    <n-form>
      <n-form-item label="表名">
        <n-input v-model="tableName" />
      </n-form-item>
      <!-- 字段列表 -->
      <div v-for="(col, index) in columns" :key="index" class="column-row">
        <n-input v-model="col.name" placeholder="字段名" />
        <n-select v-model="col.type" :options="typeOptions" />
        <n-switch v-model="col.nullable" />
        <n-button @click="removeColumn(index)">删除</n-button>
      </div>
      <n-button @click="addColumn">添加字段</n-button>
    </n-form>
  </n-modal>
</template>
```

**后端 API:**
```python
# backend/routers/tables.py
@router.post("/create-table")
def create_table(req: CreateTableParams, ops: DBOperations = Depends(get_db_ops)):
    # 生成 CREATE TABLE SQL 并执行
    sql = build_create_table_sql(req)
    ops.execute(sql)
    return {"success": True}
```

**测试用例:**
- 创建只有主键的表
- 创建多字段表（含各种类型）
- 创建带外键的表
- 创建带索引的表
- 验证表创建成功
- 修改已存在表结构

---

## 4. 数据库对象管理模块

### 4.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 视图(View)管理 | P1 | 已有列表 | 完善 CRUD |
| 存储过程管理 | P1 | 待开发 | 列表 + 创建/修改 |
| 函数管理 | P1 | 待开发 | 列表 + 创建/修改 |
| 触发器管理 | P2 | 待开发 | 列表 + 创建/修改 |
| 事件管理 | P2 | 待开发 | 列表 + 创建/修改 |

### 4.2 开发细节

#### 4.2.1 存储过程/函数管理

```python
# backend/routers/routines.py (新建)
@router.get("/procedures/{conn_id}")
def list_procedures(conn_id: int, database: str, ops: DBOperations = Depends(get_db_ops)):
    # MySQL: SHOW PROCEDURE STATUS
    # PostgreSQL: SELECT proname FROM pg_proc
    ...

@router.post("/procedures/{conn_id}")
def create_procedure(conn_id: int, database: str, body: dict, ops: DBOperations = Depends(get_db_ops)):
    # DELIMITER // ... CREATE PROCEDURE ... // DELIMITER ;
    ...
```

**测试用例:**
- 列出数据库中所有存储过程
- 列出所有函数
- 创建存储过程
- 修改存储过程
- 删除存储过程
- 执行存储过程

---

## 5. 查询分析模块

### 5.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| EXPLAIN 执行计划 | P1 | 待开发 | 执行 EXPLAIN SQL |
| 慢查询日志 | P2 | 待开发 | 查询 slow_log |
| 索引建议 | P2 | 待开发 | 分析查询模式 |

### 5.2 开发细节

#### 5.2.1 执行计划

```python
# backend/routers/query.py
@router.post("/explain")
def explain_query(conn_id: int, sql: str, database: str, ops: DBOperations = Depends(get_db_ops)):
    # MySQL: EXPLAIN [FORMAT=JSON] sql
    # PostgreSQL: EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) sql
    result = ops.execute(f"EXPLAIN {sql}")
    return {"success": True, "data": result}
```

**测试用例:**
- EXPLAIN SELECT 查询
- EXPLAIN UPDATE 语句
- EXPLAIN 带子查询
- 查看 JSON 格式执行计划

---

## 6. 用户权限管理模块

### 6.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 用户列表 | P2 | 待开发 | SELECT FROM mysql.user |
| 角色管理 | P2 | 待开发 | CREATE ROLE (PG) |
| 权限授予 | P2 | 待开发 | GRANT 语句 |
| 权限回收 | P2 | 待开发 | REVOKE 语句 |
| 数据库授权 | P2 | 待开发 | GRANT ON database |

### 6.2 开发细节

```python
# backend/routers/permissions.py (新建)
@router.get("/users/{conn_id}")
def list_users(conn_id: int, ops: DBOperations = Depends(get_db_ops)):
    # MySQL: SELECT user, host FROM mysql.user
    # PostgreSQL: SELECT rolname FROM pg_roles
    ...

@router.post("/grant")
def grant_permission(conn_id: int, user: str, privileges: list, database: str, ops: DBOperations = Depends(get_db_ops)):
    sql = f"GRANT {','.join(privileges)} ON {database}.* TO '{user}'@'host'"
    ops.execute(sql)
    ...
```

---

## 7. 导入导出模块

### 7.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 导出表结构(DDL) | P1 | 待开发 | 生成 CREATE TABLE |
| 导入 SQL 脚本 | P1 | 待开发 | 解析 SQL 文件 |
| 批量导出 | P2 | 待开发 | 循环导出多表 |
| 批量导入 | P2 | 待开发 | 分割 SQL 批量执行 |
| 导入导出模板 | P2 | 待开发 | 预设模板 |

### 7.2 开发细节

#### 7.2.1 导出 DDL

```python
# backend/routers/export.py
@router.post("/export/ddl")
def export_ddl(conn_id: int, database: str, tables: list[str], ops: DBOperations = Depends(get_db_ops)):
    ddl_list = []
    for table in tables:
        cols = ops.get_table_columns(table)
        ddl = f"CREATE TABLE {table} (\n"
        # 生成字段定义
        ...
        ddl_list.append(ddl)
    return {"success": True, "data": ddl_list}
```

**测试用例:**
- 导出单表 DDL
- 导出多表 DDL
- 包含索引和外键
- 导出 PostgreSQL 风格

---

## 8. 备份恢复模块

### 8.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 定时自动备份 | P2 | 待开发 | 定时任务 + mysqldump |
| 备份计划管理 | P2 | 待开发 | 计划列表 + CRUD |
| 备份文件预览 | P2 | 待开发 | 读取备份文件内容 |
| 增量备份 | P3 | 待开发 | binlog 备份 |

### 8.2 开发细节

```python
# backend/routers/backup.py 扩展
@router.post("/schedule")
def create_backup_schedule(req: BackupScheduleRequest, storage: DBStorage = Depends(get_db_storage)):
    # 存储计划到 SQLite
    schedule_id = storage.save_backup_schedule(req.dict())
    # 启动定时任务
    scheduler.add_job(backup_task, 'cron', schedule_id, ...)
    return {"success": True}

def backup_task(schedule_id: int):
    # 执行备份逻辑
    ...
```

---

## 9. 数据同步模块

### 9.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 数据对比 | P1 | 待开发 | 比对源和目标差异 |
| 选择性同步 | P1 | 待开发 | 选择表/数据同步 |
| 同步预览 | P1 | 待开发 | 生成 SQL 不执行 |

### 9.2 开发细节

#### 9.2.1 数据对比

```python
# backend/routers/sync.py 扩展
@router.post("/compare")
def compare_databases(source: dict, target: dict, ops: DBOperations = Depends(get_db_ops)):
    # 比对表结构
    source_tables = ops.get_tables()
    target_tables = ops.get_tables()
    
    diff = {
        'only_source': list(set(source_tables) - set(target_tables)),
        'only_target': list(set(target_tables) - set(source_tables)),
        'different': [],
    }
    
    # 比对表数据
    for table in set(source_tables) & set(target_tables):
        source_count = ops.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        target_count = ops.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if source_count != target_count:
            diff['different'].append({
                'table': table,
                'source_rows': source_count,
                'target_rows': target_count,
            })
    
    return {"success": True, "data": diff}
```

---

## 10. UI/UX 优化模块

### 10.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| 收藏夹 | P1 | 待开发 | 收藏连接/查询 |
| 最近使用记录 | P1 | 待开发 | 历史记录列表 |
| 快捷键完善 | P1 | 部分 | 补充更多快捷键 |
| 右键菜单 | P1 | 部分 | 完善上下文菜单 |
| 状态栏信息 | P1 | 部分 | 显示更多信息 |
| 加载状态优化 | P0 | 待优化 | 骨架屏/进度条 |

### 10.2 开发细节

#### 10.2.1 快捷键

| 快捷键 | 功能 |
|--------|------|
| F5 / Ctrl+Enter | 执行 SQL |
| Ctrl+Shift+F | 格式化 SQL |
| Ctrl+S | 保存当前查询 |
| Ctrl+N | 新建查询标签 |
| Ctrl+W | 关闭当前标签 |
| Ctrl+Tab | 切换标签 |
| Ctrl+F | 查找 |
| Ctrl+H | 替换 |

```typescript
// frontend/src/components/SqlEditor.vue 扩展
keymap.of([
  { key: 'Mod-Enter', run: () => { emit('execute'); return true } },
  { key: 'F5', run: () => { emit('execute'); return true } },
  { key: 'Mod-Shift-f', run: () => { emit('format'); return true } },
  // 新增
  { key: 'Mod-s', run: () => { emit('save'); return true } },
  { key: 'Mod-n', run: () => { emit('newTab'); return true } },
])
```

---

## 11. 其他高级功能模块

### 11.1 功能列表

| 功能点 | 优先级 | 状态 | 技术方案 |
|--------|--------|------|----------|
| ER 图/关系图 | P2 | 待开发 | 图形化展示表关系 |
| 连接池管理 | P2 | 待开发 | 显示连接状态 |
| 性能监控 | P2 | 待开发 | 查询状态/缓存命中率 |
| SQL 任务计划 | P3 | 待开发 | 定时执行 SQL |

### 11.2 开发细节

#### 11.2.1 ER 图

```python
# backend/routers/er_diagram.py (新建)
@router.get("/er-diagram/{conn_id}")
def get_er_diagram(conn_id: int, database: str, ops: DBOperations = Depends(get_db_ops)):
    # 获取所有表的外键关系
    tables = ops.get_tables()
    relations = []
    for table in tables:
        foreign_keys = ops.get_foreign_keys(table)
        for fk in foreign_keys:
            relations.append({
                'from': table,
                'from_col': fk['column'],
                'to': fk['ref_table'],
                'to_col': fk['ref_column'],
            })
    return {"success": True, "data": {"tables": tables, "relations": relations}}
```

---

## 测试标准

### 通用测试

1. **功能测试** - 每个功能点必须有测试用例
2. **边界测试** - 空值、特殊字符、超长内容
3. **错误处理** - 网络断开、权限不足、SQL 错误
4. **UI 响应** - 加载状态、动画流畅

### 测试用例模板

```typescript
describe('SQL格式化', () => {
  test('格式化简单SELECT', () => {
    const input = 'select id,name from users where id=1'
    const output = format(input, { language: 'mysql' })
    expect(output).toContain('SELECT')
  })
  
  test('格式化复杂JOIN', () => {
    // 多表关联
  })
  
  test('快捷键触发', () => {
    // Ctrl+Shift+F
  })
})
```

---

## 代码规范

### 前端 (Vue 3 + TypeScript)

- 使用 Composition API: `<script setup lang="ts">`
- 组件文件: `frontend/src/components/`
- 页面文件: `frontend/src/views/`
- API 方法: `frontend/src/api/index.ts`
- 状态管理: `frontend/src/stores/app.ts`
- UI 库: 只使用 Naive UI

### 后端 (Python FastAPI)

- 路由文件: `backend/routers/`
- 业务逻辑: `backend/core/`
- 数据模型: `backend/models/`
- Schema: `backend/schemas.py`
- 日志: 使用 `logging` 模块

---

## 开发流程

1. **需求确认** - 明确功能细节
2. **技术方案** - 确定实现方式
3. **API 设计** - 后端接口定义
4. **前端开发** - 组件实现
5. **联调测试** - 前后端对接
6. **自测验证** - 功能测试
7. **代码提交** - Git 提交规范

---

## 文件命名规范

| 类型 | 命名规范 | 示例 |
|------|----------|------|
| 组件 | 大驼峰 | `SqlEditor.vue` |
| 页面 | 大驼峰 | `SQLWorkbench.vue` |
| API 方法 | 驼峰 | `listConnections` |
| 路由 | 小写下划线 | `/api/connections` |
| 后端文件 | 小写下划线 | `db_operations.py` |

---

## 提交规范

```
feat: 新增SQL格式化功能
- 安装 sql-formatter 依赖
- 添加格式化按钮和快捷键
- 支持 MySQL/PostgreSQL 方言

fix: 修复单元格编辑问题
- 编辑空值时报错
- 批量编辑不生效

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

*文档版本: 1.0*
*最后更新: 2026-06-13*