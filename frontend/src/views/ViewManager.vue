<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useMessage } from 'naive-ui'
import { useAppStore } from '../stores/app'

const props = withDefaults(defineProps<{
  connId?: number
  viewName?: string
  dbName?: string
  schemaName?: string
}>(), {
  connId: 0,
  viewName: '',
  dbName: '',
  schemaName: '',
})

const message = useMessage()
const store = useAppStore()

const loading = ref(false)
const ddl = ref('')
const error = ref('')

// ── 加载视图 DDL ──
async function loadViewDDL() {
  if (!props.connId || !props.viewName) return
  loading.value = true
  error.value = ''
  try {
    const res: any = await api.getViewDDL(props.connId, props.viewName, props.dbName || undefined, props.schemaName || undefined)
    if (res.success) {
      ddl.value = res.data || ''
    } else {
      error.value = res.message || '获取失败'
    }
  } catch (e: any) {
    error.value = e.message || '网络错误'
  } finally {
    loading.value = false
  }
}

onMounted(loadViewDDL)

// ── 工具栏 ──
function copyDDL() {
  navigator.clipboard.writeText(ddl.value)
  message.success('DDL 已复制')
}

function newQuery() {
  store.openTab('sql-workbench', `查询 - ${props.viewName}`, {
    connId: props.connId, dbName: props.dbName, schemaName: props.schemaName,
    initialSql: `SELECT * FROM \`${props.viewName}\` LIMIT 1000`,
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="page-title">
        <h2>👁️ 视图: {{ viewName }}</h2>
        <n-tag v-if="dbName" type="info" size="small">{{ dbName }}</n-tag>
      </div>
      <n-space size="small">
        <n-button size="tiny" @click="newQuery">查询视图</n-button>
        <n-button size="tiny" @click="copyDDL">复制 DDL</n-button>
      </n-space>
    </div>

    <n-alert v-if="error" type="error" closable class="error-alert">{{ error }}</n-alert>

    <n-card title="视图定义 (DDL)" size="small" class="ddl-card">
      <n-spin :show="loading">
        <n-code v-if="ddl" :code="ddl" language="sql" />
        <n-empty v-else-if="!loading" description="无 DDL 数据" />
      </n-spin>
    </n-card>
  </div>
</template>

<style scoped>
.page { padding: 20px; height: 100%; display: flex; flex-direction: column; overflow: auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.page-title { display: flex; align-items: center; gap: 12px; }
.page-title h2 { color: #e0e0e0; font-size: 20px; margin: 0; }
.error-alert { margin-bottom: 12px; }
.ddl-card { flex: 1; overflow: auto; min-height: 0; }
</style>
