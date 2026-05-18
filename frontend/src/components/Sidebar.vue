<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import SyncDialog from './dialogs/SyncDialog.vue'
import ImportDialog from './dialogs/ImportDialog.vue'

const message = useMessage()
const dialog = useDialog()
const store = useAppStore()

// ── 树节点接口 ──
interface TreeNode {
  label: string
  key: string
  isLeaf: boolean
  children?: TreeNode[]
  connId?: number
  dbName?: string
  schemaName?: string
  nodeType?: string
  rawData?: any
}

const treeData = ref<TreeNode[]>([])
const expandedKeys = ref<string[]>([])
const selectedKey = ref<string | null>(null)
const loadingSet = ref<Set<string>>(new Set())
const tableCache = ref<Map<string, any[]>>(new Map())

// 搜索
const searchQuery = ref('')

// 侧栏折叠
const collapsed = ref(false)

// 对话框状态
const showSyncDialog = ref(false)
const syncDialogProps = ref<{ connId?: number; dbName?: string; tableName?: string }>({})
const showImportDialog = ref(false)
const importDialogProps = ref<{ connId?: number; dbName?: string; tableName?: string }>({})
const showCreateDbDialog = ref(false)
const createDbConnId = ref(0)
const newDbName = ref('')
const creatingDb = ref(false)

async function doCreateDb() {
  if (!newDbName.value.trim()) {
    message.warning('请输入数据库名称')
    return
  }
  creatingDb.value = true
  try {
    const res: any = await api.createDatabase(createDbConnId.value, newDbName.value.trim())
    if (res.success) {
      message.success(`数据库 ${newDbName.value} 创建成功`)
      showCreateDbDialog.value = false
      newDbName.value = ''
      refreshConnections()
    } else {
      message.error(res.message || '创建失败')
    }
  } catch (e: any) {
    message.error('创建失败: ' + (e.message || '未知错误'))
  } finally {
    creatingDb.value = false
  }
}

// 右键菜单
const ctxMenu = ref({ visible: false, x: 0, y: 0, node: null as TreeNode | null })
const ctxMenuItems = computed(() => getMenuItems(ctxMenu.value.node?.nodeType ?? ''))

// ── 初始化加载连接列表 ──
async function refreshConnections() {
  await store.loadConnections()
  treeData.value = store.connections.map((c: any) => ({
    label: c.name,
    key: `conn-${c.id}`,
    isLeaf: false,
    nodeType: 'connection',
    connId: c.id,
    children: [],
  }))
}

// ── 加载数据库列表 ──
async function loadDatabases(connId: number, nodeKey: string): Promise<TreeNode[]> {
  const res: any = await api.listDatabases(connId)
  if (!res.success) return [{ label: '加载失败', key: `${nodeKey}/err`, isLeaf: true }]
  return res.data.map((db: string) => ({
    label: db,
    key: `${nodeKey}/db-${db}`,
    isLeaf: false,
    nodeType: 'database',
    connId,
    dbName: db,
    children: [],
  }))
}

// ── 加载 Schema 列表 (PostgreSQL) ──
async function loadSchemas(connId: number, dbName: string, nodeKey: string): Promise<TreeNode[]> {
  const res: any = await api.listSchemas(connId, dbName)
  if (!res.success) return [{ label: '加载失败', key: `${nodeKey}/err`, isLeaf: true }]
  return res.data.map((s: string) => ({
    label: s,
    key: `${nodeKey}/schema-${s}`,
    isLeaf: false,
    nodeType: 'schema',
    connId,
    dbName,
    schemaName: s,
    children: [],
  }))
}

