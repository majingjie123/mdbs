<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ExecResult } from '../api'
import { useMessage } from 'naive-ui'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const connId = computed(() => parseInt(route.params.connId as string))
const dbName = computed(() => (route.params.db as string) || '')

const sqlText = ref(`SELECT * FROM information_schema.tables LIMIT 100`)
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

// 编辑状态
const editCell = ref<{ row: number; col: number } | null>(null)
const editValue = ref('')
const modifiedCells = ref<Map<string, string>>(new Map())

async function runQuery() {
  if (!sqlText.value.trim()) return
  running.value = true
  error.value = ''

  try {
    const res: any = await api.executeSQL(
      connId.value,
      sqlText.value,
      dbName.value || undefined,
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
</script>

<template>
  <div class="workbench">
    <!-- SQL 编辑器 -->
    <div class="editor-panel">
      <div class="editor-toolbar">
        <span class="toolbar-title">SQL 查询</span>
        <n-space size="small">
          <n-tag v-if="dbName" type="info" size="small">{{ dbName }}</n-tag>
          <n-button size="tiny" type="primary" :loading="running" @click="runQuery">
            ▶ 执行
          </n-button>
        </n-space>
      </div>

      <n-input
        v-model:value="sqlText"
        type="textarea"
        :rows="6"
        placeholder="输入 SQL 语句..."
        :autosize="{ minRows: 4, maxRows: 12 }"
        class="sql-editor"
      />
    </div>

    <!-- 错误信息 -->
    <n-alert v-if="error" type="error" closable class="error-alert">
      {{ error }}
    </n-alert>

    <!-- 结果集 -->
    <div class="result-panel">
      <div class="result-toolbar">
        <span class="toolbar-title">
          查询结果
          <n-tag v-if="result" size="tiny" type="success">
            {{ totalRows }} 行
            <template v-if="result.affected > 0"> / {{ result.affected }} 行受影响</template>
          </n-tag>
        </span>
        <n-space v-if="totalPages > 1" size="small">
          <n-button size="tiny" :disabled="page <= 1" @click="page--">上一页</n-button>
          <span class="page-info">第 {{ page }} / {{ totalPages }} 页</span>
          <n-button size="tiny" :disabled="page >= totalPages" @click="page++">下一页</n-button>
        </n-space>
      </div>

      <div class="table-wrapper" v-if="result && result.columns.length">
        <n-data-table
          :columns="result.columns.map((col, ci) => ({
            title: col,
            key: col,
            ellipsis: { tooltip: true },
            render: (row: any, ri: number) => {
              const absRow = (page - 1) * pageSize + ri
              const cellKey = `${absRow}-${ci}`
              const isEditing = editCell?.row === ri && editCell?.col === ci
              const isModified = modifiedCells.has(cellKey)
              const val = modifiedCells.get(cellKey) ?? row[ci] ?? ''

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
                    padding: '2px 4px',
                    borderRadius: '2px',
                    outline: 'none',
                    fontSize: '13px',
                  },
                  autofocus: '',
                })
              }

              return h('span', {
                onClick: () => startEdit(ri, ci),
                style: {
                  cursor: 'text',
                  background: isModified ? '#2d4a2d' : 'transparent',
                  padding: '2px 4px',
                  display: 'block',
                  minHeight: '22px',
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
        />
      </div>

      <n-empty v-else-if="result && !result.columns.length" description="查询执行成功，无返回数据" />
    </div>
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

.page-info {
  color: #888888;
  font-size: 12px;
}

.table-wrapper {
  flex: 1;
  overflow: auto;
}
</style>
