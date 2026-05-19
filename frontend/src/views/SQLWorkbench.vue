<script setup lang="ts">
import { ref, computed, h, onMounted, onUnmounted } from 'vue'
import { api, ExecResult } from '../api'
import { useMessage } from 'naive-ui'
import SqlEditor from '../components/SqlEditor.vue'

const props = withDefaults(defineProps<{
  connId?: number
  dbName?: string
  schemaName?: string
  initialSql?: string
}>(), {
  connId: 0,
  dbName: '',
  schemaName: '',
  initialSql: '',
})

const message = useMessage()

const sqlText = ref(props.initialSql || `SELECT * FROM information_schema.tables LIMIT 100`)
const result = ref<ExecResult | null>(null)
const running = ref(false)
const error = ref('')

// ── 查询耗时 ──
const queryTime = ref(0)

// ── 可拖拽分屏 (编辑器高度百分比) ──
const splitRatio = ref(35) // 编辑器占比 %
const isDragging = ref(false)

function onSplitMouseDown(e: MouseEvent) {
  isDragging.value = true
  e.preventDefault()
}

function onSplitMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  const container = document.querySelector('.workbench') as HTMLElement
  if (!container) return
  const rect = container.getBoundingClientRect()
  const y = e.clientY - rect.top
  const pct = Math.max(15, Math.min(75, (y / rect.height) * 100))
  splitRatio.value = pct
}

function onSplitMouseUp() {
  isDragging.value = false
}

onMounted(() => {
  document.addEventListener('mousemove', onSplitMouseMove)
  document.addEventListener('mouseup', onSplitMouseUp)
})
onUnmounted(() => {
  document.removeEventListener('mousemove', onSplitMouseMove)
  document.removeEventListener('mouseup', onSplitMouseUp)
})

// ── 查询历史 (localStorage) ──
const historyKey = computed(() => `sql_history_${props.connId}`)
const queryHistory = ref<{ sql: string; time: string }[]>([])

function loadHistory() {
  try {
    const raw = localStorage.getItem(historyKey.value)
    if (raw) queryHistory.value = JSON.parse(raw)
  } catch { /* ignore */ }
}

function saveHistory() {
  try {
    localStorage.setItem(historyKey.value, JSON.stringify(queryHistory.value.slice(0, 50)))
  } catch { /* ignore */ }
}

function addHistory(sql: string) {
  const ts = new Date().toLocaleString()
  queryHistory.value.unshift({ sql, time: ts })
  if (queryHistory.value.length > 50) queryHistory.value.pop()
  saveHistory()
}

function selectFromHistory(item: { sql: string }) {
  sqlText.value = item.sql
}

function clearHistory() {
  queryHistory.value = []
  localStorage.removeItem(historyKey.value)
}

onMounted(loadHistory)

// 分页
const page = ref(1)
const pageSize = ref(100)

const allRows = ref<any[][]>([])
const displayRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return allRows.value.slice(start, start + pageSize.value)
})
const totalPages = computed(() => Math.max(1, Math.ceil(allRows.value.length / pageSize.value)))
const totalRows = computed(() => allRows.value.length)

// 水平滚动：每列按 160px 计算总宽度
const scrollX = computed(() => {
  if (!result.value?.columns) return 0
  return Math.max(result.value.columns.length * 160, 600)
})

// 编辑状态
const editCell = ref<{ row: number; col: number } | null>(null)
const editValue = ref('')
const modifiedCells = ref<Map<string, string>>(new Map())

async function runQuery() {
  if (!sqlText.value.trim()) return
  if (!props.connId) {
    message.warning('连接不存在')
    return
  }
  running.value = true
  error.value = ''
  const t0 = performance.now()

  try {
    const res: any = await api.executeSQL(
      props.connId,
      sqlText.value,
      props.dbName || undefined,
    )

    if (res.success) {
      result.value = res.data
      allRows.value = res.data.rows || []
      page.value = 1
      modifiedCells.value.clear()
      addHistory(sqlText.value)
    } else {
      error.value = res.message || '执行失败'
      result.value = null
      allRows.value = []
    }
  } catch (e: any) {
    error.value = e.message
    result.value = null
    allRows.value = []
  } finally {
    queryTime.value = Math.round((performance.now() - t0) * 10) / 10 // ms, 1 decimal
    running.value = false
  }
}