// ── 加载数据库对象（表/视图/函数） ──
async function loadDbObjects(connId: number, dbName: string, schemaName: string | undefined, nodeKey: string): Promise<TreeNode[]> {
  const children: TreeNode[] = []

  // 查询文件夹
  const qFolderKey = `${nodeKey}/queries`
  children.push({
    label: '📂 查询',
    key: qFolderKey,
    isLeaf: false,
    nodeType: 'folder',
    connId,
    dbName,
    children: [],
  })

  // 表文件夹
  const tFolderKey = `${nodeKey}/tables`
  children.push({
    label: '📂 表',
    key: tFolderKey,
    isLeaf: false,
    nodeType: 'folder',
    connId,
    dbName,
    children: [],
  })

  // 视图文件夹
  const vFolderKey = `${nodeKey}/views`
  children.push({
    label: '📂 视图',
    key: vFolderKey,
    isLeaf: false,
    nodeType: 'folder',
    connId,
    dbName,
    children: [],
  })

  // 函数/过程文件夹
  const fFolderKey = `${nodeKey}/funcs`
  children.push({
    label: '📂 函数/过程',
    key: fFolderKey,
    isLeaf: false,
    nodeType: 'folder',
    connId,
    dbName,
    children: [],
  })

  return children
}

// ── 加载表列表 ──
async function loadTablesIntoFolder(folderNode: TreeNode) {
  const { connId, dbName, schemaName, key } = folderNode
  if (!connId) return
  const res: any = await api.listTables(connId, dbName, schemaName)
  if (!res.success) {
    folderNode.children = [{ label: '加载失败', key: `${key}/err`, isLeaf: true }]
    return
  }
  tableCache.value.set(key, res.data)
  folderNode.children = res.data.map((t: any) => ({
    label: t.comment ? `${t.name}  (${t.comment})` : t.name,
    key: `${key}/tbl-${t.name}`,
    isLeaf: true,
    nodeType: 'table',
    connId,
    dbName,
    schemaName,
    rawData: t,
  }))
}

// ── 加载视图列表 ──
async function loadViewsIntoFolder(folderNode: TreeNode) {
  const { connId, dbName, schemaName, key } = folderNode
  if (!connId) return
  const res: any = await api.listViews?.(connId, dbName, schemaName)
  if (!res?.success) {
    folderNode.children = []
    return
  }
  folderNode.children = (res.data || []).map((v: any) => ({
    label: typeof v === 'string' ? v : v.name,
    key: `${key}/view-${typeof v === 'string' ? v : v.name}`,
    isLeaf: true,
    nodeType: 'view',
    connId,
    dbName,
    schemaName,
  }))
}

// ── 加载函数列表 ──
async function loadFuncsIntoFolder(folderNode: TreeNode) {
  const { connId, dbName, schemaName, key } = folderNode
  if (!connId) return
  const res: any = await api.listFunctions?.(connId, dbName, schemaName)
  if (!res?.success) {
    folderNode.children = []
    return
  }
  folderNode.children = (res.data || []).map((f: any) => ({
    label: `${f.type === 'PROCEDURE' ? '⚙️' : 'ƒ'} ${f.name}`,
    key: `${key}/func-${f.name}`,
    isLeaf: true,
    nodeType: 'function',
    connId,
    dbName,
    schemaName,
    rawData: f,
  }))
}

// ── 展开节点事件 ──
async function onExpand(node: TreeNode) {
  if (node.isLeaf) return
  if (node.children && node.children.length > 0) return

  const parts = node.key.split('/')
  const topLevel = parts[0]

  try {
    if (topLevel.startsWith('conn-') && parts.length === 1) {
      // 连接 → 加载数据库
      node.children = await loadDatabases(node.connId!, node.key)
    } else if (parts.some((p) => p.startsWith('db-')) && parts.length === 2) {
      // 数据库 → 检查是否是 PostgreSQL 需要加载 schema
      const connData = store.connections.find((c) => c.id === node.connId)
      if (connData?.db_type === 'PostgreSQL') {
        node.children = await loadSchemas(node.connId!, node.dbName!, node.key)
      } else {
        node.children = await loadDbObjects(node.connId!, node.dbName!, undefined, node.key)
      }
    } else if (parts.some((p) => p.startsWith('schema-')) && parts.length === 3) {
      // Schema → 加载对象
      node.children = await loadDbObjects(node.connId!, node.dbName!, node.schemaName, node.key)
    } else if (parts.some((p) => p === 'tables')) {
      // 表文件夹 → 加载表
      await loadTablesIntoFolder(node)
    } else if (parts.some((p) => p === 'views')) {
      await loadViewsIntoFolder(node)
    } else if (parts.some((p) => p === 'funcs')) {
      await loadFuncsIntoFolder(node)
    } else {
      node.children = []
    }
  } catch (e: any) {
    node.children = [{ label: `❌ ${e.message || '加载失败'}`, key: `${node.key}/err`, isLeaf: true }]
  }
}

