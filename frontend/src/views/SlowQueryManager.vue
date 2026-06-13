<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api'

const message = useMessage()

const props = defineProps<{
  connId: number
}>()

const loading = ref(false)
const settings = ref<Record<string, string>>({})
const topQueries = ref<any[]>([])
const source = ref('')
const currentTab = ref('settings')

// 开关设置
const slowLogEnabled = ref(false)
const longQueryTime = ref(2)
const showToggleDialog = ref(false)
const toggling = ref(false)

async function loadSettings() {
  try {
    const res: any = await api.getSlowQuerySettings(props.connId)
    if (res.success) {
      settings.value = res.data || {}
      slowLogEnabled.value = res.data?.slow_query_log === 'ON'
      longQueryTime.value = parseFloat(res.data?.long_query_time || '2')
    }
  } catch (e: any) {
    message.error(e.message || '加载配置失败')
  }
}

async function loadTopQueries() {
  loading.value = true
  try {
    const res: any = await api.getTopSlowQueries(props.connId)
    if (res.success) {
      topQueries.value = res.data?.queries || []
      source.value = res.data?.source || ''
    } else {
      message.error(res.message || '加载慢查询失败')
    }
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function doToggleSlowLog() {
  toggling.value = true
  try {
    const res: any = await api.toggleSlowLog(props.connId, {
      enable: slowLogEnabled.value,
      long_query_time: longQueryTime.value,
    })
    if (res.success) {
      message.success(res.message)
      showToggleDialog.value = false
      await loadSettings()
    } else {
      message.error(res.message || '操作失败')
    }
  } catch (e: any) {
    message.error(e.message || '操作失败')
  } finally {
    toggling.value = false
  }
}

function formatDuration(sec: string | number): string {
  const s = parseFloat(String(sec))
  if (s >= 3600) return `${(s / 3600).toFixed(1)}h`
  if (s >= 60) return `${(s / 60).toFixed(1)}m`
  return `${s.toFixed(3)}s`
}

function formatQuery(sql: string): string {
  if (!sql) return ''
  return sql.length > 120 ? sql.substring(0, 120) + '...' : sql
}

onMounted(() => {
  loadSettings()
  loadTopQueries()
})
</script>

<template>
  <div class="slow-query-manager">
    <div class="header">
      <h2>🐢 慢查询日志</h2>
      <n-space size="small">
        <n-button size="tiny" @click="showToggleDialog = true">
          {{ slowLogEnabled ? '⚙️ 设置' : '🔌 开启慢查询' }}
        </n-button>
        <n-button size="tiny" @click="loadSettings">刷新</n-button>
      </n-space>
    </div>

    <n-tabs v-model:value="currentTab" type="line" size="small">
      <n-tab-pane name="settings" tab="⚙️ 系统配置">
        <n-card size="small" :bordered="true">
          <n-descriptions size="small" :column="2" bordered>
            <n-descriptions-item
              v-for="(val, key) in settings"
              :key="key"
              :label="key"
            >
              <n-tag v-if="key === 'slow_query_log'" :type="val === 'ON' ? 'success' : 'warning'" size="small">
                {{ val === 'ON' ? '已启用' : '已关闭' }}
              </n-tag>
              <span v-else>{{ val }}</span>
            </n-descriptions-item>
          </n-descriptions>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="top" tab="🔝 Top 慢查询">
        <n-space vertical>
          <n-alert v-if="source" type="info" :bordered="false" closable>
            <template #header>数据来源: {{ source }}</template>
          </n-alert>
          <n-spin :show="loading">
            <n-data-table
              v-if="topQueries.length > 0"
              :columns="[
                { title: '#', key: 'index', width: 40, render: (_: any, idx: number) => idx + 1 },
                { title: 'SQL', key: 'query', ellipsis: true, minWidth: 300,
                  render: (row: any) => formatQuery(row.query || row.sql_text || '') },
                { title: '数据库', key: 'db', width: 120,
                  render: (row: any) => row.db || row.SCHEMA_NAME || '-' },
                { title: '执行次数', key: 'exec_count', width: 90, sortable: true,
                  render: (row: any) => row.exec_count || row.calls || '-' },
                { title: '总耗时', key: 'total', width: 100, sortable: true,
                  render: (row: any) => {
                    const v = row.total_sec !== undefined ? row.total_sec :
                              row.total_ms ? row.total_ms / 1000 :
                              row.query_time ? row.query_time : 0
                    return formatDuration(v)
                  }},
                { title: '平均耗时', key: 'avg', width: 100, sortable: true,
                  render: (row: any) => {
                    const v = row.avg_sec !== undefined ? row.avg_sec :
                              row.avg_ms ? row.avg_ms / 1000 : 0
                    return formatDuration(v)
                  }},
                { title: '最大耗时', key: 'max', width: 100,
                  render: (row: any) => {
                    const v = row.max_sec !== undefined ? row.max_sec :
                              row.max_ms ? row.max_ms / 1000 : 0
                    return formatDuration(v)
                  }},
                { title: '扫描行数', key: 'rows_examined', width: 100,
                  render: (row: any) => row.avg_rows_examined ?? row.rows_examined ?? row.rows ?? '-' },
                { title: '返回行数', key: 'rows_sent', width: 90,
                  render: (row: any) => row.rows_sent ?? '-' },
              ]"
              :data="topQueries"
              striped
              :bordered="true"
              size="small"
              :max-height="500"
              :row-key="(row: any) => row.query || row.sql_text || Math.random()"
            />
            <n-empty v-else-if="!loading" description="暂无慢查询数据（需要开启 slow_query_log 或安装 pg_stat_statements）" />
          </n-spin>
        </n-space>
      </n-tab-pane>
    </n-tabs>

    <!-- 设置对话框 -->
    <n-modal v-model:show="showToggleDialog" title="慢查询日志设置" preset="card" style="width: 400px;" :mask-closable="false">
      <n-space vertical>
        <n-switch v-model:value="slowLogEnabled" />
        <span>慢查询日志：{{ slowLogEnabled ? '已启用' : '已关闭' }}</span>
        <n-input-number v-model:value="longQueryTime" :min="0.1" :max="3600" :step="0.1" placeholder="阈值(秒)">
          <template #prefix>阈值</template>
          <template #suffix>秒</template>
        </n-input-number>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showToggleDialog = false">取消</n-button>
          <n-button type="primary" @click="doToggleSlowLog" :loading="toggling">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.slow-query-manager {
  padding: 12px;
  display: flex;
  flex-direction: column;
  height: 100%;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.header h2 {
  margin: 0;
  font-size: 18px;
}
</style>
