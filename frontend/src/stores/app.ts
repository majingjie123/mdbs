import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api'

export const useAppStore = defineStore('app', () => {
  const connections = ref<any[]>([])
  const currentConnId = ref<number | null>(null)
  const currentDb = ref('')
  const sidebarExpanded = ref(true)

  const currentConn = computed(() =>
    connections.value.find((c) => c.id === currentConnId.value) || null,
  )

  async function loadConnections() {
    const res: any = await api.listConnections()
    if (res.success) connections.value = res.data
  }

  function selectConnection(id: number) {
    currentConnId.value = id
  }

  return {
    connections,
    currentConnId,
    currentDb,
    sidebarExpanded,
    currentConn,
    loadConnections,
    selectConnection,
  }
})
