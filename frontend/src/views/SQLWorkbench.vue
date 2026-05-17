<script setup lang="ts">
import { ref, computed, h } from 'vue'
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
    running.value = false
  }
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
  <div class="workbench">
    <!-- SQL 编辑器 -->
    <div class="editor-panel">
      <div class="editor-toolbar">
        <span class="toolbar-title">SQL 查询</span>
        <n-space size="small">
          <n-tag v-if="props.dbName" type="info" size="small">{{ props.dbName }}</n-tag>
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

    <!-- 错误信息 -->
    <n-alert v-if="error" type="error" closable class="error-alert">
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
            render: (row: any, ri: number) => {
              const absRow = (page - 1) * pageSize + ri
              const cellKey = `${absRow}-${ci}`
              const isEditing = editCell?.row === ri && editCell?.col === ci
              const isModified = modifiedCells.has(cellKey)
              const val = modifiedCells.get(cellKey) ?? row[col] ?? ''

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
                  color: '#cccccc',
                  background: isModified ? '#2d4a2d' : 'transparent',
                  padding: '0 4px',
display: 'block',
                  minHeight: '22px',
                  lineHeight: '22px',
                  fontSize: '12px',
                },
                title: isModified ? `已修改: ${val}` : String(val),
              }, String(val))
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
  gap: 8px;
}

.editor-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-title {
  color: #cccccc;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sql-editor {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}

.error-alert {
  margin: 4px 0;
}

.result-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 0;
}

.result-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  border-top: 1px solid #333;
}

.footer-info {
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

/* n-data-table 紧凑行高 */
.table-wrapper :deep(.n-data-table-td) {
  padding: 1px 4px !important;
  height: auto !important;
  line-height: 20px;
  font-size: 12px;
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