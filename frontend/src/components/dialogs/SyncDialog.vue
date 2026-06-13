<script setup lang="ts">
import { ref, watch, computed, h, onBeforeUnmount } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import type { DataTableColumn } from 'naive-ui'
import { api } from '../../api'
import SyncProgressDialog from './SyncProgressDialog.vue'

const props = defineProps<{
  visible: boolean
  connId?: number
  dbName?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const activeTab = ref('sync')

const connections = ref<any[]>([])
const sourceConnId = ref<number | null>(props.connId ?? null)
const sourceDb = ref(props.dbName ?? '')
const sourceDatabases = ref<string[]>([])
const loadingSourceDbs = ref(false)

const targetConnId = ref<number | null>(null)
const targetDatabases = ref<string[]>([])
const targetDb = ref('')
const loadingDbs = ref(false)

const sourceTables = ref<any[]>([])
const tableSearch = ref('')
const selectedTables = ref<string[]>([])
const loadingTables = ref(false)

const filteredTables = computed(() => {
  if (!tableSearch.value) return sourceTables.value
  const q = tableSearch.value.toLowerCase()
  return sourceTables.value.filter((t: any) => t.name.toLowerCase().includes(q))
})

const conflictStrategy = ref('overwrite')

const conflictOptions = [
  { label: '覆盖写入 (overwrite)', value: 'overwrite' },
  { label: '跳过已存在 (skip)', value: 'skip' },
]

const syncStructure = ref(true)
const syncData = ref(true)

const currentTaskId = ref<string | null>(null)
const progressVisible = ref(false)
let progressTimer: ReturnType<typeof setInterval> | null = null

const historyRecords = ref<any[]>([])
const loadingHistory = ref(false)

async function loadConnections() {
  try {
    const res: any = await api.listConnections()
    if (res.success && res.data) {
      connections.value = res.data
      // 如果 props 有 connId，确保 sourceConnId 在连接列表中有对应项
      if (props.connId && !connections.value.some((c: any) => c.id === props.connId)) {
        sourceConnId.value = null
      }
    }
  } catch {
    connections.value = []
  }
}

async function loadSourceDatabases() {
  if (!sourceConnId.value) {
    sourceDatabases.value = []
    sourceDb.value = ''
    return
  }
  loadingSourceDbs.value = true
  try {
    const res: any = await api.listDatabases(sourceConnId.value)
    if (res.success && res.data) {
      sourceDatabases.value = res.data
      // 如果 props.dbName 在加载之前设了 dbName 且属于该连接，保留，否则重置
      if (props.dbName && sourceDatabases.value.includes(props.dbName)) {
        sourceDb.value = props.dbName
      } else {
        sourceDb.value = ''
      }
    } else {
      sourceDatabases.value = []
    }
  } catch {
    sourceDatabases.value = []
  } finally {
    loadingSourceDbs.value = false
  }
}

async function loadTargetDatabases() {
  if (!targetConnId.value) {
    targetDatabases.value = []
    targetDb.value = ''
    return
  }
  loadingDbs.value = true
  try {
    const res: any = await api.listDatabases(targetConnId.value)
    if (res.success && res.data) {
      targetDatabases.value = res.data
    } else {
      targetDatabases.value = []
    }
  } catch {
    targetDatabases.value = []
  } finally {
    loadingDbs.value = false
  }
}

async function loadSourceTables() {
  if (!sourceConnId.value || !sourceDb.value) return
  loadingTables.value = true
  try {
    const res: any = await api.listTables(sourceConnId.value, sourceDb.value)
    if (res.success && res.data) {
      sourceTables.value = res.data
    } else {
      sourceTables.value = []
    }
  } catch {
    sourceTables.value = []
  } finally {
    loadingTables.value = false
  }
}

function selectAllTables() {
  selectedTables.value = filteredTables.value.map((t: any) => t.name)
}

function deselectAllTables() {
  selectedTables.value = []
}

async function startSync() {
  if (!sourceConnId.value) {
    message.warning('请选择源连接')
    return
  }
  if (!sourceDb.value) {
    message.warning('请选择源数据库')
    return
  }
  if (!targetConnId.value) {
    message.warning('请选择目标连接')
    return
  }
  if (!targetDb.value) {
    message.warning('请选择目标数据库')
    return
  }
  if (selectedTables.value.length === 0) {
    message.warning('请选择要同步的表')
    return
  }

  loading.value = true
  try {
    const res: any = await api.syncStart({
      source_conn_id: sourceConnId.value,
      source_db: sourceDb.value,
      target_conn_id: targetConnId.value,
      target_db: targetDb.value,
      tables: selectedTables.value,
      sync_structure: syncStructure.value,
      sync_data: syncData.value,
      conflict_strategy: conflictStrategy.value,
    })
    if (res.success && res.data) {
      currentTaskId.value = res.data.task_id
      progressVisible.value = true
      startProgressPolling(res.data.task_id)
      message.success('同步任务已启动')
    } else {
      message.error(res.message || '启动同步失败')
    }
  } catch (e: any) {
    message.error(e.message || '启动同步失败')
  } finally {
    loading.value = false
  }
}

function startProgressPolling(taskId: string) {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try {
      const res: any = await api.syncProgress(taskId)
      if (res.success && res.data) {
        const status = res.data.status
        if (status !== 'running') {
          stopProgressPolling()
          loadHistory()
        }
      }
    } catch {
    }
  }, 2000)
}

