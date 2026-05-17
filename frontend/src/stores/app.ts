import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'

export interface TabItem {
  id: string
  title: string
  type: 'sql-workbench' | 'table-browser' | 'ai-chat' | 'connection-list'
  props: Record<string, any>
  closable: boolean
}

export const useAppStore = defineStore('app', () => {
  const connections = ref<any[]>([])
  const currentConnId = ref<number | null>(null)
  const currentDb = ref('')
  const sidebarExpanded = ref(true)

  // ── 标签页管理 ──
  const tabs = ref<TabItem[]>([])
  const activeTabId = ref<string | null>(null)

  const currentConn = computed(() =>
    connections.value.find((c) => c.id === currentConnId.value) || null,
  )

  const activeTab = computed(() =>
    tabs.value.find((t) => t.id === activeTabId.value) || null,
  )

  async function loadConnections() {
    const res: any = await api.listConnections()
    if (res.success) connections.value = res.data
  }

  function selectConnection(id: number) {
    currentConnId.value = id
  }

  // ── 标签页操作 ──
  function _genId(): string {
    return `tab_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  }

  function openTab(type: TabItem['type'], title: string, props: Record<string, any> = {}, closable = true) {
    // 如果同类型同 props 的标签已存在，直接激活
    const existing = tabs.value.find(
      (t) => t.type === type && _propsMatch(t.props, props),
    )
    if (existing) {
      activeTabId.value = existing.id
      return existing.id
    }
    const id = _genId()
    tabs.value.push({ id, title, type, props, closable })
    activeTabId.value = id
    return id
  }

  function _propsMatch(a: Record<string, any>, b: Record<string, any>): boolean {
    const keysA = Object.keys(a).sort()
    const keysB = Object.keys(b).sort()
    if (keysA.length !== keysB.length) return false
    for (const k of keysA) {
      if (a[k] !== b[k]) return false
    }
    return true
  }

  function closeTab(id: string) {
    const idx = tabs.value.findIndex((t) => t.id === id)
    if (idx === -1) return
    tabs.value.splice(idx, 1)
    if (activeTabId.value === id) {
      // 激活相邻标签
      if (tabs.value.length === 0) {
        activeTabId.value = null
      } else if (idx >= tabs.value.length) {
        activeTabId.value = tabs.value[tabs.value.length - 1].id
      } else {
        activeTabId.value = tabs.value[idx].id
      }
    }
  }

  function closeOtherTabs(id: string) {
    const keep = tabs.value.find((t) => t.id === id)
    if (!keep) return
    tabs.value = [keep]
    activeTabId.value = id
  }

  function closeAllTabs() {
    tabs.value = []
    activeTabId.value = null
  }

  function activateTab(id: string) {
    if (tabs.value.find((t) => t.id === id)) {
      activeTabId.value = id
    }
  }

  return {
    connections,
    currentConnId,
    currentDb,
    sidebarExpanded,
    currentConn,
    // 标签页
    tabs,
    activeTabId,
    activeTab,
    // 方法
    loadConnections,
    selectConnection,
    openTab,
    closeTab,
    closeOtherTabs,
    closeAllTabs,
    activateTab,
  }
})