// ── 选择节点事件（单击） ──
function onSelect(keys: string[]) {
  if (keys.length === 0) {
    selectedKey.value = null
    store.clearSelectedNode()
    return
  }
  selectedKey.value = keys[0]

  // 查找选中的节点
  const findNode = (nodes: TreeNode[]): TreeNode | null => {
    for (const n of nodes) {
      if (n.key === keys[0]) return n
      if (n.children) { const f = findNode(n.children); if (f) return f }
    }
    return null
  }
  const node = findNode(treeData.value)
  if (node) {
    const connData = store.connections.find((c: any) => c.id === node.connId)
    store.updateSelectedNode({
      connId: node.connId || null,
      connName: connData?.name || '',
      dbName: node.dbName || '',
      schemaName: node.schemaName || '',
      tableName: node.rawData?.name || '',
      nodeType: node.nodeType || '',
    })
  }
}

// ── 双击节点事件 ──
function onDblClick(node: TreeNode) {
  if (!node) return
  const type = node.nodeType

  if (type === 'connection' || type === 'database' || type === 'schema' || type === 'folder') {
    return // 这些类型双击不打开标签
  }

  // 表/视图 → 打开 SQLWorkbench
  if (type === 'table' || type === 'view') {
    const name = node.rawData?.name || node.label.split('  ')[0]
    let initialSql = ''
    const connData = store.connections.find((c) => c.id === node.connId)
    if (connData?.db_type === 'PostgreSQL') {
      const schema = node.schemaName || 'public'
      initialSql = `SELECT * FROM "${schema}"."${name}" LIMIT 1000;`
    } else {
      initialSql = `SELECT * FROM \`${name}\` LIMIT 1000;`
    }
    store.openTab('sql-workbench', name, {
      connId: node.connId,
      dbName: node.dbName || '',
      schemaName: node.schemaName || '',
      initialSql,
    })
    return
  }

  // 函数 → 查看 DDL（待后续实现，先开空工作台）
  if (type === 'function') {
    store.openTab('sql-workbench', node.label, {
      connId: node.connId,
      dbName: node.dbName || '',
      schemaName: node.schemaName || '',
      initialSql: '',
    })
  }
}

// ── 展开/折叠逻辑 ──
function onUpdateExpandedKeys(keys: string[]) {
  const newlyExpanded = keys.filter((k) => !expandedKeys.value.includes(k))
  expandedKeys.value = keys
  for (const key of newlyExpanded) {
    const find = (nodes: TreeNode[]): TreeNode | null => {
      for (const n of nodes) {
        if (n.key === key) return n
        if (n.children) { const f = find(n.children); if (f) return f }
      }
      return null
    }
    const node = find(treeData.value)
    if (node) onExpand(node)
  }
}

// ── 右键菜单 ──
// 使用 n-tree 的 :node-props 回调为每个节点注入 onContextmenu 原生事件
function handleNodeProps({ option }: { option: any }) {
  return {
    onContextmenu: (e: MouseEvent) => {
      e.preventDefault()
      ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, node: option as TreeNode }
    }
  }
}

function closeCtxMenu() { ctxMenu.value.visible = false }