function stopProgressPolling() {
  if (progressTimer !== null) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const res: any = await api.syncHistory(50)
    if (res.success && res.data) {
      historyRecords.value = res.data.map((r: any) => {
        let tablesList: string[] = []
        if (r.tables) {
          if (typeof r.tables === 'string') {
            try { tablesList = JSON.parse(r.tables) } catch { tablesList = [] }
          } else if (Array.isArray(r.tables)) {
            tablesList = r.tables
          }
        }
        return {
          ...r,
          _tablesCount: tablesList.length,
        }
      })
    }
  } catch {
    historyRecords.value = []
  } finally {
    loadingHistory.value = false
  }
}

function viewHistRecord(row: any) {
  const record = historyRecords.value.find((r: any) => r.id === row.id)
  if (!record) return

  dialog.info({
    title: '同步历史',
    content: () =>
      h('div', { style: 'font-size: 13px; line-height: 1.8' }, [
        h('p', {}, '开始时间: ' + (record.start_time || '-')),
        h('p', {}, '结束时间: ' + (record.end_time || '-')),
        h('p', {}, '源连接: ' + (record.source_name || '-') + ' / ' + (record.source_db || '-')),
        h('p', {}, '目标连接: ' + (record.target_name || '-') + ' / ' + (record.target_db || '-')),
        h('p', {}, '表结构同步: ' + (record.sync_structure ? '是' : '否')),
        h('p', {}, '数据同步: ' + (record.sync_data ? '是' : '否')),
        h('p', {}, '表数量: ' + (record._tablesCount || 0)),
        h('p', {}, '状态: ' + (record.status || '-')),
        record.error_summary
          ? h('p', { style: 'color: #e53e3e' }, '错误信息: ' + record.error_summary)
          : null,
      ]),
    positiveText: '关闭',
  })
}

const historyColumns: DataTableColumn[] = [
  {
    title: '开始时间',
    key: 'start_time',
    width: 160,
    ellipsis: { tooltip: true },
  },
  {
    title: '源连接',
    key: 'source_name',
    width: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '源数据库',
    key: 'source_db',
    width: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '目标连接',
    key: 'target_name',
    width: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '目标数据库',
    key: 'target_db',
    width: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row: any) => {
      const statusMap: Record<string, { type: string; label: string }> = {
        success: { type: 'success', label: '成功' },
        running: { type: 'info', label: '运行中' },
        failed: { type: 'error', label: '失败' },
        cancelled: { type: 'warning', label: '已取消' },
      }
      const s = statusMap[row.status] || { type: 'default', label: row.status || '-' }
      return h(
        'n-tag',
        { size: 'small', type: s.type },
        { default: () => s.label },
      )
    },
  },
  {
    title: '表数量',
    key: '_tablesCount',
    width: 80,
    align: 'center',
  },
]

const connOptions = computed(() => {
  return (connections.value || []).map((c: any) => ({
    label: c.name + ' (' + c.db_type + '@' + c.host + ':' + c.port + '/' + c.database + ')',
    value: c.id,
  }))
})

// ── 数据对比 ──
const compareResult = ref<{ only_source: string[]; only_target: string[]; different: any[]; same: string[] } | null>(null)
const compareLoading = ref(false)

async function runCompare() {
  if (!sourceConnId.value || !sourceDb.value || !targetConnId.value || !targetDb.value) {
    message.warning('请选择源/目标连接和数据库')
    return
  }
  compareLoading.value = true
  compareResult.value = null
  try {
    const res: any = await api.syncCompare({
      source_conn_id: sourceConnId.value,
      source_db: sourceDb.value,
      target_conn_id: targetConnId.value,
      target_db: targetDb.value,
      tables: selectedTables.value.length > 0 ? selectedTables.value : [],
    })
    if (res.success) {
      compareResult.value = res.data
      if (res.data.only_source.length === 0 && res.data.only_target.length === 0 && res.data.different.every((d: any) => !d.data.diff)) {
        message.success('数据完全一致')
      } else {
        message.info('发现差异')
      }
    } else {
      message.error(res.message || '对比失败')
    }
  } catch (e: any) {
    message.error('对比失败: ' + e.message)
  } finally {
    compareLoading.value = false
  }
}

