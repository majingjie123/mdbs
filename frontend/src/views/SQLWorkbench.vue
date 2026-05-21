<script setup lang="ts">
import { ref, computed, h, shallowRef, markRaw, nextTick, onMounted, onUnmounted, reactive, watch } from 'vue'
import { api, ExecResult } from '../api'
import { useMessage } from 'naive-ui'
import SqlEditor from '../components/SqlEditor.vue'
import AIAssistantPanel from '../components/AIAssistantPanel.vue'
const props = withDefaults(defineProps<{
  connId?: number
  dbName?: string
  schemaName?: string
  initialSql?: string
  savedQueryId?: number        // 从已保存的查询打开时需要
  savedQueryName?: string      // 已保存查询的名称
}>(), {
  connId: 0,
  dbName: '',
  schemaName: '',
  initialSql: '',
  savedQueryId: 0,
  savedQueryName: '',
})

const message = useMessage()

const sqlText = ref(props.initialSql || `SELECT 1`)
const result = ref<ExecResult | null>(null)
const running = ref(false)
const error = ref('')
const abortController = ref<AbortController | null>(null)

// ── 查询耗时 ──
const queryTime = ref(0)

// ── 可拖拽分屏 (编辑器高度百分比) ──
const splitRatio = ref(35) // 编辑器占比 %
const isDragging = ref(false)

// ── AI 助手侧边栏 ──
const showAiAssistant = ref(false)

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

// ── 分页 ──
const page = ref(1)
const pageSize = ref(1000)

const allRows = shallowRef<any[][]>([])
// 后端已分页，displayRows 即返回结果
const displayRows = computed(() => allRows.value)
const totalRows = computed(() => result.value?.total ?? allRows.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(totalRows.value / pageSize.value)))

// 上次查询参数，用于翻页时重新请求
const lastQuery = reactive<{ sql: string; database?: string }>({ sql: '' })

// 翻页时重新请求服务端
watch([page, pageSize], () => {
  if (lastQuery.sql && result.value?.is_query) {
    runQueryPage()
  }
})

// 将二维数组转为对象数组（缓存，仅 displayRows 或 columns 变化时重算）
const mappedRows = computed(() => {
  const cols = result.value?.columns
  if (!cols) return []
  const rows = displayRows.value
  const out: Record<string, any>[] = new Array(rows.length)
  for (let ri = 0; ri < rows.length; ri++) {
    const row = rows[ri]
    const obj: Record<string, any> = {}
    for (let ci = 0; ci < cols.length; ci++) {
      obj[cols[ci]] = row[ci]
    }
    out[ri] = obj
  }
  return out
})

