<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api'

const props = defineProps<{ connId: number; dbName?: string }>()
const message = useMessage()
const loading = ref(false)
const erData = ref<any>(null)
const selectedTable = ref<any>(null)
const mermaidCode = ref('')
const tableSearch = ref('')

function generateMermaid(data: any): string {
  const lines = ['erDiagram']
  for (const t of data.tables || []) {
    lines.push('  ' + t.name.replace(/[^a-zA-Z0-9_]/g, '_') + ' {')
    for (const col of t.columns) {
      const pk = col.key === 'PRI' ? ' PK' : ''
      lines.push('    ' + col.type + ' ' + col.name + pk)
    }
    lines.push('  }')
  }
  for (const r of data.relations || []) {
    const from = r.from_table.replace(/[^a-zA-Z0-9_]/g, '_')
    const to = r.to_table.replace(/[^a-zA-Z0-9_]/g, '_')
    lines.push('  ' + from + ' }|--o{ ' + to + ' : "' + r.from_column + ' -> ' + r.to_column + '"')
  }
  return lines.join('
')
}

async function loadERData() {
  if (!props.connId) return
  loading.value = true
  try {
    const res: any = await api.getERData(props.connId, props.dbName)
    if (res.success && res.data) {
      erData.value = res.data
      mermaidCode.value = generateMermaid(res.data)
    } else message.error(res.message)
  } catch (e: any) { message.error(e.message) }
  finally { loading.value = false }
}

function selectTable(name: string) {
  selectedTable.value = (erData.value?.tables || []).find((t: any) => t.name === name) || null
}

onMounted(loadERData)
</script>

<template>
  <div class="er-viewer">
    <div class="header">
      <h2>🗺️ ER 图查看器</h2>
      <n-space>
        <n-tag v-if="erData" size="small">{{ erData.tables?.length || 0 }} 张表</n-tag>
        <n-tag v-if="erData" size="small">{{ erData.relations?.length || 0 }} 个关系</n-tag>
        <n-button size="small" @click="loadERData" :loading="loading" secondary>刷新</n-button>
      </n-space>
    </div>
    <n-split style="height: calc(100vh - 160px)" :default-size="0.7">
      <template #1>
        <n-spin :show="loading">
          <div v-if="mermaidCode" class="mermaid-container">
            <pre class="mermaid">{{ mermaidCode }}</pre>
          </div>
          <n-empty v-else description="加载中..." />
        </n-spin>
      </template>
      <template #2>
        <div class="table-list">
          <n-input v-model:value="tableSearch" placeholder="搜索表..." size="small" clearable style="margin-bottom:8px" />
          <n-data-table
            v-if="erData?.tables"
            :columns="[
              { title: '表名', key: 'name', ellipsis: true,
                render: (row: any) => h('a', { style: 'cursor:pointer;color:var(--color-accent)', onClick: () => selectTable(row.name) }, row.name),
              },
              { title: '字段数', key: 'columns', width: 70, render: (row: any) => row.columns?.length || 0 },
            ]"
            :data="erData.tables"
            size="small"
            :max-height="500"
            striped
          />
        </div>
      </template>
    </n-split>
    <n-drawer v-model:show="!!selectedTable" :width="400" placement="right">
      <n-drawer-content :title="selectedTable?.name || ''" closable @close="selectedTable = null">
        <n-data-table
          v-if="selectedTable"
          :columns="[
            { title: '字段', key: 'name' },
            { title: '类型', key: 'type', width: 100 },
            { title: '键', key: 'key', width: 50 },
            { title: '可空', key: 'nullable', width: 50, render: (row: any) => row.nullable ? '✅' : '❌' },
          ]"
          :data="selectedTable.columns"
          size="small" bordered
        />
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.er-viewer { padding: 16px; height: 100%; display: flex; flex-direction: column; }
.header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.header h2 { margin: 0; font-size: 18px; }
.mermaid-container { background: white; border-radius: 8px; padding: 24px; overflow: auto; height: 100%; }
.mermaid { margin: 0; font-family: Arial, sans-serif; }
.table-list { padding: 0 8px; }
</style>