const sourceDbOptions = computed(() => {
  return (sourceDatabases.value || []).map((db: string) => ({
    label: db,
    value: db,
  }))
})

const targetDbOptions = computed(() => {
  return (targetDatabases.value || []).map((db: string) => ({
    label: db,
    value: db,
  }))
})

watch(() => props.visible, (v) => {
  if (v) {
    activeTab.value = 'sync'
    sourceConnId.value = props.connId ?? null
    sourceDb.value = props.dbName ?? ''
    sourceDatabases.value = []
    targetConnId.value = null
    targetDb.value = ''
    selectedTables.value = []
    tableSearch.value = ''
    conflictStrategy.value = 'overwrite'
    syncStructure.value = true
    syncData.value = true
    currentTaskId.value = null
    progressVisible.value = false
    stopProgressPolling()
    loadConnections()
    loadHistory()
    if (props.connId) {
      loadSourceDatabases()
    }
    if (props.connId && props.dbName) {
      loadSourceTables()
    }
  }
})

watch(sourceConnId, () => {
  sourceDb.value = ''
  sourceTables.value = []
  selectedTables.value = []
  loadSourceDatabases()
})

watch(sourceDb, () => {
  selectedTables.value = []
  loadSourceTables()
})

watch(targetConnId, () => {
  targetDb.value = ''
  loadTargetDatabases()
})

onBeforeUnmount(() => {
  stopProgressPolling()
})

function close() {
  stopProgressPolling()
  progressVisible.value = false
  emit('update:visible', false)
}
</script>