// 水平滚动按钮（带 debounce 避免频繁 reflow）
const scrollContainerRef = ref<HTMLElement | null>(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(false)
let _scrollTimer: number | null = null
function updateScrollButtons() {
  if (_scrollTimer !== null) return // 已排队
  _scrollTimer = window.requestAnimationFrame(() => {
    _scrollTimer = null
    const el = scrollContainerRef.value
    if (!el) { canScrollLeft.value = false; canScrollRight.value = false; return }
    canScrollLeft.value = el.scrollLeft > 4
    canScrollRight.value = el.scrollLeft < el.scrollWidth - el.clientWidth - 4
  })
}
function scrollLeftStep() {
  const el = scrollContainerRef.value
  if (!el) return
  el.scrollBy({ left: -260, behavior: 'smooth' })
  requestAnimationFrame(() => requestAnimationFrame(updateScrollButtons))
}
function scrollRightStep() {
  const el = scrollContainerRef.value
  if (!el) return
  el.scrollBy({ left: 260, behavior: 'smooth' })
  requestAnimationFrame(() => requestAnimationFrame(updateScrollButtons))
}

// 水平滚动：每列按 160px 计算总宽度
const scrollX = computed(() => {
  if (!result.value?.columns) return 0
  return Math.max(result.value.columns.length * 160, 600)
})

// 结果集自适应高度：随窗口大小变化
const tableMaxHeight = ref(500)
function updateTableMaxHeight() {
  const panel = document.querySelector('.result-panel') as HTMLElement | null
  if (panel) {
    // 留出工具栏(36px) + 底部栏(42px) + padding(8px)
    const avail = panel.clientHeight - 86
    tableMaxHeight.value = Math.max(200, avail)
  }
}
onMounted(() => {
  window.addEventListener('resize', updateTableMaxHeight)
  // 首次渲染后计算
  nextTick(updateTableMaxHeight)
})
onUnmounted(() => {
  window.removeEventListener('resize', updateTableMaxHeight)
})

// 编辑状态（非响应式 stores + version 触发器，避免每个 cell render 创建海量 deps）
let _editCell: { row: number; col: number } | null = null
let _editValue = ''
const _modifiedMap = new Map<string, string>()
const _cellVersion = ref(0)  // 编辑/修改变化时 +1，所有 cell render 通过它创建单个 dep
const modifiedCount = computed(() => _modifiedMap.size)
const saving = ref(false)

// 列定义 computed，仅 columns 变化时重建（不依赖 page/pageSize）
const tableColumns = computed(() => {
  if (!result.value?.columns) return []
  const cols = result.value.columns
  const defs = cols.map((col, ci) => markRaw({
    title: col,
    key: col,
    width: 160,
    resizable: true,
    ellipsis: { tooltip: true },
    render: (row: any, ri: number) => {
      // 用 _cellVersion 创建唯一 reactivity dep，读取非响应式 store 避免海量 deps
      _cellVersion.value; // 只读一次，建立单个 dep
      const p = page.value
      const ps = pageSize.value
      const absRow = (p - 1) * ps + ri
      const cellKey = `${absRow}-${ci}`
      const ec = _editCell
      const isEditing = ec !== null && ec.row === ri && ec.col === ci
      const isModified = _modifiedMap.has(cellKey)
      const rawVal = row[col]
      const cellVal = _modifiedMap.get(cellKey) ?? rawVal
      const isNull = rawVal === null || rawVal === undefined

      if (isEditing) {
        return h('input', {
          value: _editValue,
          onInput: (e: any) => { _editValue = e.target.value },
          onBlur: () => commitEdit(ri, ci),
          onKeydown: (e: any) => {
            if (e.key === 'Enter') commitEdit(ri, ci)
            if (e.key === 'Escape') { _editCell = null; _cellVersion.value++ }
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
  }))
  return defs
})

async function runQuery() {
  if (!sqlText.value.trim()) return
  if (!props.connId) {
    message.warning('连接不存在')
    return
  }
  running.value = true
  error.value = ''
  const t0 = performance.now()

  const ac = new AbortController()
  abortController.value = ac

  try {
    lastQuery.sql = sqlText.value
    const offset = (page.value - 1) * pageSize.value
    const res: any = await api.executeSQL(
      props.connId,
      sqlText.value,
      props.dbName || undefined,
      undefined,
      ac.signal,
      pageSize.value,
      offset,
    )

    if (res.success) {
      result.value = res.data
      allRows.value = res.data.rows || []
      page.value = 1
      _modifiedMap.clear()
      _cellVersion.value++
      addHistory(sqlText.value)
      nextTick(() => updateScrollButtons())
    } else {
      error.value = res.message || '执行失败'
      result.value = null
      allRows.value = []
    }
  } catch (e: any) {
    if (e.name === 'AbortError' || e.message?.includes('abort')) return
    error.value = e.message
    result.value = null
    allRows.value = []
  } finally {
    abortController.value = null
    queryTime.value = Math.round((performance.now() - t0) * 10) / 10 // ms, 1 decimal
    running.value = false
  }
}

/** 翻页查询（不重置 page，不记录历史） */
async function runQueryPage() {
  if (!props.connId || !lastQuery.sql) return
  running.value = true
  const t0 = performance.now()
  const ac = new AbortController()
  abortController.value = ac
  try {
    const offset = (page.value - 1) * pageSize.value
    const res: any = await api.executeSQL(
      props.connId,
      lastQuery.sql,
      lastQuery.database || props.dbName || undefined,
      undefined,
      ac.signal,
      pageSize.value,
      offset,
    )
    if (res.success && res.data) {
      result.value = res.data
      allRows.value = res.data.rows || []
      queryTime.value = Math.round((performance.now() - t0) * 10) / 10
    }
  } catch (e: any) {
    if (e.name === 'AbortError' || e.message?.includes('abort')) return
    error.value = e.message
    result.value = null
    allRows.value = []
  } finally {
    abortController.value = null
    running.value = false
  }
}

function stopQuery() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
    running.value = false
    message.info('查询已取消')
  }
}


function clearSql() { sqlText.value = ''; error.value = '' }

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
  const absRow = (page.value - 1) * pageSize.value + rowIdx
  const cellKey = `${absRow}-${colIdx}`
  _editValue = String(_modifiedMap.get(cellKey) ?? row[colIdx] ?? '')
  _editCell = { row: rowIdx, col: colIdx }
  _cellVersion.value++
}

function commitEdit(rowIdx: number, colIdx: number) {
  if (!_editCell) return
  const absRow = (page.value - 1) * pageSize.value + rowIdx
  const cellKey = `${absRow}-${colIdx}`
  const row = allRows.value[absRow]
  const oldVal = row ? row[colIdx] : undefined
  const newVal = _editValue
  // 值没变 → 跳过
  if (oldVal === null && newVal === '') return
  if (oldVal !== null && String(oldVal) === newVal) return
  // 清空数字字段 → 跳过（避免 DOUBLE 列 1292 错误）
  if (typeof oldVal === 'number' && newVal === '') return
  _modifiedMap.set(cellKey, newVal)
  _editCell = null
  _cellVersion.value++
}

// ── 取消所有修改 ──
function cancelEdits() {
  _modifiedMap.clear()
  _cellVersion.value++
}

// ── 保存修改到数据库 ──
function escapeSql(val: any): string {
  if (val === null || val === undefined) return 'NULL'
  const s = String(val)
  // 转义单引号 (MySQL: '' 转义)
  return `'${s.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`
}

function guessTableName(sql: string): string | null {
  // 尝试匹配 FROM/JOIN 后的第一个表名（支持反引号/引号包裹）
  const m = sql.match(
    /(?:FROM|JOIN|UPDATE|INTO)\s+`?([a-zA-Z_][\w$]*)`?/i
  )
  return m ? m[1] : null
}

async function saveEdits() {
  if (_modifiedMap.size === 0) return
  if (!props.connId) {
    message.warning('连接不存在')
    return
  }

  const tableName = guessTableName(sqlText.value)
  if (!tableName) {
    message.warning('无法从 SQL 中解析表名，请使用单表查询（如 SELECT * FROM table）')
    return
  }

  const cols = result.value?.columns
  if (!cols || cols.length === 0) return

  saving.value = true
  // 使用参数化查询：{ sql: string, params: any[] }[]
  const sqls: { sql: string; params: any[] }[] = []

  // 按行分组：cellKey = "absRow-colIdx"
  const rowMap = new Map<number, Map<number, string>>()
  for (const [key, newVal] of _modifiedMap) {
    const [r, c] = key.split('-').map(Number)
    if (!rowMap.has(r)) rowMap.set(r, new Map())
    rowMap.get(r)!.set(c, newVal)
  }

  for (const [absRow, modCols] of rowMap) {
    const rowData = allRows.value[absRow]
    if (!rowData) continue

    const setClauses: string[] = []
    const setParams: any[] = []
    const whereClauses: string[] = []
    const whereParams: any[] = []

    for (let ci = 0; ci < cols.length; ci++) {
      const colName = cols[ci]
      const newVal = modCols.get(ci)
      const oldVal = rowData[ci]

      // 二次保护：空字符串写入 NULL 或数字列 → 跳过 SET（通常历史脏数据）
      // 极端保护：任何空字符串值都转为 null，避免 MySQL 类型不兼容
      const noopNewVal = (newVal === '') ? null : newVal

      if (newVal !== undefined) {
        // 被修改的列 → SET 用新值（空字符串转为 null）
        setClauses.push(`\`${colName}\` = %s`)
        setParams.push(noopNewVal)
        // WHERE 用原值定位
        if (oldVal === null || oldVal === undefined) {
          whereClauses.push(`\`${colName}\` IS NULL`)
        } else {
          whereClauses.push(`\`${colName}\` = %s`)
          whereParams.push(oldVal)
        }
      } else {
        // 未修改的列（或跳过无意义修改）→ 只用做 WHERE
        if (oldVal === null || oldVal === undefined) {
          whereClauses.push(`\`${colName}\` IS NULL`)
        } else {
          whereClauses.push(`\`${colName}\` = %s`)
          whereParams.push(oldVal)
        }
      }
    }

    if (setClauses.length === 0) continue

    const database = props.dbName ? `\`${props.dbName}\`.` : ''
    const sql = `UPDATE ${database}\`${tableName}\` SET ${setClauses.join(', ')} WHERE ${whereClauses.join(' AND ')} LIMIT 1;`
    sqls.push({ sql, params: [...setParams, ...whereParams] })
  }

  if (sqls.length === 0) {
    message.info('没有需要保存的修改')
    saving.value = false
    return
  }

  // 调试：打印每一条 SQL 和参数
  console.log('=== saveEdits 调试 ===')
  for (const s of sqls) {
    console.log('SQL:', s.sql)
    console.log('Params:', JSON.stringify(s.params))
  }

  try {
    const res: any = await api.executeBatch(props.connId, sqls, props.dbName || undefined)
    if (res.success) {
      message.success(`成功保存 ${sqls.length} 行修改`)
      // 将新值写回 allRows，使界面立即反映修改
      for (const [absRow, modCols] of rowMap) {
        const rowData = allRows.value[absRow]
        if (rowData) {
          for (const [ci, newVal] of modCols) {
            rowData[ci] = newVal
          }
        }
      }
      _modifiedMap.clear()
      _cellVersion.value++
    } else {
      // 在错误消息中附带第一条 SQL 的参数信息，帮助定位脏数据
      const debug1 = sqls.length > 0
        ? `\nSQL: ${sqls[0].sql}\nParams: ${JSON.stringify(sqls[0].params)}`
        : ''
      message.error('保存失败: ' + (res.message || '') + debug1)
    }
  } catch (e: any) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
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
    const filename = `query_result_${Date.now()}.csv`

    // 在 pywebview 环境下使用原生保存对话框
    const pv = (window as any).pywebview
    if (pv?.api) {
      const reader = new FileReader()
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1]
        pv.api.save_file(filename, base64)
      }
      reader.readAsDataURL(blob)
      message.success(`已导出 ${allRows.value.length} 行数据`)
      return
    }

    // 浏览器环境退化方案
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    message.success(`已导出 ${allRows.value.length} 行数据`)
  } catch (e: any) {
    message.error('导出失败: ' + (e.message || '未知错误'))
  } finally {
    exporting.value = false
  }
}

