# Tkinter Desktop 布局 → Vue3 前端 1:1 复刻开发计划

> 生成日期: 2026-05-17
> 目标: 将当前 Vue3 前端的布局和交互方式完全对齐 Tkinter 桌面版 (`ui/main_window.py`)

---

## 一、核心架构变更

### 1.1 当前架构问题

当前前端使用 **Vue Router 页面导航** 模式：点击侧边栏树节点 → `router.push()` → 切换整个 `RouterView` 工作区。这与 Tkinter 的 **标签页 (Notebook) MDI** 模式完全不同。

### 1.2 目标架构

```
AppLayout
├── MenuBar (顶层菜单栏 — 已有, 微调)
├── 分隔线 (已有)
├── SplitPane (新增 — 可拖拽分隔)
│   ├── Sidebar (改造)
│   │   ├── 标题栏: "数据库浏览器" + 折叠按钮 ◀
│   │   └── TreeView: 连接→数据库→Schema→{表/视图/函数}
│   └── TabWorkspace (新增 — 替代 RouterView)
│       ├── TabBar: 标签栏 + 关闭按钮
│       └── TabContent: 动态渲染活动标签页
└── StatusBar (已有, 微调)
```

### 1.3 组件通信

- **Pinia Store (`app.ts`)** — 管理所有打开标签页的状态
  ```ts
  interface TabItem {
    id: string
    title: string
    type: 'sql-workbench' | 'table-browser' | 'ai-chat'
    props: Record<string, any>
    closable: boolean
  }
  ```
- **provide/inject** — Sidebar 调用 `openTab()` 打开标签页
- 标签页组件通过 **Props** 接收参数（不再依赖 `useRoute()`）

---

## 二、详细改造步骤

### Step 1: 改造 Pinia Store (`stores/app.ts`)

**内容:**
- 添加 tab 状态管理: `tabs[]`, `activeTabId`
- 方法: `openTab()`, `closeTab()`, `closeOtherTabs()`, `closeAllTabs()`, `activateTab()`
- `openTab()` 逻辑: 如果已存在同类型的标签页则激活，否则新建

**涉及文件:**
- `frontend/src/stores/app.ts` — 修改

---

### Step 2: 新建 TabWorkspace 组件 (`components/TabWorkspace.vue`)

**内容:**
- `TabBar` 标签栏: 每个标签显示标题 + 关闭按钮 (✕)
- 标签支持中键点击关闭
- 右键标签弹出菜单: 关闭当前/关闭其他/全部关闭
- `TabContent` 动态组件渲染: 根据 `tab.type` 渲染对应组件
  - `sql-workbench` → `SQLWorkbench` (传入 props)
  - `table-browser` → `TableBrowser` (传入 props)
  - `ai-chat` → `AIChat` (传入 props)
- 空状态: 无标签时显示欢迎页面或连接列表

**涉及文件:**
- `frontend/src/components/TabWorkspace.vue` — 新建

---

### Step 3: 改造 Sidebar (`components/Sidebar.vue`)

**内容:**
1. **标题栏**: 改为 "数据库浏览器" + ◀ 折叠按钮（与 Tkinter 一致）
2. **树结构**: 展开节点时加载完整层级：
   - 连接 → 数据库列表
   - 数据库 (MySQL) → 📂查询 / 📂表 / 📂视图 / 📂函数/过程
   - 数据库 (PostgreSQL) → Schema 列表 → 各 Schema 下同上结构
3. **交互**: 单击展开/折叠节点 (默认不自动加载)，双击打开标签页
   - 单击连接 → 展开显示数据库（触发加载）
   - 单击数据库 → 展开显示对象（触发加载）
   - 双击表 → 在 TabWorkspace 打开 SQLWorkbench tab，初始 SQL 为 `SELECT * FROM \`table\``
4. **右键菜单**: 完整实现各节点类型菜单（对照 Tkinter）：

   **连接右键:**
   - 新建查询 / 断开连接 / 创建数据库 / 刷新数据库列表 / 编辑连接 / 删除连接

   **数据库右键:**
   - 新建查询 / 同步库结构 / 刷新 / 删除数据库

   **表右键:**
   - 查看数据 / 查询表结构 / 查看 DDL / 修改表结构 / 同步表结构 / 导入数据到该表 / 复制表名 / 生成 SELECT 语句 / 新建查询 / 刷新

   **视图右键:**
   - 查看视图定义 (DDL) / 修改视图 / 复制视图名 / 生成 SELECT 语句 / 刷新

   **函数右键:**
   - 查看定义 (DDL) / 修改函数/过程 / 复制名称 / 测试/调用 / 刷新