<template>
  <n-modal
    :show="visible"
    @update:show="(v: boolean) => emit('update:visible', v)"
    :mask-closable="false"
    preset="card"
    title="数据库同步"
    style="width: 680px"
    :bordered="true"
    :segmented="{ content: true }"
  >
    <SyncProgressDialog
      v-if="progressVisible"
      :task-id="currentTaskId || ''"
      @close="progressVisible = false; stopProgressPolling(); loadHistory()"
    />

    <n-tabs v-model:value="activeTab" type="line">

      <n-tab-pane name="sync" tab="数据库同步">
        <n-form label-placement="left" label-width="110" size="small">

          <n-form-item label="源连接">
            <n-select
              v-model:value="sourceConnId"
              :options="connOptions"
              filterable
              placeholder="选择源连接"
              clearable
              :loading="connections.length === 0"
            />
          </n-form-item>

          <n-form-item label="源数据库">
            <n-select
              v-model:value="sourceDb"
              :options="sourceDbOptions"
              filterable
              placeholder="选择源数据库"
              :loading="loadingSourceDbs"
              :disabled="!sourceConnId"
              clearable
            />
          </n-form-item>

          <n-divider />

          <n-form-item label="目标连接">
            <n-select
              v-model:value="targetConnId"
              :options="connOptions"
              filterable
              placeholder="选择目标连接"
              clearable
              :loading="connections.length === 0"
            />
          </n-form-item>

          <n-form-item label="目标数据库">
            <n-select
              v-model:value="targetDb"
              :options="targetDbOptions"
              filterable
              placeholder="选择目标数据库"
              :loading="loadingDbs"
              :disabled="!targetConnId"
              clearable
            />
          </n-form-item>

          <n-divider />

          <n-form-item label="选择表">
            <div style="width: 100%">
              <div style="display: flex; gap: 8px; margin-bottom: 8px">
                <n-input
                  v-model:value="tableSearch"
                  placeholder="搜索表名..."
                  clearable
                  size="small"
                  style="flex: 1"
                />
                <n-button size="tiny" @click="selectAllTables">全选</n-button>
                <n-button size="tiny" @click="deselectAllTables">取消全选</n-button>
              </div>
              <div
                v-if="loadingTables"
                style="padding: 24px 0; text-align: center; color: #888"
              >
                <n-spin size="small" /> 加载中...
              </div>
              <div
                v-else-if="filteredTables.length === 0"
                style="padding: 24px 0; text-align: center; color: #888"
              >
                暂无表数据
              </div>
              <n-checkbox-group v-else v-model:value="selectedTables">
                <div style="max-height: 220px; overflow-y: auto; border: 1px solid #333; border-radius: 4px; padding: 4px 8px">
                  <div
                    v-for="t in filteredTables"
                    :key="t.name"
                    style="padding: 3px 0"
                  >
                    <n-checkbox :value="t.name">
                      {{ t.comment ? t.name + ' (' + t.comment + ')' : t.name }}
                    </n-checkbox>
                  </div>
                </div>
              </n-checkbox-group>
              <div style="margin-top: 4px; font-size: 12px; color: #888">
                已选择 {{ selectedTables.length }} / {{ sourceTables.length }} 个表
              </div>
            </div>
          </n-form-item>

          <n-divider />

          <n-form-item label="冲突策略">
            <n-select
              v-model:value="conflictStrategy"
              :options="conflictOptions"
              style="width: 260px"
            />
          </n-form-item>

          <n-form-item label="同步选项">
            <n-space>
              <n-checkbox v-model:checked="syncStructure">表结构</n-checkbox>
              <n-checkbox v-model:checked="syncData">数据</n-checkbox>
            </n-space>
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <n-tab-pane name="history" tab="同步历史">
        <div style="margin-bottom: 8px">
          <n-button size="small" @click="loadHistory" :loading="loadingHistory">
            刷新
          </n-button>
        </div>
        <n-data-table
          :columns="historyColumns"
          :data="historyRecords"
          :loading="loadingHistory"
          :bordered="true"
          striped
          size="small"
          :max-height="420"
          :row-props="(row: any) => ({
            style: 'cursor: pointer',
            onClick: () => viewHistRecord(row),
          })"
        >
          <template #empty>
            <n-empty description="暂无同步历史" />
          </template>
        </n-data-table>
      </n-tab-pane>

      <n-tab-pane name="compare" tab="数据对比">
        <n-space vertical size="large">
          <n-alert type="info" :show-icon="false">
            比对源数据库和目标数据库的表结构和数据差异
          </n-alert>

          <n-space>
            <n-button type="primary" :loading="compareLoading" @click="runCompare">
              开始对比
            </n-button>
            <n-button :disabled="!compareResult" @click="compareResult = null">
              清除结果
            </n-button>
          </n-space>

          <div v-if="compareResult" class="compare-result">
            <n-space vertical>
              <!-- 仅源端有的表 -->
              <div v-if="compareResult.only_source.length > 0">
                <div class="compare-section-title" style="color: #18a058">
                  仅源端 ({{ compareResult.only_source.length }})
                </div>
                <n-tag v-for="t in compareResult.only_source" :key="t" size="small" type="success" style="margin: 2px">
                  {{ t }}
                </n-tag>
              </div>

              <!-- 仅目标端有的表 -->
              <div v-if="compareResult.only_target.length > 0">
                <div class="compare-section-title" style="color: #d03050">
                  仅目标端 ({{ compareResult.only_target.length }})
                </div>
                <n-tag v-for="t in compareResult.only_target" :key="t" size="small" type="error" style="margin: 2px">
                  {{ t }}
                </n-tag>
              </div>

              <!-- 数据差异 -->
              <div v-if="compareResult.different.length > 0">
                <div class="compare-section-title">数据差异 ({{ compareResult.different.filter((d: any) => d.data.diff).length }})</div>
                <n-data-table
                  :columns="[
                    { title: '表名', key: 'table', width: 200 },
                    { title: '源行数', key: 'source', width: 100 },
                    { title: '目标行数', key: 'target', width: 100 },
                    { title: '差异', key: 'diff', width: 80,
                      render: (row: any) => row.data.diff
                        ? h('n-tag', { size: 'small', type: 'warning' }, '有差异')
                        : h('n-tag', { size: 'small', type: 'success' }, '一致')
                    },
                  ]"
                  :data="compareResult.different"
                  :bordered="true"
                  size="small"
                  :max-height="250"
                />
              </div>

              <n-empty v-if="compareResult.only_source.length === 0 && compareResult.only_target.length === 0 && compareResult.different.every((d: any) => !d.data.diff)" description="数据完全一致" />
            </n-space>
          </div>
        </n-space>
      </n-tab-pane>
    </n-tabs>

    <template #footer>
      <n-space justify="end">
        <n-button @click="close">关闭</n-button>
        <n-button
          v-if="activeTab === 'sync'"
          type="primary"
          :loading="loading"
          @click="startSync"
        >
          开始同步
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
:deep(.n-divider) {
  margin-top: 8px;
  margin-bottom: 8px;
}

:deep(.n-checkbox-group) {
  width: 100%;
}
</style>