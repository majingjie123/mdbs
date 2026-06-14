<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api'

const props = defineProps<{ connId: number }>()
const message = useMessage()
const loading = ref(false)
const status = ref<any>(null)
const refreshing = ref(false)
const poolStats = ref<any>(null)
const poolLoading = ref(false)

async function loadStatus() {
  if (!props.connId) return
  refreshing.value = true
  try {
    const res: any = await api.monitorStatus(props.connId)
    if (res.success) status.value = res.data
    else message.error(res.message)
  } catch (e: any) {
    message.error(e.message)
  } finally {
    refreshing.value = false
  }
}

async function loadPoolStats() {
  poolLoading.value = true
  try {
    const res: any = await api.monitorPoolStats()
    if (res.success) poolStats.value = res.data
  } catch (e: any) {
    // 静默失败
  } finally {
    poolLoading.value = false
  }
}

function formatUptime(seconds: string | number): string {
  const s = parseInt(String(seconds))
  if (!s) return 'N/A'
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  return d + '天 ' + h + '时 ' + m + '分'
}

onMounted(() => { loadStatus(); loadPoolStats() })
</script>

<template>
  <div class="monitor">
    <div class="monitor-header">
      <h2>📊 数据库性能监控</h2>
      <n-button size="small" @click="loadStatus" :loading="refreshing" secondary>刷新</n-button>
    </div>

    <n-spin :show="loading || refreshing">
      <template v-if="status">
        <n-grid :cols="4" :x-gap="12" :y-gap="12" style="margin-bottom: 16px">
          <n-grid-item>
            <n-card size="small" title="运行时间">
              <n-h2 style="margin:0;font-size:20px">{{ formatUptime(status.uptime || status.uptime_raw) }}</n-h2>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small" title="当前连接">
              <n-h2 style="margin:0;font-size:20px">
                {{ status.threads_connected }} / {{ status.max_connections || 'N/A' }}
              </n-h2>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small" title="总查询数">
              <n-h2 style="margin:0;font-size:20px">{{ status.total_queries || 0 }}</n-h2>
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small" title="慢查询">
              <n-h2 style="margin:0;font-size:20px">{{ status.slow_queries || 0 }}</n-h2>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-grid :cols="2" :x-gap="12">
          <n-grid-item>
            <n-card size="small" title="数据库大小排行" :bordered="true">
              <n-data-table
                v-if="status.database_sizes && status.database_sizes.length > 0"
                :columns="[
                  { title: '数据库', key: 'db', ellipsis: true },
                  { title: '大小 (MB)', key: 'size_mb', width: 120, sortable: true,
                    render: (row: any) => row.size_mb.toFixed(1) },
                ]"
                :data="status.database_sizes"
                size="small"
                :max-height="250"
                striped
              />
              <n-empty v-else description="暂无数据" />
            </n-card>
          </n-grid-item>
          <n-grid-item>
            <n-card size="small" title="当前进程 (TOP 20)" :bordered="true">
              <n-data-table
                v-if="status.processes && status.processes.length > 0"
                :columns="[
                  { title: 'ID', key: 'id', width: 50 },
                  { title: '用户', key: 'user', width: 60 },
                  { title: '命令', key: 'command', width: 60 },
                  { title: '耗时', key: 'time', width: 50, sortable: true },
                  { title: '状态', key: 'state', width: 80, ellipsis: true },
                  { title: 'SQL', key: 'info', ellipsis: true,
                    render: (row: any) => row.info || '-' },
                ]"
                :data="status.processes"
                size="small"
                :max-height="250"
                striped
              />
              <n-empty v-else description="无活动进程" />
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-card v-if="status.innodb_lock_waits !== undefined" size="small" title="InnoDB 状态" style="margin-top:12px">
          <n-space>
            <n-statistic label="行锁等待" :value="status.innodb_lock_waits" />
            <n-statistic label="打开的表" :value="status.open_tables" />
            <n-statistic label="表锁立即" :value="status.table_locks_immediate" />
          </n-space>
        </n-card>
      </template>
      <n-empty v-else description="加载状态中..." />
    </n-spin>
  </div>
</template>

<style scoped>
.monitor {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}
.monitor-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.monitor-header h2 {
  margin: 0;
  font-size: 18px;
}
</style>