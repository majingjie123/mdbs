# 缺失功能补全计划

## 阶段一：SQLWorkbench 高级功能 (P0)

### 步骤 1.1 — 中止执行按钮
- 文件: `frontend/src/views/SQLWorkbench.vue`
- 在工具栏右侧添加"■ 停止"按钮，`running` 状态时显示
- 使用 `AbortController` 中止 `api.executeSQL` 请求
- 影响范围: script (添加 abortController ref) + template + api/index.ts (让 executeSQL 支持 signal)

### 步骤 1.2 — 分页大小选择器
- 文件: `frontend/src/views/SQLWorkbench.vue`
- 在分页栏添加 `n-select`，选项: 10/50/100/500/1000/5000
- 替换硬编码 `pageSize = ref(100)` 为可配置

### 步骤 1.3 — Ctrl+F 查找栏
- 文件: `frontend/src/views/SQLWorkbench.vue`
- 添加查找状态: `findVisible`, `findText`, `findMatchCount`, `findCurrentIdx`
- 在编辑器面板上方添加查找栏: 输入框 + ↑↓ 导航 + 计数显示 + 关闭按钮
- 快捷键: Ctrl+F 显示, Escape 关闭, Enter/F3 下一个, Shift+F3 上一个
- SqlEditor 组件需暴露 `findText()` / 高亮方法；或由 SQLWorkbench 自行实现查找导航

### 步骤 1.4 — 保存/打开 SQL 文件
- 文件: `frontend/src/views/SQLWorkbench.vue`
- 工具栏添加"保存"按钮 → `saveAs` (Blob download .sql)
- 工具栏添加"打开"按钮 → `file input` 读取 .sql 文件内容到当前标签
- 使用 `<input type="file" accept=".sql" hidden>` + click 触发

### 步骤 1.5 — 导出 Excel
- 文件: `frontend/src/views/SQLWorkbench.vue`
- 在导出按钮旁添加"导出 Excel"按钮
- 使用 SheetJS (xlsx) 库将结果转为 .xlsx 并下载
- 需要 `npm install xlsx` 或使用后端 API 导出

### 步骤 1.6 — 列排序 + 列筛选
- 文件: `frontend/src/views/SQLWorkbench.vue`
- 列排序: 点击列头切换升序/降序/无排序，`n-data-table` 原生支持 `@update:sorter`
- 列筛选: 添加 filter 状态，点击列头筛选图标弹出 n-input，过滤行数据

### 步骤 1.7 — 复制为 INSERT / UPDATE
- 文件: `frontend/src/views/SQLWorkbench.vue`
- 在结果工具栏添加"复制为 INSERT"和"复制为 UPDATE"按钮
- `copyAsInsert()`: 生成 INSERT INTO table (cols) VALUES (vals);
- `copyAsUpdate()`: 生成 UPDATE table SET col=val WHERE ...

## 阶段二：TableBrowser 编辑能力 (P0)

### 步骤 2.1 — 字段内联编辑
- 文件: `frontend/src/views/TableBrowser.vue`
- 双击字段单元格进入编辑模式
- 修改字段名/类型/默认值/注释
- 添加/删除字段按钮
- 修改预览 SQL 按钮（自动生成 ALTER TABLE）
- 保存修改按钮（执行 ALTER TABLE）

### 步骤 2.2 — 索引管理
- 文件: `frontend/src/views/TableBrowser.vue`
- 索引标签页: 添加/删除索引行
- 修改索引属性

## 阶段三：Sidebar 存根填充 (P0-P1)

### 步骤 3.1 — 右键菜单存根功能实现
- 文件: `frontend/src/components/Sidebar.vue`
- `create-db`: 弹出 `n-modal` 输入数据库名 → 调用 `api.createDatabase`
- `sync-structure`: 打开 SynDialog 并预填源连接/库
- `view-structure`: 打开 TableBrowser 标签页（已有 `alter-table` 动作可用）
- `view-ddl`: 在 sql-workbench 标签页执行 `SHOW CREATE TABLE`
- `sync-table`: 打开 SyncDialog 预填表名
- `import-to-table`: 打开 ImportDialog 预填表名

### 步骤 3.2 — 表名搜索/过滤框
- 文件: `frontend/src/components/Sidebar.vue`
- 在侧栏标题下方添加搜索输入框
- 输入时动态过滤树节点显示的表名
- 使用 `n-input` + 计算属性过滤 `treeData`

### 步骤 3.3 — 断开连接实现
- 文件: `frontend/src/components/Sidebar.vue`
- `disconnect` 动作: 调用 `api.disconnect(connId)` 关闭后端连接池/SSH隧道

## 阶段四：连接编辑增强 (P1)

### 步骤 4.1 — 测试 SSH 按钮
- 文件: `frontend/src/views/ConnectionDetail.vue`
- 添加"测试 SSH"按钮
- 调用 `api.testSshConnection(formValue)`
- 后端需添加 `test_ssh` 端点（或复用已有）

### 步骤 4.2 — 私钥文件浏览器
- 文件: `frontend/src/views/ConnectionDetail.vue`
- 私钥路径输入框旁添加"浏览"按钮
- 使用 `<input type="file" accept=".pub,.ppk,.pem" hidden>` 触发文件选择

## 阶段五：菜单栏补全 (P1)

### 步骤 5.1 — 添加"编辑"/"查看"/"帮助"菜单
- 文件: `frontend/src/components/AppLayout.vue`
- "编辑": 撤销/重做/剪切/复制/粘贴/查找
- "查看": 切换侧边栏/切换状态栏/全屏
- "帮助": 关于/版本信息

### 步骤 5.2 — ER 导出菜单项
- 文件: `frontend/src/components/AppLayout.vue`
- 在文件菜单中添加"导出 ER 图..."
- 调用 api 导出

## 阶段六：功能/视图管理对话框 (P1)

### 步骤 6.1 — ViewManagerDialog 基础实现
- 新建: `frontend/src/components/dialogs/ViewManagerDialog.vue`
- 查看/编辑视图 DDL
- 执行修改

### 步骤 6.2 — FunctionManagerDialog 基础实现
- 新建: `frontend/src/components/dialogs/FunctionManagerDialog.vue`
- 查看/编辑函数 DDL
- 测试函数（生成 SELECT/CALL）

## 阶段七：验证 (P0)

### 步骤 7.1 — 构建验证
- `npx vue-tsc --noEmit`
- `npx vite build`
- 修复所有类型错误和构建警告

---

## 文件变更清单

| 文件 | 阶段 | 操作 |
|------|------|------|
| `frontend/src/views/SQLWorkbench.vue` | 一 | 修改 (7个子步骤) |
| `frontend/src/api/index.ts` | 一 | 修改 (signal 参数) |
| `frontend/src/views/TableBrowser.vue` | 二 | 修改 |
| `frontend/src/components/Sidebar.vue` | 三 | 修改 |
| `frontend/src/views/ConnectionDetail.vue` | 四 | 修改 |
| `frontend/src/components/AppLayout.vue` | 五 | 修改 |
| `frontend/src/components/dialogs/ViewManagerDialog.vue` | 六 | 新建 |
| `frontend/src/components/dialogs/FunctionManagerDialog.vue` | 六 | 新建 |