function handleCtxAction(action: string | undefined) {
  if (!action) return
  const node = ctxMenu.value.node
  if (!node) return
  closeCtxMenu()

  const connId = node.connId
  const dbName = node.dbName || ''
  const schemaName = node.schemaName || ''
  const tableName = node.rawData?.name || node.label.split('  (')[0]

  switch (action) {
    // ── 连接 ──
    case 'new-query':
      store.openTab('sql-workbench', `查询 - ${dbName || connId}`, { connId, dbName, schemaName, initialSql: '' })
      break
    case 'disconnect':
      if (connId) {
        api.disconnectConnection(connId).then(() => {
          refreshConnections()
          message.success('已断开连接')
        }).catch(() => {
          refreshConnections()
          message.success('已断开连接')
        })
      }
      break
    case 'create-db':
      if (connId) {
        createDbConnId.value = connId
        showCreateDbDialog.value = true
      }
      break
    case 'refresh':
      node.children = []
      expandedKeys.value = [...expandedKeys.value]
      onExpand(node)
      break
    case 'edit-connection':
      store.openTab('connection-detail', `编辑 - ${node.label}`, { id: connId, edit: 1 }, true)
      break
    case 'delete-connection':
      dialog.warning({
        title: '删除连接',
        content: '确定要删除该连接吗？',
        positiveText: '删除',
        negativeText: '取消',
        onPositiveClick: async () => {
          if (connId) {
            await api.deleteConnection(connId)
            refreshConnections()
            message.success('已删除')
          }
        },
      })
      break

    // ── 数据库 ──
    case 'sync-structure':
      syncDialogProps.value = { connId, dbName }
      showSyncDialog.value = true
      break
    case 'delete-database':
      dialog.warning({
        title: '删除数据库',
        content: `确定要删除数据库 ${dbName} 吗？此操作不可撤销。`,
        positiveText: '删除',
        negativeText: '取消',
        onPositiveClick: async () => {
          if (connId && dbName) {
            try {
              await api.deleteDatabase(connId, dbName)
              message.success(`数据库 ${dbName} 已删除`)
              refreshConnections()
            } catch (e: any) {
              message.error('删除失败: ' + (e.message || '未知错误'))
            }
          }
        },
      })
      break

    // ── 表 ──
    case 'view-data': {
      const name = node.rawData?.name || node.label.split('  (')[0]
      store.openTab('sql-workbench', name, {
        connId, dbName, schemaName,
        initialSql: `SELECT * FROM \`${name}\` LIMIT 1000;`,
      })
      break
    }
    case 'view-structure':
      store.openTab('table-browser', tableName, { connId, tableName, dbName, schemaName })
      break
    case 'view-ddl': {
      store.openTab('sql-workbench', `DDL: ${tableName}`, {
        connId, dbName, schemaName,
        initialSql: `SHOW CREATE TABLE \`${tableName}\`;`,
      })
      break
    }
    case 'alter-table':
      store.openTab('table-browser', tableName, { connId, tableName, dbName, schemaName })
      break
    case 'copy-name': {
      navigator.clipboard.writeText(tableName)
      message.success(`已复制: ${tableName}`)
      break
    }
    case 'generate-select':
      navigator.clipboard.writeText(`SELECT * FROM \`${tableName}\``)
      message.success('已复制 SELECT 语句')
      break
    case 'import-to-table':
      importDialogProps.value = { connId, dbName, tableName }
      showImportDialog.value = true
      break
    case 'sync-table':
      syncDialogProps.value = { connId, dbName, tableName }
      showSyncDialog.value = true
      break

    // ── 视图 ──
    case 'manage-view':
      store.openTab('table-browser', tableName, { connId, tableName, dbName, schemaName })
      break
    case 'view-view-ddl':
      store.openTab('sql-workbench', `DDL: ${tableName}`, {
        connId, dbName, schemaName,
        initialSql: `SHOW CREATE VIEW \`${tableName}\`;`,
      })
      break
    case 'copy-view-name':
      navigator.clipboard.writeText(tableName)
      message.success(`已复制: ${tableName}`)
      break
    case 'generate-view-select':
      navigator.clipboard.writeText(`SELECT * FROM \`${tableName}\``)
      message.success('已复制 SELECT 语句')
      break

    // ── 函数 ──
    case 'manage-func':
      store.openTab('sql-workbench', `管理: ${tableName}`, {
        connId, dbName, schemaName,
        initialSql: `SHOW CREATE FUNCTION \`${tableName}\``,
      })
      break
    case 'view-func-ddl':
      store.openTab('sql-workbench', `DDL: ${tableName}`, {
        connId, dbName, schemaName,
        initialSql: `SHOW CREATE FUNCTION \`${tableName}\`;`,
      })
      break
    case 'copy-func-name':
      navigator.clipboard.writeText(node.label)
      message.success(`已复制: ${node.label}`)
      break
    default:
      message.info(`功能 ${action} 开发中`)
  }
}