// ── 保存查询 ──
const saveQueryDialog = ref(false)
const saveQueryName = ref('')
const savingQuery = ref(false)
const isUpdateOnly = ref(false)  // true = 直接覆盖已有名称

function openSaveQueryDialog() {
  if (props.savedQueryId && props.savedQueryName) {
    // 已有保存的查询 → 询问覆盖还是另存
    saveQueryName.value = props.savedQueryName
    isUpdateOnly.value = true
  } else {
    saveQueryName.value = sqlText.value.trim().split('\n')[0].replace(/^--\s*/, '').slice(0, 30) || '新查询'
    isUpdateOnly.value = false
  }
  saveQueryDialog.value = true
}

async function doSaveQuery(overwrite?: boolean) {
  if (!saveQueryName.value.trim()) {
    message.warning('请输入查询名称')
    return
  }
  savingQuery.value = true
  try {
    if (props.savedQueryId && overwrite !== false) {
      // 覆盖已保存的查询
      const res: any = await api.updateQuery(props.savedQueryId, {
        sql_text: sqlText.value,
      })
      if (res.success) {
        message.success('查询已保存')
        saveQueryDialog.value = false
      } else {
        message.error('保存失败: ' + (res.message || ''))
      }
    } else {
      // 新建查询 (或在已有基础上另存为)
      const res: any = await api.createQuery({
        conn_id: props.connId,
        db_name: props.dbName,
        name: saveQueryName.value.trim(),
        sql_text: sqlText.value,
      })
      if (res.success) {
        message.success(`查询「${saveQueryName.value.trim()}」已保存`)
        // 更新 props 中的 savedQueryId 和 title
        // 由于 props 是只读的，我们通过更新 title 来反映当前编辑的是已保存查询
        saveQueryDialog.value = false
      } else {
        message.error('保存失败: ' + (res.message || ''))
      }
    }
  } catch (e: any) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    savingQuery.value = false
  }
}
</script>

