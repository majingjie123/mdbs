<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'

const router = useRouter()
const store = useAppStore()

interface TreeNode {
  label: string
  key: string
  isLeaf: boolean
  children?: TreeNode[]
  icon?: string
  connId?: number
  dbName?: string
  schemaName?: string
}

const treeData = ref<TreeNode[]>([])
const expandedKeys = ref<string[]>([])
const loading = ref(false)
const selectedKey = ref<string | null>(null)

async function refreshConnections() {
  await store.loadConnections()
  treeData.value = store.connections.map((c: any) => ({
    label: `${c.name} (${c.db_type})`,
    key: `conn-${c.id}`,
    isLeaf: false,
    icon: 'database',
    connId: c.id,
    children: [],
  }))
}

async function loadDatabases(connId: number, nodeKey: string) {
  const res: any = await api.listDatabases(connId)
  if (!res.success) return []
  return res.data.map((db: string) => ({
    label: db,
    key: `${nodeKey}/db-${db}`,
    isLeaf: false,
    connId,
    dbName: db,
    children: [],
  }))
}

async function loadTables(connId: number, dbName: string, nodeKey: string) {
  const res: any = await api.listTables(connId, dbName)
  if (!res.success) return []
  return res.data.map((t: any) => ({
    label: t.comment ? `${t.name} (${t.comment})` : t.name,
    key: `${nodeKey}/tbl-${t.name}`,
    isLeaf: true,
    connId,
    dbName,
  }))
}

async function onExpand(node: TreeNode) {
  if (node.isLeaf) return
  if (node.children && node.children.length > 0) return

  const parts = node.key.split('/')
  const isConn = parts.length === 1 && parts[0].startsWith('conn-')
  const isDb = parts.length >= 2 && parts[1].startsWith('db-')

  try {
    if (isConn) {
      const dbs = await loadDatabases(node.connId!, node.key)
      node.children = dbs
    } else if (isDb) {
      const tables = await loadTables(node.connId!, node.dbName!, node.key)
      node.children = tables
    }
  } catch (e: any) {
    node.children = [{ label: `加载失败: ${e.message}`, key: `err-${Date.now()}`, isLeaf: true }]
  }
}

function onSelect(keys: string[]) {
  if (keys.length === 0) return
  const key = keys[0]
  selectedKey.value = key

  // 查找节点
  function findNode(nodes: TreeNode[]): TreeNode | null {
    for (const n of nodes) {
      if (n.key === key) return n
      if (n.children) {
        const found = findNode(n.children)
        if (found) return found
      }
    }
    return null
  }

  const node = findNode(treeData.value)
  if (!node) return

  // 根据节点类型导航
  if (key.startsWith('conn-') && !key.includes('/')) {
    const connId = parseInt(key.replace('conn-', ''))
    store.selectConnection(connId)
    router.push(`/connections/${connId}`)
  } else if (key.includes('/tbl-')) {
    // 表节点
    const parts = key.split('/')
    const connPart = parts[0]
    const connId = parseInt(connPart.replace('conn-', ''))
    const tblPart = parts[parts.length - 1].replace('tbl-', '')
    router.push(`/tables/${connId}/${tblPart}?db=${node.dbName || ''}`)
  } else if (key.includes('/db-')) {
    // 数据库节点 - 打开工作台
    const parts = key.split('/')
    const connPart = parts[0]
    const connId = parseInt(connPart.replace('conn-', ''))
    const dbName = node.dbName || ''
    router.push(`/workbench/${connId}/${dbName}`)
  }
}

onMounted(refreshConnections)
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">MDBS</span>
    </div>

    <n-tree
      :data="treeData"
      :default-expanded-keys="expandedKeys"
      :selected-keys="selectedKey ? [selectedKey] : []"
      block-line
      :on-update:expanded-keys="(keys: string[]) => expandedKeys = keys"
      @update:selected-keys="onSelect"
      @update:expanded-keys="
        (keys: string[]) => {
          expandedKeys = keys
          for (const key of keys) {
            const find = (nodes: TreeNode[]): TreeNode | null => {
              for (const n of nodes) {
                if (n.key === key) return n
                if (n.children) {
                  const f = find(n.children)
                  if (f) return f
                }
              }
              return null
            }
            const node = find(treeData)
            if (node) onExpand(node)
          }
        }
      "
      style="flex: 1; overflow-y: auto; padding: 0 8px"
    />
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
}

.sidebar-header {
  padding: 14px 16px;
  border-bottom: 1px solid #3c3c3c;
}

.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: #cccccc;
  letter-spacing: 1px;
}
</style>