5. **表搜索**: 树内嵌搜索输入框，实时过滤表名（参照 Tkinter 的 `_show_search_entry`）

**涉及文件:**
- `frontend/src/components/Sidebar.vue` — 重写

---

### Step 4: 改造 AppLayout (`AppLayout.vue`)

**内容:**
1. 将 `RouterView` 替换为 `TabWorkspace`
2. 侧栏 + 工作区之间使用可拖拽分隔布局（SplitPane / resizable）
3. 菜单栏操作触发 `openTab` 或弹窗
4. 保留 Router 用于设置页等全屏页面，但主工作区由 TabWorkspace 接管

**涉及文件:**
- `frontend/src/components/AppLayout.vue` — 改造

---

### Step 5: 改造 SQLWorkbench (`views/SQLWorkbench.vue`)

**内容:**
- 从依赖 `useRoute()` 改为通过 **Props** 接收 `connId`、`dbName`、`schemaName`、`initialSql`
- 保持内部多标签查询功能不变
- 支持同时打开多个实例（每个 tab 一个实例）

**涉及文件:**
- `frontend/src/views/SQLWorkbench.vue` — 改造

---

### Step 6: 改造 TableBrowser (`views/TableBrowser.vue`)

**内容:**
- 从依赖 `useRoute()` + `route.query.db` 改为通过 **Props** 接收 `connId`, `tableName`, `dbName`
- 保持现有功能不变

**涉及文件:**
- `frontend/src/views/TableBrowser.vue` — 改造

---

### Step 7: 改造 AIChat (`views/AIChat.vue`)

**内容:**
- 从依赖 `useRoute()` 改为通过 Props 接收参数
- 支持作为标签页打开

**涉及文件:**
- `frontend/src/views/AIChat.vue` — 改造

---

### Step 8: 调整 Router (`router/index.ts`)

**内容:**
- 移除主工作区的路由（如 `/workbench/:connId`、`/tables/:connId/:table`），这些由 TabWorkspace 管理
- 保留独立页面路由（如 `/settings`、`/ai/settings`）
- 根路径 `/` 默认展示连接列表（或空 TabWorkspace 的欢迎页）

**涉及文件:**
- `frontend/src/router/index.ts` — 改造

---

### Step 9: 样式微调

**内容:**
- 树图标与 Tkinter 保持一致：📂(文件夹) 📊(表) 🖼️(视图) ⚙️(函数/过程) 🗄️(数据库) 🔌(连接)
- 标签栏样式：暗色背景、活跃标签高亮、hover 效果
- 可拖拽分隔条样式
- 确保所有组件适配深色主题

**涉及文件:**
- 多个组件样式调整

---

## 三、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/stores/app.ts` | 修改 | 添加标签页状态管理 |
| `frontend/src/components/TabWorkspace.vue` | **新建** | 标签页工作区组件 |
| `frontend/src/components/Sidebar.vue` | 重写 | 完整树层级 + 右键菜单 |
| `frontend/src/components/AppLayout.vue` | 改造 | SplitPane + TabWorkspace |
| `frontend/src/views/SQLWorkbench.vue` | 改造 | Props 化 |
| `frontend/src/views/TableBrowser.vue` | 改造 | Props 化 |
| `frontend/src/views/AIChat.vue` | 改造 | Props 化 |
| `frontend/src/router/index.ts` | 改造 | 移除主工作区路由 |

---

## 四、实施顺序

```
Step 1 (Store)
    ↓
Step 2 (TabWorkspace)
    ↓
Step 3 (Sidebar) ← 最复杂的步骤
    ↓
Step 4 (AppLayout) ← 集成的步骤
    ↓
Step 5-7 (视图改造) ← 可并行
    ↓
Step 8 (Router)
    ↓
Step 9 (样式微调)
    ↓
验证: 启动前端，测试所有交互路径
```

---

## 五、验证清单

- [ ] 侧边栏展开/折叠正常
- [ ] 连接→数据库→Schema→表/视图/函数 层级完整
- [ ] 双击连接/数据库/表/视图/函数 打开对应标签页
- [ ] 右键菜单各操作项正常工作
- [ ] 标签页打开/关闭/切换正常
- [ ] 表搜索过滤正常
- [ ] 可拖拽分隔条正常工作
- [ ] SQL 工作台在标签页中正常执行查询
- [ ] 表浏览器在标签页中正常显示
- [ ] 状态栏实时显示状态
- [ ] 无报错/Pydantic warning