// ── 右键菜单项定义 ──
function getMenuItems(nodeType: string = '') {
  switch (nodeType) {
    case 'connection':
      return [
        { label: '新建查询', action: 'new-query' },
        { separator: true },
        { label: '断开连接', action: 'disconnect' },
        { label: '创建数据库...', action: 'create-db' },
        { label: '刷新数据库列表', action: 'refresh' },
        { separator: true },
        { label: '编辑连接...', action: 'edit-connection' },
        { label: '删除连接', action: 'delete-connection' },
      ]
    case 'database':
      return [
        { label: '新建查询', action: 'new-query' },
        { separator: true },
        { label: '同步库结构...', action: 'sync-structure' },
        { separator: true },
        { label: '刷新', action: 'refresh' },
        { label: '删除数据库', action: 'delete-database' },
      ]
    case 'table':
      return [
        { label: '查看数据', action: 'view-data' },
        { separator: true },
        { label: '查询表结构', action: 'view-structure' },
        { label: '查看 DDL', action: 'view-ddl' },
        { label: '修改表结构', action: 'alter-table' },
        { separator: true },
        { label: '同步表结构...', action: 'sync-table' },
        { label: '📥 导入数据到该表...', action: 'import-to-table' },
        { separator: true },
        { label: '复制表名', action: 'copy-name' },
        { label: '生成 SELECT 语句', action: 'generate-select' },
        { separator: true },
        { label: '新建查询', action: 'new-query' },
        { label: '刷新', action: 'refresh' },
      ]
    case 'view':
      return [
        { label: '管理视图', action: 'manage-view' },
        { separator: true },
        { label: '查看视图定义 (DDL)', action: 'view-view-ddl' },
        { separator: true },
        { label: '复制视图名', action: 'copy-view-name' },
        { label: '生成 SELECT 语句', action: 'generate-view-select' },
        { separator: true },
        { label: '刷新', action: 'refresh' },
      ]
    case 'function':
      return [
        { label: '管理函数', action: 'manage-func' },
        { separator: true },
        { label: '查看定义 (DDL)', action: 'view-func-ddl' },
        { separator: true },
        { label: '复制名称', action: 'copy-func-name' },
        { separator: true },
        { label: '刷新', action: 'refresh' },
      ]
    default:
      return [
        { label: '新建查询', action: 'new-query' },
        { label: '刷新', action: 'refresh' },
      ]
  }
}