<template>
  <div class="workbench" :class="{ dragging: isDragging, 'with-ai': showAiAssistant }">
    <!-- 主区域：SQL 编辑器 + 结果 -->
    <div class="main-area">
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
          <n-button size="tiny" quaternary @click="openSaveQueryDialog" title="保存当前 SQL 到侧边栏查询列表">
            💾 保存查询
          </n-button>
          <!-- AI 助手切换按钮 -->
          <n-button
            size="tiny"
            :type="showAiAssistant ? 'primary' : 'default'"
            quaternary
            @click="showAiAssistant = !showAiAssistant"
            title="AI 助手"
          >
            🤖
          </n-button>
          <n-button size="tiny" type="primary" :loading="running" @click="runQuery">
            ▶ 执行
          </n-button>
          <n-button v-show="running" size="tiny" type="error" @click="stopQuery">
            ⬛ 停止
          </n-button>
        </n-space>
      </div>

      <div class="editor-body">
        <div class="editor-sql-area">
          <SqlEditor
            v-model:modelValue="sqlText"
            :connId="props.connId"
            :dbName="props.dbName"
            @execute="runQuery"
          />
        </div>
      </div>
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
            v-if="modifiedCount > 0"
            size="tiny"
            type="warning"
            :loading="saving"
            @click="saveEdits"
          >
            💾 保存修改 ({{ modifiedCount }})
          </n-button>
          <n-button
            v-if="modifiedCount > 0"
            size="tiny"
            @click="cancelEdits"
          >
            取消修改
          </n-button>
          <n-button
            size="tiny"
            :loading="exporting"
            @click="exportResult"
          >
            导出 CSV
          </n-button>
        </n-space>
      </div>

      <div class="table-scroll-wrapper">
        <button
          class="scroll-btn scroll-btn-left"
          :class="{ visible: canScrollLeft }"
          @click="scrollLeftStep"
          title="向左滚动"
        >‹</button>
        <div
          class="table-wrapper"
          ref="scrollContainerRef"
          @scroll="updateScrollButtons"
        >
          <n-data-table
            :scroll-x="scrollX"
            single-line
            :columns="tableColumns"
            :data="mappedRows"
            :bordered="true"
            striped
            :max-height="tableMaxHeight"
            virtual-scroll
            :row-height="28"
            :row-key="(row: Record<string, any>, idx: number) => (page - 1) * pageSize + idx"
          />
        </div>
        <button
          class="scroll-btn scroll-btn-right"
          :class="{ visible: canScrollRight }"
          @click="scrollRightStep"
          title="向右滚动"
        >›</button>
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
              { label: '1000 条', value: 1000 },
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
        <span class="footer-info">{{ modifiedCount > 0 ? `已修改 ${modifiedCount} 个单元格` : '' }}</span>
      </div>
    </div>

    <n-empty v-else-if="result && !result.columns.length" description="查询执行成功，无返回数据" />

    <!-- 保存查询对话框 -->
    <n-modal v-model:show="saveQueryDialog" title="保存查询" preset="card" style="width: 450px" :mask-closable="false">
      <n-space vertical>
        <n-input
          v-model:value="saveQueryName"
          placeholder="输入查询名称..."
          :disabled="isUpdateOnly && !!props.savedQueryId"
        />
        <n-input
          v-model:value="sqlText"
          type="textarea"
          :autosize="{ minRows: 5, maxRows: 12 }"
          placeholder="SQL 语句"
        />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="saveQueryDialog = false">取消</n-button>
          <n-button v-if="isUpdateOnly" @click="doSaveQuery(false)" :loading="savingQuery">
            另存为新查询
          </n-button>
          <n-button type="primary" @click="doSaveQuery()" :loading="savingQuery">
            {{ isUpdateOnly ? '覆盖保存' : '保存' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
    </div><!-- /.main-area -->
    <!-- AI 助手侧边栏 -->
    <div v-if="showAiAssistant" class="ai-sidebar">
      <AIAssistantPanel
        :conn-id="props.connId"
        :db-name="props.dbName"
        :schema-name="props.schemaName"
      />
    </div>
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
.workbench.with-ai {
  flex-direction: row;
}
.workbench.dragging { user-select: none; cursor: row-resize; }
.workbench.dragging .table-wrapper { pointer-events: none; }

/* AI 助手侧边栏 */
.ai-sidebar {
  width: 320px;
  min-width: 280px;
  max-width: 400px;
  border-left: 1px solid var(--color-border, #333);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: aiSlideIn 0.2s ease;
}
@keyframes aiSlideIn {
  from { width: 0; min-width: 0; opacity: 0; }
  to { width: 320px; min-width: 280px; opacity: 1; }
}

/* 主区域（编辑器 + 结果） */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}

.editor-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 60px;
  overflow: hidden;
}

.editor-body {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 0;
  overflow: hidden;
}

.editor-sql-area {
  flex: 1;
  min-width: 0;
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

/* ── 水平滚动按钮 ── */
.table-scroll-wrapper {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
  min-height: 0;
}
.table-scroll-wrapper .table-wrapper {
  flex: 1;
  overflow: auto;
}
.scroll-btn {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 10;
  width: 28px;
  border: none;
  background: rgba(30, 30, 30, 0.85);
  color: #aaa;
  font-size: 22px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s, background 0.15s;
  pointer-events: none;
  padding: 0;
}
.scroll-btn:hover {
  background: rgba(60, 60, 60, 0.95);
  color: #fff;
}
.scroll-btn.visible {
  opacity: 1;
  pointer-events: auto;
}
.scroll-btn-left { left: 0; border-radius: 0 4px 4px 0; }
.scroll-btn-right { right: 0; border-radius: 4px 0 0 4px; }

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