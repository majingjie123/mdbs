<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { api } from '../../api'

const props = defineProps<{
  taskId: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

// ── 状态 ──
const running = ref(true)
const statusText = ref('准备中...')
const progress = ref({ table: '', index: 0, total: 0, percent: 0 })
const logs = ref<{ message: string; level: string }[]>([])
const error = ref('')
const rowProgress = ref<{ table: string; inserted: number; total_est: number; percent: number } | null>(null)
const logContainer = ref<HTMLElement | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

// ── 自动滚动到日志底部 ──
function scrollLogToBottom() {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

// ── 轮询进度 ──
async function pollProgress() {
  try {
    const res: any = await api.syncProgress(props.taskId)
    if (!res.success) {
      running.value = false
      statusText.value = '获取进度失败'
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
      return
    }

    const data = res.data

    // 更新进度
    if (data.progress) {
      progress.value = data.progress
      if (data.progress.table) {
        statusText.value = `正在同步: ${data.progress.table}`
      }
    }

    // 更新行级进度
    if (data.row_progress) {
      rowProgress.value = data.row_progress
      const rp = data.row_progress
      if (rp.inserted > 0 && rp.total_est > 0) {
        statusText.value = `同步中: ${rp.table} (${rp.inserted.toLocaleString()}/${rp.total_est.toLocaleString()} 行)`
      }
    }

    // 更新日志
    if (data.logs && data.logs.length > 0) {
      const prevLen = logs.value.length
      logs.value = data.logs as { message: string; level: string }[]
      if (logs.value.length > prevLen) {
        scrollLogToBottom()
      }
    }

    // 更新错误
    if (data.error) {
      error.value = data.error
    }

    // 检查任务是否结束
    if (data.status !== 'running') {
      running.value = false
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }

      if (data.status === 'success') {
        statusText.value = '同步完成 ✓'
      } else if (data.status === 'failed') {
        statusText.value = '同步失败 ✗'
        error.value = data.error || '任务执行出错'
      } else if (data.status === 'cancelled') {
        statusText.value = '同步已取消'
      } else {
        statusText.value = `状态: ${data.status}`
      }
    }
  } catch (e: any) {
    running.value = false
    statusText.value = '轮询失败'
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }
}

// ── 取消任务 ──
async function cancelTask() {
  try {
    const res: any = await api.syncCancel(props.taskId)
    if (res.success) {
      statusText.value = '正在取消...'
    }
  } catch (e: any) {
    // ignore
  }
}

// ── 生命周期 ──
onMounted(() => {
  pollTimer = setInterval(pollProgress, 1000)
  pollProgress() // 立即执行一次
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <n-modal
    :show="true"
    preset="card"
    title="同步进度"
    style="width: 600px"
    :closable="false"
    :mask-closable="false"
    :bordered="true"
    :segmented="{ content: true, footer: true }"
  >
    <div class="progress-body">
      <!-- 状态 / 当前表名 -->
      <div class="current-table">{{ statusText }}</div>

      <!-- 行级进度条（细粒度） -->
      <div v-if="rowProgress && rowProgress.total_est > 0" class="row-progress">
        <div class="row-bar-wrap">
          <div
            class="row-bar-fill"
            :style="{ width: rowProgress.percent + '%' }"
          />
        </div>
        <div class="row-bar-text">
          行: {{ rowProgress.inserted.toLocaleString() }} / {{ rowProgress.total_est.toLocaleString() }}
          ({{ rowProgress.percent }}%)
        </div>
      </div>

      <!-- 进度条 -->
      <n-progress
        type="line"
        :value="progress.percent"
        :indicator-placement="'inside'"
        :height="22"
        processing
      />

      <!-- 进度文本 -->
      <div class="progress-text">
        进度: {{ progress.index }} / {{ progress.total }} ({{ progress.percent }}%)
        <span v-if="rowProgress && rowProgress.inserted > 0" style="margin-left:12px;color:var(--color-accent)">
          共 {{ rowProgress.inserted.toLocaleString() }} 行
        </span>
      </div>

      <!-- 日志区域 -->
      <div ref="logContainer" class="log-area">
        <div
          v-for="(log, i) in logs"
          :key="i"
          class="log-line"
          :class="'log-' + log.level.toLowerCase()"
        >
          <pre>{{ log.message }}</pre>
        </div>
        <div v-if="logs.length === 0" class="log-placeholder">等待日志...</div>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button v-if="running" @click="cancelTask">
          取消任务
        </n-button>
        <n-button
          @click="emit('close')"
          :disabled="running"
          :type="running ? 'default' : 'primary'"
        >
          关闭
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped>
.progress-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.current-table {
  color: var(--color-text);
  font-size: 14px;
  font-weight: 600;
}

.progress-text {
  color: var(--color-text-muted);
  font-size: 12px;
}

.log-area {
  background: var(--bg-app);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 8px;
  height: 250px;
  overflow-y: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
}

.log-info {
  color: var(--color-text);
}

.log-error {
  color: #ff6b6b;
}

.log-warning {
  color: #ffd93d;
}

.log-debug {
  color: var(--color-text-muted);
}

.log-line pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-placeholder {
  color: var(--color-text-muted);
  font-style: italic;
}

/* ── 行级进度条样式 ── */
.row-progress{display:flex;align-items:center;gap:10px}
.row-bar-wrap{flex:1;height:8px;background:var(--bg-hover);border-radius:4px;overflow:hidden}
.row-bar-fill{height:100%;background:linear-gradient(90deg,#4caf50,#8bc34a);border-radius:4px;transition:width .5s}
.row-bar-text{font-size:11px;color:var(--color-text-secondary);white-space:nowrap}
</style>