function clearSql() { sqlText.value = '' }

function formatSql() {
  // 简单格式化：关键字大写 + 缩进
  let s = sqlText.value.trim()
  if (!s) return
  const kw = /\b(SELECT|FROM|WHERE|AND|OR|ORDER BY|GROUP BY|HAVING|LIMIT|OFFSET|INSERT INTO|VALUES|UPDATE|SET|DELETE|CREATE|ALTER|DROP|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN|ON|UNION|ALL|INTO|LIKE|BETWEEN|EXISTS|NOT|IN|AS|DISTINCT|COUNT|SUM|AVG|MIN|MAX|INTO)\b/gi
  s = s.replace(kw, m => m.toUpperCase())
  // 在主要关键字前加换行（不在字符串内）
  const breakKw = /\b(WHERE|ORDER BY|GROUP BY|HAVING|LIMIT|OFFSET|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN|ON|UNION|AND|OR)\b/gi
  const parts: string[] = []
  let last = 0
  let match: RegExpExecArray | null
  while ((match = breakKw.exec(s)) !== null) {
    const pos = match.index
    if (pos > last) parts.push(s.slice(last, pos))
    // 检测是否在引号内（简单检测）
    const before = s.slice(0, pos)
    const quotes = (before.match(/'/g)||[]).length
    if (quotes % 2 === 1) {
      parts.push(match[0])
    } else {
      parts.push('\n  ' + match[0])
    }
    last = breakKw.lastIndex
  }
  if (last < s.length) parts.push(s.slice(last))
  sqlText.value = parts.join('').trim()
}

function startEdit(rowIdx: number, colIdx: number) {
  const row = allRows.value[(page.value - 1) * pageSize.value + rowIdx]
  if (!row) return
  const cellKey = `${(page.value - 1) * pageSize.value + rowIdx}-${colIdx}`
  editValue.value = String(modifiedCells.value.get(cellKey) ?? row[colIdx] ?? '')
  editCell.value = { row: rowIdx, col: colIdx }
}

function commitEdit(rowIdx: number, colIdx: number) {
  if (!editCell.value) return
  const absRow = (page.value - 1) * pageSize.value + rowIdx
  const cellKey = `${absRow}-${colIdx}`
  modifiedCells.value.set(cellKey, editValue.value)
  editCell.value = null
}

// 导出当前结果集
const exporting = ref(false)
async function exportResult() {
  if (!result.value || allRows.value.length === 0) {
    message.warning('没有可导出的数据')
    return
  }
  exporting.value = true
  try {
    const cols = result.value.columns
    const data = [cols, ...allRows.value.map(row => row.map(v => v ?? ''))]
    const BOM = '\uFEFF'
    const csv = BOM + data.map(row =>
      row.map(v => {
        const s = String(v ?? '')
        return s.includes(',') || s.includes('"') || s.includes('\n')
          ? '"' + s.replace(/"/g, '""') + '"'
          : s
      }).join(',')
    ).join('\n')

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `query_result_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    message.success(`已导出 ${allRows.value.length} 行数据`)
  } catch (e: any) {
    message.error('导出失败: ' + (e.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="workbench" :class="{ dragging: isDragging }">
    <!-- SQL 编辑器 -->
    <div class="editor-panel" :style="{ height: splitRatio + '%' }">
      <div class="editor-toolbar">
        <span class="toolbar-title">SQL 查询 <span class="shortcut-hint">Ctrl+Enter</span></span>
        <n-space size="small">
          <n-tag v-if="props.dbName" type="info" size="small">{{ props.dbName }}</n-tag>

          <!-- 查询历史 -->
          <n-popover v-if="queryHistory.length > 0" trigger="click" placement="bottom-start" :width="400">
            <template #trigger>
              <n-button size="tiny" quaternary>📜 历史 ({{ queryHistory.length }})</n-button>
            </template>
            <div class="history-panel">
              <div class="history-header">
                <span style="font-weight:600;font-size:13px">查询历史</span>
                <n-button size="tiny" text type="error" @click="clearHistory">清空</n-button>
              </div>
              <div class="history-list">
                <div
                  v-for="(item, idx) in queryHistory"
                  :key="idx"
                  class="history-item"
                  @click="selectFromHistory(item)"
                >
                  <div class="history-sql">{{ item.sql.slice(0, 120) }}{{ item.sql.length > 120 ? '...' : '' }}</div>
                  <div class="history-time">{{ item.time }}</div>
                </div>
              </div>
            </div>
          </n-popover>

          <n-button size="tiny" quaternary @click="formatSql" title="格式化 SQL">美化</n-button>
          <n-button size="tiny" quaternary @click="clearSql" title="清空编辑器">清空</n-button>
          <n-button size="tiny" type="primary" :loading="running" @click="runQuery">
            ▶ 执行
          </n-button>
        </n-space>
      </div>

      <SqlEditor
        v-model:modelValue="sqlText"
        :connId="props.connId"
        :dbName="props.dbName"
        @execute="runQuery"
      />
    </div>

    <!-- 拖拽分隔条 -->
    <div
      class="split-handle"
      @mousedown="onSplitMouseDown"
      :title="'拖拽调整大小'"
    >
      <div class="split-handle-bar"></div>
    </div>

    <!-- 错误信息 -->
    <n-alert v-if="error" type="error" closable class="error-alert">
      <template #header>
        <span style="font-size:12px">执行错误 ({{ queryTime }}ms)</span>
      </template>
      {{ error }}
    </n-alert>

    <!-- 结果集 -->
    <div class="result-panel" v-if="result && result.columns.length">
      <div class="result-toolbar">
        <span class="toolbar-title">
          查询结果
          <n-tag v-if="result" size="tiny" :type="result.is_query ? 'success' : 'warning'">
            <template v-if="result.is_query">
              {{ totalRows }} 行
            </template>
            <template v-else>
              {{ result.affected }} 行受影响
            </template>
          </n-tag>
        </span>
        <n-space size="small">
          <n-tag v-if="queryTime > 0" size="tiny" type="info">{{ queryTime }}ms</n-tag>
          <n-button
            size="tiny"
            :loading="exporting"
            @click="exportResult"
          >
            导出 CSV
          </n-button>
        </n-space>
      </div>

      <div class="table-wrapper">
        <n-data-table
          :scroll-x="scrollX"
          single-line
          :columns="result.columns.map((col, ci) => ({
            title: col,
            key: col,
            width: 160,
            resizable: true,
            ellipsis: { tooltip: true },
            render: (row: any, ri: number) => {
              const absRow = (page - 1) * pageSize + ri
              const cellKey = `${absRow}-${ci}`
              const isEditing = editCell?.row === ri && editCell?.col === ci
              const isModified = modifiedCells.has(cellKey)
              const rawVal = row[col]
              const cellVal = modifiedCells.get(cellKey) ?? rawVal
              const isNull = rawVal === null || rawVal === undefined

              if (isEditing) {
                return h('input', {
                  value: editValue,
                  onInput: (e: any) => { editValue = e.target.value },
                  onBlur: () => commitEdit(ri, ci),
                  onKeydown: (e: any) => {
                    if (e.key === 'Enter') commitEdit(ri, ci)
                    if (e.key === 'Escape') editCell = null
                  },
                  style: {
                    width: '100%',
                    border: '2px solid #3498db',
                    background: '#2a2a2a',
                    color: '#e0e0e0',
                    padding: '1px 4px',
                    borderRadius: '2px',
                    outline: 'none',
                    fontSize: '12px',
                    lineHeight: '18px',
                  },
                  autofocus: '',
                })
              }

              return h('span', {
                onClick: () => startEdit(ri, ci),
                style: {
                  cursor: 'text',
                  color: isNull ? '#666' : (isModified ? '#6f6' : '#ccc'),
                  fontStyle: isNull ? 'italic' : 'normal',
                  background: isModified ? 'rgba(45, 100, 45, 0.15)' : 'transparent',
                  padding: '0 4px',
                  display: 'block',
                  minHeight: '22px',
                  lineHeight: '22px',
                  fontSize: '12px',
                },
                title: isNull ? 'NULL' : (isModified ? `已修改: ${cellVal}` : String(cellVal)),
              }, isNull ? 'NULL' : String(cellVal))
            },
          })) as any"
          :data="displayRows.map((row, ri) => {
            const obj: any = {}
            result!.columns.forEach((col, ci) => { obj[col] = row[ci] })
            return obj
          })"
          :bordered="true"
          striped
          :max-height="500"
          virtual-scroll
          :row-height="28"
        />
      </div>

      <!-- 底部分页栏 -->
      <div class="result-footer" v-if="totalRows > 0">
        <span class="footer-info">共 {{ totalRows }} 行</span>
        <n-space v-if="totalPages > 1" size="small" align="center">
          <span class="footer-label">每页</span>
          <n-select
            v-model:value="pageSize"
            :options="[
              { label: '50 条', value: 50 },
              { label: '100 条', value: 100 },
              { label: '200 条', value: 200 },
              { label: '500 条', value: 500 },
            ]"
            size="tiny"
            style="width: 90px"
          />
          <n-button size="tiny" :disabled="page <= 1" @click="page--">上一页</n-button>
          <span class="page-info">
            第
            <n-input-number
              v-model:value="page"
              :min="1"
              :max="totalPages"
              size="tiny"
              style="width: 60px; display: inline-block;"
            />
            / {{ totalPages }} 页
          </span>
          <n-button size="tiny" :disabled="page >= totalPages" @click="page++">下一页</n-button>
        </n-space>
        <span class="footer-info">{{ modifiedCells.size > 0 ? `已修改 ${modifiedCells.size} 个单元格` : '' }}</span>
      </div>
    </div>

    <n-empty v-else-if="result && !result.columns.length" description="查询执行成功，无返回数据" />
  </div>
</template>

<style scoped>
.workbench {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
  gap: 6px;
}
.workbench.dragging { user-select: none; cursor: row-resize; }
.workbench.dragging .table-wrapper { pointer-events: none; }

.editor-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 60px;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.toolbar-title {
  color: #cccccc;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.shortcut-hint { color: #666; font-weight: 400; font-size: 11px; }

/* ── 拖拽分隔条 ── */
.split-handle {
  height: 6px;
  cursor: row-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin: -1px 0;
  position: relative;
  z-index: 10;
}
.split-handle:hover .split-handle-bar,
.workbench.dragging .split-handle-bar {
  background: #0078d4;
  height: 3px;
}
.split-handle-bar {
  width: 40px;
  height: 2px;
  border-radius: 2px;
  background: #555;
  transition: background 0.15s, height 0.15s;
}

/* ── 查询历史 ── */
.history-panel {
  max-height: 400px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px 8px;
  border-bottom: 1px solid #333;
}
.history-list {
  overflow-y: auto;
  max-height: 360px;
}
.history-item {
  padding: 6px 8px;
  cursor: pointer;
  border-bottom: 1px solid #2a2a2a;
}
.history-item:hover {
  background: #2a2a2a;
}
.history-sql {
  font-family: 'Consolas', monospace;
  font-size: 12px;
  color: #ccc;
  white-space: pre-wrap;
  word-break: break-all;
}
.history-time {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
}

.sql-editor {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}

.error-alert {
  margin: 4px 0;
  flex-shrink: 0;
}

.result-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 0;
  overflow: hidden;
}

.result-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.result-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-top: 1px solid #333;
  flex-shrink: 0;
}

.footer-info {
  color: #888;
  font-size: 12px;
}

.footer-label {
  color: #888;
  font-size: 12px;
}

.page-info {
  color: #888888;
  font-size: 12px;
}

.table-wrapper {
  flex: 1;
  overflow: auto;
}

.table-wrapper :deep(.n-data-table-th) {
  padding: 3px 4px !important;
  height: auto !important;
  line-height: 20px;
  font-size: 12px;
}

.table-wrapper :deep(.n-data-table-tr) {
  height: auto !important;
}

/* 虚拟滚动内部 item 高度覆盖 */
.table-wrapper :deep(.n-base-virtual-list-item) {
  padding: 0 !important;
  margin: 0 !important;
  line-height: 22px;
}

.table-wrapper :deep(.n-data-table-base-table-body-cell) {
  padding: 0 !important;
  margin: 0 !important;
}
</style>