// 点击文档关闭右键菜单 + AI 入口
function onDocClick() { closeCtxMenu() }
onMounted(() => { document.addEventListener('click', onDocClick); refreshConnections() })
onUnmounted(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- 标题栏 -->
    <div class="sidebar-header">
      <span v-if="!collapsed" class="sidebar-title">数据库浏览器</span>
      <button class="toggle-btn" @click="collapsed = !collapsed" :title="collapsed ? '展开' : '折叠'">
        {{ collapsed ? '▶' : '◀' }}
      </button>
    </div>

    <!-- 搜索框 -->
    <div v-show="!collapsed" class="sidebar-search">
      <n-input
        v-model:value="searchQuery"
        placeholder="搜索表名..."
        size="tiny"
        clearable
        :style="{ margin: '4px 8px' }"
      >
        <template #prefix>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/></svg>
        </template>
      </n-input>
    </div>

    <!-- 树 -->
    <div v-show="!collapsed" class="tree-container">
      <n-tree
        :data="treeData as any"
        :default-expanded-keys="expandedKeys"
        :selected-keys="selectedKey ? [selectedKey] : []"
        :pattern="searchQuery"
        block-line
        :virtual-scroll="false"
        @update:selected-keys="onSelect"
        @update:expanded-keys="onUpdateExpandedKeys"
        :node-props="handleNodeProps"
        style="flex: 1; overflow-y: auto; padding: 2px 4px"
      />
    </div>

    <!-- 创建数据库对话框 -->
    <n-modal v-model:show="showCreateDbDialog" title="创建数据库" preset="card" style="width: 400px">
      <n-input v-model:value="newDbName" placeholder="输入数据库名称" />
      <template #footer>
        <n-button @click="showCreateDbDialog = false">取消</n-button>
        <n-button type="primary" @click="doCreateDb" :loading="creatingDb">创建</n-button>
      </template>
    </n-modal>

    <!-- 同步对话框 -->
    <SyncDialog v-model:visible="showSyncDialog" :conn-id="syncDialogProps.connId" :db-name="syncDialogProps.dbName" :table-name="syncDialogProps.tableName" />

    <!-- 导入对话框 -->
    <ImportDialog v-model:visible="showImportDialog" :conn-id="importDialogProps.connId" :db-name="importDialogProps.dbName" :table-name="importDialogProps.tableName" />

    <!-- 右键菜单（teleport 到 body） -->
    <teleport to="body">
      <div
        v-if="ctxMenu.visible"
        class="context-menu"
        :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
        @click.stop
      >
        <template v-for="(item, idx) in ctxMenuItems" :key="idx">
          <div v-if="item.separator" class="ctx-sep"></div>
          <div v-else class="ctx-item" @click="handleCtxAction(item.action)">{{ item.label }}</div>
        </template>
      </div>
    </teleport>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  min-width: 260px;
  background: #252526;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #3c3c3c;
  user-select: none;
  transition: width 0.2s, min-width 0.2s;
  overflow: hidden;
}

.sidebar.collapsed {
  width: 35px;
  min-width: 35px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 10px;
  border-bottom: 1px solid #3c3c3c;
  flex-shrink: 0;
}

.sidebar-search {
  flex-shrink: 0;
  border-bottom: 1px solid #3c3c3c;
  padding-bottom: 4px;
}

.sidebar-title {
  font-size: 12px;
  font-weight: 600;
  color: #cccccc;
}

.toggle-btn {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 2px 6px;
  font-size: 11px;
  border-radius: 3px;
}

.toggle-btn:hover {
  background: #3c3c3c;
  color: #fff;
}

.tree-container {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* 右键菜单（用 :global() 确保 teleport 到 body 的样式生效）*/
:global(.context-menu) {
  position: fixed;
  z-index: 9999;
  min-width: 190px;
  background: #3c3f41;
  border: 1px solid #555;
  border-radius: 4px;
  padding: 4px 0;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

:global(.ctx-item) {
  padding: 5px 16px;
  cursor: pointer;
  color: #ccc;
  font-size: 12px;
  white-space: nowrap;
}

:global(.ctx-item:hover) {
  background: #4c4f51;
  color: #fff;
}

:global(.ctx-sep) {
  height: 1px;
  background: #555;
  margin: 4px 8px;
}
</style>
