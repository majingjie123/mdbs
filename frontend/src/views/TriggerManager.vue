<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useMessage, useDialog } from 'naive-ui'
import { useAppStore } from '../stores/app'

const props = withDefaults(defineProps<{
  connId?: number
  triggerName?: string
  dbName?: string
  schemaName?: string
}>(), {
  connId: 0,
  triggerName: '',
  dbName: '',
  schemaName: '',
})

const message = useMessage()
const dialog = useDialog()
const store = useAppStore()

const loading = ref(false)
const ddl = ref('')
const error = ref('')

// ── 触发器信息表 ──
const triggerInfo = ref<Record<string, string>>({})

// ── 加载触发器 DDL ──
async function loadTriggerDDL() {
  if (!props.connId || !props.triggerName) return
  loading.value = true
  error.value = ''
  try {
    const res: any = await api.getTriggerDDL(props.connId, props.triggerName, props.dbName || undefined, props.schemaName || undefined)
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

// ── 加载触发器信息 ──
async function loadTriggerInfo() {
  if (!props.connId || !props.triggerName) return
  try {
    const res: any = await api.listTriggers(props.connId, props.dbName || undefined, props.schemaName || undefined)
    if (res.success && res.data) {
      const found = res.data.find((t: any) => t.TRIGGER_NAME === props.triggerName)
      if (found) {
        triggerInfo.value = found
      }
    }
  } catch {
    // ignore
  }
}

onMounted(() => {
  loadTriggerDDL()
  loadTriggerInfo()
})

// ── 工具栏 ──
function copyDDL() {
  navigator.clipboard.writeText(ddl.value)
  message.success('DDL 已复制')
}

function copyName() {
  navigator.clipboard.writeText(props.triggerName)
  message.success('名称已复制')
}

function newQuery() {
  store.openTab('sql-workbench', `查询 - ${props.triggerName}`, {
    connId: props.connId, dbName: props.dbName, schemaName: props.schemaName,
    initialSql: `SHOW TRIGGERS WHERE \`Trigger\` = '${props.triggerName}'`,
  })
}

function confirmDrop() {
  dialog.warning({
    title: '删除触发器',
    content: `确定要删除触发器 "${props.triggerName}" 吗？此操作不可撤销！`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res: any = await api.dropTrigger(props.connId, props.triggerName, props.dbName || undefined, props.schemaName || undefined)
        if (res.success) {
          message.success(`触发器 ${props.triggerName} 已删除`)
          // 关闭当前标签
          if (store.activeTabId) {
            store.closeTab(store.activeTabId)
          }
        } else {
          message.error(res.message || '删除失败')
        }
      } catch (e: any) {
        message.error('删除失败: ' + (e.message || ''))
      }
    },
  })
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="page-title">
        <h2>🔔 触发器: {{ triggerName }}</h2>
        <n-tag v-if="dbName" type="info" size="small">{{ dbName }}</n-tag>
      </div>
      <n-space size="small">
        <n-button size="tiny" @click="newQuery">查询</n-button>
        <n-button size="tiny" @click="copyDDL">复制 DDL</n-button>
        <n-button size="tiny" @click="copyName">复制名称</n-button>
        <n-button size="tiny" type="error" @click="confirmDrop">删除</n-button>
      </n-space>
    </div>

    <n-alert v-if="error" type="error" closable class="error-alert">{{ error }}</n-alert>

    <!-- 触发器基本信息 -->
    <n-card v-if="Object.keys(triggerInfo).length > 0" title="基本信息" size="small" class="info-card">
      <n-descriptions label-placement="left" :column="3" size="small" bordered>
        <n-descriptions-item v-if="triggerInfo.EVENT_OBJECT_TABLE" label="关联表">
          {{ triggerInfo.EVENT_OBJECT_TABLE }}
        </n-descriptions-item>
        <n-descriptions-item v-if="triggerInfo.EVENT_MANIPULATION" label="触发事件">
          <n-tag size="small" type="info">{{ triggerInfo.EVENT_MANIPULATION }}</n-tag>
        </n-descriptions-item>
        <n-descriptions-item v-if="triggerInfo.ACTION_TIMING" label="触发时机">
          <n-tag size="small" type="warning">{{ triggerInfo.ACTION_TIMING }}</n-tag>
        </n-descriptions-item>
        <n-descriptions-item v-if="triggerInfo.DEFINER" label="定义者">
          {{ triggerInfo.DEFINER }}
        </n-descriptions-item>
        <n-descriptions-item v-if="triggerInfo.CREATED" label="创建时间">
          {{ triggerInfo.CREATED }}
        </n-descriptions-item>
      </n-descriptions>
    </n-card>

    <!-- DDL -->
    <n-card title="触发器定义 (DDL)" size="small" class="ddl-card">
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
.info-card { margin-bottom: 12px; flex-shrink: 0; }
.info-card :deep(.n-descriptions-table) { font-size: 12px; }
.ddl-card { flex: 1; overflow: auto; min-height: 0; }
</style>
