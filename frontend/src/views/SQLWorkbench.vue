<script setup lang="ts">
import { ref, computed, h, shallowRef, markRaw, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { api, ExecResult } from '../api'
import { useMessage, useDialog } from 'naive-ui'
import { useAppStore } from '../stores/app'
import SqlEditor from '../components/SqlEditor.vue'
import SnippetPanel from '../components/SnippetPanel.vue'
import AIAssistantPanel from '../components/AIAssistantPanel.vue'
const store = useAppStore()
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
const dialog = useDialog()

const sqlText = ref(props.initialSql || `SELECT 1`)
const result = ref<ExecResult | null>(null)
const sqlEditorRef = ref<InstanceType<typeof SqlEditor> | null>(null)

// ── 自动保存草稿 ──
const draftKey = computed(() => `sql_draft_${props.connId}_${props.dbName || ''}`)
let _draftTimer: ReturnType<typeof setTimeout> | null = null
const draftRestored = ref(false)

watch(sqlText, (val) => {
  if (_draftTimer) clearTimeout(_draftTimer)
  if (!val.trim() || val === `SELECT 1`) return // 不保存默认值
  _draftTimer = setTimeout(() => {
    try {
      localStorage.setItem(draftKey.value, val)
    } catch { /* ignore */ }
  }, 1500) // 1.5s 防抖
})

function loadDraft() {
  if (props.initialSql) return // 有初始 SQL 时不恢复草稿
  try {
    const saved = localStorage.getItem(draftKey.value)
    if (saved && saved.trim()) {
      sqlText.value = saved
      draftRestored.value = true
      setTimeout(() => { draftRestored.value = false }, 4000)
    }
  } catch { /* ignore */ }
}

function clearDraft() {
  try {
    localStorage.removeItem(draftKey.value)
  } catch { /* ignore */ }
}

const running = ref(false)
const error = ref('')
const abortController = ref<AbortController | null>(null)
const _lastSql = ref('')  // 追踪上次执行的 SQL 文本，用于判断是否重置页码

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
const favHistoryKey = computed(() => `sql_fav_${props.connId}`)
const queryHistory = ref<{ sql: string; time: string }[]>([])
const favQueries = ref<{ sql: string; name: string }[]>([])
const historySearch = ref('')
const showHistoryPanel = ref(false)
const snippetPanelRef = ref<InstanceType<typeof SnippetPanel> | null>(null)
const showSnippetPanel = ref(false)

// ── 拖拽上传 ──
const isDragOver = ref(false)

function onDrop(e: DragEvent) {
  isDragOver.value = false
  const raw = e.dataTransfer?.getData('application/mdbs-node')
  if (!raw) return
  try {
    const data = JSON.parse(raw)
    const { nodeType, label, connId: dragConnId, dbName: dragDbName, schemaName: dragSchemaName, tableName } = data
    // 只处理表/视图
    if (nodeType !== 'table' && nodeType !== 'view') return
    const name = label || tableName
    if (!name) return

    let sql = ''
    // 检查连接类型
    const isPG = dragConnId && store.connections.find((c: any) => c.id === dragConnId)?.db_type === 'PostgreSQL'

    sql = isPG
      ? `SELECT * FROM "${dragSchemaName || 'public'}"."${name}" LIMIT 1000;`
      : `SELECT * FROM \`${name}\` LIMIT 1000;`

    // 插入到编辑器
    if (sqlText.value && !sqlText.value.endsWith('\n') && !sqlText.value.endsWith(';')) {
      sqlText.value += '\n' + sql
    } else {
      sqlText.value += sql
    }
    clearDraft()
    message.success(`已插入 ${name} 的查询`)
  } catch { /* ignore */ }
}

const filteredHistory = computed(() => {
  if (!historySearch.value.trim()) return queryHistory.value
  const kw = historySearch.value.toLowerCase()
  return queryHistory.value.filter(h => h.sql.toLowerCase().includes(kw))
})

const groupedHistory = computed(() => {
  const groups: Record<string, typeof queryHistory.value> = {}
  const items = filteredHistory.value
  for (const item of items) {
    const date = item.time.split(' ')[0] || '其他'
    if (!groups[date]) groups[date] = []
    groups[date].push(item)
  }
  return groups
})

function loadHistory() {
  try {
    const raw = localStorage.getItem(historyKey.value)
    if (raw) queryHistory.value = JSON.parse(raw)
    const favRaw = localStorage.getItem(favHistoryKey.value)
    if (favRaw) favQueries.value = JSON.parse(favRaw)
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
  showHistoryPanel.value = false
}

function toggleFav(item: { sql: string }) {
  const idx = favQueries.value.findIndex(f => f.sql === item.sql)
  if (idx >= 0) {
    favQueries.value.splice(idx, 1)
    message.info('已取消收藏')
  } else {
    const name = prompt('收藏名称（用于快速识别）:', item.sql.slice(0, 40) + '...')
    if (!name) return
    favQueries.value.unshift({ sql: item.sql, name })
    message.success('已收藏')
  }
  localStorage.setItem(favHistoryKey.value, JSON.stringify(favQueries.value))
}

function isFav(item: { sql: string }) {
  return favQueries.value.some(f => f.sql === item.sql)
}

function selectFromFav(item: { sql: string }) {
  sqlText.value = item.sql
  showHistoryPanel.value = false
}

function deleteFav(item: { sql: string }) {
  favQueries.value = favQueries.value.filter(f => f.sql !== item.sql)
  localStorage.setItem(favHistoryKey.value, JSON.stringify(favQueries.value))
  message.success('已删除收藏')
}

// ── SQL 片段 — 插入到编辑器 ──
function insertSnippet(sql: string) {
  // 追加到编辑器当前内容后面（或替换选中？这里追加）
  sqlText.value = sqlText.value ? `${sqlText.value}\n${sql}` : sql
}

function clearHistory() {
  queryHistory.value = []
  localStorage.removeItem(historyKey.value)
}

onMounted(loadHistory)
onMounted(loadDraft)

// ── 分页 ──
const page = ref(1)
const pageSize = ref(1000)

// ── 多结果集 ──
interface SavedResult {
  sql: string
  data: ExecResult
  rows: any[][]
  modifiedMap: Record<string, string>  // serializable version of _modifiedMap
  newRowIndices: number[]
  queryTime: number
  id: string
  error?: string
}

const results = ref<SavedResult[]>([])
const activeResultIndex = ref(0)

const activeResult = computed(() => results.value[activeResultIndex.value] || null)

const allRows = shallowRef<any[][]>([])
const displayRows = computed(() => {
  // 服务端分页：allRows 就是当前页数据
  return allRows.value
})
const totalPages = computed(() => Math.max(1, Math.ceil((activeResult.value?.data.total_count || 0) / pageSize.value)))
const totalRows = computed(() => activeResult.value?.data.total_count || allRows.value.length)

watch([page, pageSize], () => {
  if (activeResult.value) {
    runQuery()
  }
})

// 切换结果集
function switchResult(idx: number) {
  if (idx < 0 || idx >= results.value.length) return
  // 保存当前结果的状态
  saveCurrentResultState()
  // 切换到新结果
  activeResultIndex.value = idx
  restoreResultState(idx)
}

function saveCurrentResultState() {
  const cur = results.value[activeResultIndex.value]
  if (!cur) return
  cur.rows = allRows.value
  const modMap: Record<string, string> = {}
  for (const [k, v] of _modifiedMap) modMap[k] = v
  cur.modifiedMap = modMap
  cur.newRowIndices = [..._newRowAbsIndices]
  cur.queryTime = queryTime.value
}

function restoreResultState(idx: number) {
  const cur = results.value[idx]
  if (!cur) return
  allRows.value = cur.rows
  _modifiedMap.clear()
  for (const [k, v] of Object.entries(cur.modifiedMap)) _modifiedMap.set(k, v)
  _newRowAbsIndices.clear()
  for (const n of cur.newRowIndices) _newRowAbsIndices.add(n)
  queryTime.value = cur.queryTime
  _cellVersion.value++
  nextTick(() => updateScrollButtons())
}

function closeResult(idx: number) {
  if (results.value.length <= 1) {
    // 最后一个结果 → 清空
    results.value = []
    activeResultIndex.value = 0
    allRows.value = []
    _modifiedMap.clear()
    _cellVersion.value++
    return
  }
  results.value.splice(idx, 1)
  if (activeResultIndex.value >= results.value.length) {
    activeResultIndex.value = results.value.length - 1
  }
  restoreResultState(activeResultIndex.value)
}

// 将二维数组转为对象数组（缓存，仅 displayRows 或 columns 变化时重算）
const mappedRows = computed(() => {
  const cols = activeResult.value?.data?.columns
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
  if (!activeResult.value?.data?.columns) return 0
  return Math.max(activeResult.value.data.columns.length * 160, 600)
})

// 结果集自适应高度：随窗口大小变化
const tableMaxHeight = ref(500)
function updateTableMaxHeight() {
  const panel = document.querySelector('.result-panel') as HTMLElement | null
  if (panel) {
    const avail = panel.clientHeight - 86
    tableMaxHeight.value = Math.max(200, avail)
  }
}
let _resizeTimer: number | null = null
function onResize() {
  if (_resizeTimer) return
  _resizeTimer = window.requestAnimationFrame(() => {
    _resizeTimer = null
    updateTableMaxHeight()
  })
}
onMounted(() => {
  window.addEventListener('resize', onResize)
  nextTick(updateTableMaxHeight)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (_resizeTimer) cancelAnimationFrame(_resizeTimer)
  if (_scrollTimer !== null) cancelAnimationFrame(_scrollTimer)
})

// 编辑状态（非响应式 stores + version 触发器，避免每个 cell render 创建海量 deps）
let _editCell: { row: number; col: number } | null = null
let _editValue = ''
const _modifiedMap = new Map<string, string>()
const _cellVersion = ref(0)  // 编辑/修改变化时 +1，所有 cell render 通过它创建单个 dep
const modifiedCount = computed(() => _modifiedMap.size)
const saving = ref(false)

// 行选择状态
const checkedRowKeys = ref<(string | number)[]>([])
const allRowKeys = computed(() => {
  if (!activeResult.value?.data?.columns) return []
  const cols = activeResult.value.data.columns
  if (!cols.length) return []
  return mappedRows.value.map((_, idx) => (page.value - 1) * pageSize.value + idx)
})

// ── 新增行 ──
const _newRowAbsIndices = new Set<number>()
const hasNewRows = computed(() => _newRowAbsIndices.size > 0)

function addEmptyRow() {
  if (!activeResult.value?.data?.columns || activeResult.value.data.columns.length === 0) {
    message.warning('请先执行查询')
    return
  }
  const cols = activeResult.value.data.columns
  const emptyRow: any[] = new Array(cols.length).fill(null)
  allRows.value = [...allRows.value, emptyRow]

  const relRowIdx = allRows.value.length - 1
  const absRow = (page.value - 1) * pageSize.value + relRowIdx

  // 标记所有列为"待插入"，让用户双击编辑
  for (let ci = 0; ci < cols.length; ci++) {
    _modifiedMap.set(`${absRow}-${ci}`, '')
  }
  _newRowAbsIndices.add(absRow)
  _cellVersion.value++
  message.success('已添加空行，双击单元格编辑值')
}

function removeNewRowMarker(absRow: number) {
  _newRowAbsIndices.delete(absRow)
  for (let ci = 0; ci < (activeResult.value?.data?.columns?.length || 0); ci++) {
    _modifiedMap.delete(`${absRow}-${ci}`)
  }
}

// ── 删除行 ──
const deleting = ref(false)
async function deleteSelectedRows() {
  if (checkedRowKeys.value.length === 0) {
    message.warning('请先勾选要删除的行')
    return
  }
  if (!props.connId) {
    message.warning('连接不存在')
    return
  }

  const tableName = guessTableName(sqlText.value)
  if (!tableName) {
    message.warning('无法确定表名，请使用 SELECT * FROM table 查询')
    return
  }

  const cols = activeResult.value?.data?.columns
  if (!cols || cols.length === 0) return
  const pkCol = cols[0] // 默认第一列为主键

  // 分离"新行"和"已有行"
  const newAbsRows: number[] = []
  const existingAbsRows: number[] = []

  for (const k of checkedRowKeys.value) {
    const absRow = Number(k)
    if (_newRowAbsIndices.has(absRow)) {
      newAbsRows.push(absRow)
    } else {
      existingAbsRows.push(absRow)
    }
  }

  let msg = `确定要删除 ${checkedRowKeys.value.length} 行吗？`
  if (newAbsRows.length > 0) {
    msg += `\n（其中 ${newAbsRows.length} 行为未保存的新行）`
  }
  msg += '\n此操作不可撤销！'

  dialog.warning({
    title: '删除行',
    content: msg,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      deleting.value = true
      try {
        // 1) 先从 allRows 移除新行（无需数据库操作）
        if (newAbsRows.length > 0) {
          const newRelRows = new Set(newAbsRows.map(abs => abs - (page.value - 1) * pageSize.value))
          allRows.value = allRows.value.filter((_, idx) => !newRelRows.has(idx))
          for (const abs of newAbsRows) {
            _newRowAbsIndices.delete(abs)
            for (let ci = 0; ci < (cols?.length || 0); ci++) {
              _modifiedMap.delete(`${abs}-${ci}`)
            }
          }
        }

        // 2) 删除已有行 → 发 DELETE SQL
        if (existingAbsRows.length > 0) {
          const pkValues = existingAbsRows.map(abs => {
            const relRow = abs - (page.value - 1) * pageSize.value
            return allRows.value[relRow]?.[0] // pkCol = columns[0]
          }).filter(v => v !== null && v !== undefined)

          if (pkValues.length > 0) {
            const deleteSqls = pkValues.map(id => ({
              sql: `DELETE FROM ${tableName} WHERE ${pkCol} = ?`,
              params: [id],
            }))
            const res: any = await api.executeBatch(props.connId, deleteSqls, props.dbName || undefined)
            if (!res.success) {
              message.error('删除失败: ' + (res.message || ''))
              return
            }
          }

          // 从 allRows 移除已删除的已有行
          const existingRelRows = new Set(existingAbsRows.map(abs => abs - (page.value - 1) * pageSize.value))
          allRows.value = allRows.value.filter((_, idx) => !existingRelRows.has(idx))
        }

        message.success(`已删除 ${checkedRowKeys.value.length} 行`)
        checkedRowKeys.value = []
        _cellVersion.value++
      } catch (e: any) {
        message.error('删除失败: ' + (e.message || '未知错误'))
      } finally {
        deleting.value = false
      }
    },
  })
}

// 排序状态
const sortState = ref<{ column: string; order: 'asc' | 'desc' } | null>(null)

// 筛选状态
const filterText = ref('')
const filteredRows = computed(() => {
  if (!filterText.value.trim()) return mappedRows.value
  const keyword = filterText.value.toLowerCase()
  return mappedRows.value.filter(row => {
    return Object.values(row).some(val =>
      val !== null && String(val).toLowerCase().includes(keyword)
    )
  })
})

// 列定义 computed，仅 columns 变化时重建（不依赖 page/pageSize）
const columnOrder = ref<string[]>([]) // 用户自定义列顺序，空 = 默认
const colCtxMenu = ref({ visible: false, x: 0, y: 0, col: '' })

const tableColumns = computed(() => {
  if (!activeResult.value?.data?.columns) return []
  let cols = activeResult.value.data.columns
  // 应用用户自定义列顺序
  if (columnOrder.value.length > 0) {
    const ordered = columnOrder.value.filter(c => cols.includes(c))
    const remaining = cols.filter(c => !columnOrder.value.includes(c))
    cols = [...ordered, ...remaining]
  }
  const defs = cols.map((col, ci) => markRaw({
    title: () => h('span', {
      style: 'cursor: pointer; user-select: none;',
      onContextmenu: (e: MouseEvent) => {
        e.preventDefault()
        e.stopPropagation()
        colCtxMenu.value = { visible: true, x: e.clientX, y: e.clientY, col }
      },
    }, col),
    key: col,
    width: 160,
    ellipsis: true,
    sorter: (rowA: any, rowB: any) => {
      const a = rowA[col]
      const b = rowB[col]
      if (a === null || a === undefined) return 1
      if (b === null || b === undefined) return -1
      if (typeof a === 'number' && typeof b === 'number') return a - b
      return String(a).localeCompare(String(b))
    },
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
    const res: any = await api.executeSQL(
      props.connId,
      sqlText.value,
      props.dbName || undefined,
      undefined,
      ac.signal,
      page.value,
      pageSize.value,
    )

    if (res.success) {
      // 仅当 SQL 内容变化时重置到第一页，翻页不重置
      if (sqlText.value !== _lastSql.value) {
        page.value = 1
        _lastSql.value = sqlText.value
      }

      // 检查是否已有同名 SQL 的结果（覆盖更新）
      const existingIdx = results.value.findIndex(r => r.sql === sqlText.value)
      const newResult: SavedResult = {
        sql: sqlText.value,
        data: res.data,
        rows: res.data.rows || [],
        modifiedMap: {},
        newRowIndices: [],
        queryTime: performance.now() - t0,
        id: Date.now().toString(36),
      }

      if (existingIdx >= 0) {
        results.value[existingIdx] = newResult
        activeResultIndex.value = existingIdx
      } else {
        results.value.push(newResult)
        activeResultIndex.value = results.value.length - 1
      }

      allRows.value = newResult.rows
      _modifiedMap.clear()
      _newRowAbsIndices.clear()
      _cellVersion.value++
      addHistory(sqlText.value)
      clearDraft()
      nextTick(() => updateScrollButtons())
    } else {
      error.value = res.message || '执行失败'
      allRows.value = []
    }
  } catch (e: any) {
    if (e.name === 'AbortError' || e.message?.includes('abort')) return
    error.value = e.message
    allRows.value = []
  } finally {
    abortController.value = null
    queryTime.value = Math.round((performance.now() - t0) * 10) / 10 // ms, 1 decimal
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


function clearSql() { sqlText.value = ''; error.value = ''; clearDraft() }

function formatSql() {
  if (sqlEditorRef.value) {
    sqlEditorRef.value.format()
  }
}

// ── EXPLAIN 执行计划 ──
const explainResult = ref('')
const showExplain = ref(false)
const explainTab = ref<'tree' | 'table' | 'raw'>('tree')
const explainTreeData = ref<any[]>([])
const explainTableData = ref<any[]>([])
const explainTableCols = ref<string[]>([])

function parseExplainJson(json: any) {
  // MySQL EXPLAIN FORMAT=JSON → 树形结构
  if (!json) return

  // 表格式数据（降级展示）
  const tableRows: any[] = []
  const tableCols: string[] = []

  function buildTreeNode(node: any, path: string[] = []): any {
    if (!node) return null
    const label = node.Select_type || node.access_type || node.Query_block || node.operation || 'QUERY'
    const table = node.table_name || node.Table || ''
    const key = node.key || node.Key || ''
    const rows = node.rows || node.Rows || 0
    const cost = node.cost_info?.query_cost ?? node.query_cost ?? ''
    const filtered = node.filtered || node.Filtered || ''
    const extra = node.Extra || node.attached_condition || ''

    const details: string[] = []
    if (table) details.push(`📋 ${table}`)
    if (key) details.push(`🔑 ${key}`)
    if (rows) details.push(`📊 ${rows} 行`)
    if (cost) details.push(`💰 成本 ${cost}`)
    if (filtered) details.push(`🎯 ${filtered}%`)
    if (extra) details.push(`📌 ${extra}`)

    // 加到表格式数据
    tableRows.push({
      id: path.join('.'),
      select_type: label,
      table,
      type: node.access_type || node.type || '',
      possible_keys: (node.possible_keys || []).join(', '),
      key,
      key_len: node.key_length || node.key_len || '',
      ref: node.ref || '',
      rows,
      filtered,
      extra,
      cost,
    })

    // 子节点
    const children: any[] = []
    // MySQL JSON 格式嵌套结构
    const nesting_keys = ['nested_loop', 'union_result', 'sub_select', 'query_block', 'table_dependencies', 'materialized_from_subquery', 'table', 'attached_subqueries']
    for (const key of nesting_keys) {
      const val = node[key]
      if (Array.isArray(val)) {
        val.forEach((v: any, i: number) => {
          const child = buildTreeNode(v, [...path, `${key}[${i}]`])
          if (child) children.push(child)
        })
      } else if (val && typeof val === 'object') {
        const child = buildTreeNode(val, [...path, key])
        if (child) children.push(child)
      }
    }

    return {
      label: `${label}${table ? ` — ${table}` : ''}`,
      key: path.join('.'),
      isLeaf: children.length === 0,
      children: children.length > 0 ? children : undefined,
      detail: details.join(' | '),
    }
  }

  // 设置列
  if (tableRows.length > 0) {
    Object.keys(tableRows[0]).forEach(k => { if (!tableCols.includes(k)) tableCols.push(k) })
  }
  explainTableCols.value = tableCols
  explainTableData.value = tableRows

  // 解析顶层
  const root = buildTreeNode(json.query_block || json, ['root'])
  explainTreeData.value = root ? [root] : []
}

// 自定义渲染 EXPLAIN 树节点
function renderExplainNode(info: { option: any }) {
  const node = info.option
  return h('span', { style: 'white-space: nowrap; display: flex; align-items: center; gap: 6px;' }, [
    h('span', node.label),
    node.detail ? h('span', { style: 'color: var(--color-text-muted); font-size: 11px; margin-left: 8px;' }, node.detail) : null,
  ])
}

async function runExplain() {
  if (!sqlText.value.trim()) {
    message.warning('请输入 SQL 语句')
    return
  }
  if (!props.connId) {
    message.warning('连接不存在')
    return
  }

  // 只对 SELECT/INSERT/UPDATE/DELETE 进行 EXPLAIN
  const upperSql = sqlText.value.trim().toUpperCase()
  if (!upperSql.match(/^(SELECT|INSERT|UPDATE|DELETE|REPLACE)/)) {
    message.warning('EXPLAIN 仅支持 SELECT/INSERT/UPDATE/DELETE 语句')
    return
  }

  running.value = true
  showExplain.value = true
  explainResult.value = ''

  try {
    // 使用 EXPLAIN FORMAT=JSON 获取详细信息
    const explainSql = `EXPLAIN FORMAT=JSON ${sqlText.value}`
    const res: any = await api.executeSQL(
      props.connId,
      explainSql,
      props.dbName || undefined,
      undefined,
      undefined,
      1,
      1,
    )

    if (res.success && res.data) {
      // 格式化 JSON 输出
      try {
        const json = typeof res.data.rows[0] === 'string'
          ? JSON.parse(res.data.rows[0][0])
          : res.data.rows[0]
        explainResult.value = JSON.stringify(json, null, 2)
        parseExplainJson(json)
      } catch {
        explainResult.value = res.data.rows[0]?.[0] || JSON.stringify(res.data, null, 2)
      }
    } else {
      // 如果 JSON 格式失败，尝试普通 EXPLAIN
      const simpleExplainSql = `EXPLAIN ${sqlText.value}`
      const simpleRes: any = await api.executeSQL(
        props.connId,
        simpleExplainSql,
        props.dbName || undefined,
        undefined,
        undefined,
        1,
        100,
      )
      if (simpleRes.success && simpleRes.data) {
        // 转换为表格形式显示
        const cols = simpleRes.data.columns || []
        const rows = simpleRes.data.rows || []
        let output = cols.join(' | ') + '\n' + cols.map(() => '---').join(' | ') + '\n'
        for (const row of rows) {
          output += row.join(' | ') + '\n'
        }
        explainResult.value = output
      } else {
        explainResult.value = res.message || 'EXPLAIN 执行失败'
      }
    }
  } catch (e: any) {
    explainResult.value = '执行失败: ' + e.message
  } finally {
    running.value = false
  }
}

function copyExplainResult() {
  if (explainResult.value) {
    navigator.clipboard.writeText(explainResult.value)
    message.success('已复制到剪贴板')
  }
}

// ── 列排序 ──
function moveColumnLeft(colName: string) {
  const cols = activeResult.value?.data?.columns
  if (!cols) return
  const idx = columnOrder.value.indexOf(colName)
  if (columnOrder.value.length === 0) {
    columnOrder.value = [...cols]
  }
  const curIdx = columnOrder.value.indexOf(colName)
  if (curIdx > 0) {
    const arr = [...columnOrder.value]
    ;[arr[curIdx - 1], arr[curIdx]] = [arr[curIdx], arr[curIdx - 1]]
    columnOrder.value = arr
  }
  colCtxMenu.value.visible = false
}

function moveColumnRight(colName: string) {
  const cols = activeResult.value?.data?.columns
  if (!cols) return
  if (columnOrder.value.length === 0) {
    columnOrder.value = [...cols]
  }
  const curIdx = columnOrder.value.indexOf(colName)
  if (curIdx >= 0 && curIdx < columnOrder.value.length - 1) {
    const arr = [...columnOrder.value]
    ;[arr[curIdx], arr[curIdx + 1]] = [arr[curIdx + 1], arr[curIdx]]
    columnOrder.value = arr
  }
  colCtxMenu.value.visible = false
}

function resetColumnOrder() {
  columnOrder.value = []
  colCtxMenu.value.visible = false
}

// 点击文档关闭列右键菜单
function onDocClickColMenu() {
  if (colCtxMenu.value.visible) colCtxMenu.value.visible = false
}
onMounted(() => document.addEventListener('click', onDocClickColMenu))
onUnmounted(() => document.removeEventListener('click', onDocClickColMenu))

// ── 批量操作 ──
const batchOptions = [
  { label: '批量设置值', key: 'set' },
  { label: '批量删除行', key: 'delete' },
  { label: '取消选择', key: 'clear' },
]

async function handleBatchAction(key: string) {
  if (key === 'clear') {
    checkedRowKeys.value = []
    return
  }

  if (!props.connId) {
    message.warning('连接不存在')
    return
  }

  const tableName = guessTableName(sqlText.value)
  if (!tableName) {
    message.warning('无法确定表名，请使用 SELECT 语句')
    return
  }

  if (key === 'delete') {
    const rows = checkedRowKeys.value.map((k: string | number) => Number(k))
    const pkCol = activeResult.value?.data?.columns[0] || 'id'
    const ids = rows.map((r: number) => {
      const rowIdx = r - (page.value - 1) * pageSize.value
      const row = allRows.value[rowIdx as number]
      return row ? (row as any)[pkCol as string] : undefined
    }).filter(Boolean)

    if (ids.length === 0) {
      message.warning('无法获取主键值')
      return
    }

    // 逐行删除
    const deleteSqls = ids.map(id => ({ sql: `DELETE FROM ${tableName} WHERE ${pkCol} = ?`, params: [id] }))
    try {
      const res: any = await api.executeBatch(props.connId, deleteSqls, props.dbName || undefined)
      if (res.success) {
        message.success(`已删除 ${ids.length} 行`)
        checkedRowKeys.value = []
        await runQuery()
      } else {
        message.error(res.message || '删除失败')
      }
    } catch (e: any) {
      message.error('删除失败: ' + e.message)
    }
  }

  if (key === 'set') {
    const col = activeResult.value?.data?.columns[0]
    if (!col) return
    const newVal = prompt(`请输入要设置的统一值（将设置到选中的 ${checkedRowKeys.value.length} 行的 ${col} 列）:`)
    if (newVal === null) return

    const rows = checkedRowKeys.value.map(k => Number(k))
    const pkCol = activeResult.value?.data?.columns[0] || 'id'
    const ids = rows.map((r: number) => {
      const rowIdx = r - (page.value - 1) * pageSize.value
      const row = allRows.value[rowIdx]
      return row ? (row as any)[pkCol as string] : undefined
    }).filter(Boolean)

    if (ids.length === 0) {
      message.warning('无法获取主键值')
      return
    }

    // 逐行更新
    const updateSqls = ids.map((id: any) => ({ sql: `UPDATE ${tableName} SET ${col} = ? WHERE ${pkCol} = ?`, params: [newVal, id] }))
    try {
      const res: any = await api.executeBatch(props.connId, updateSqls, props.dbName || undefined)
      if (res.success) {
        message.success(`已更新 ${ids.length} 行`)
        checkedRowKeys.value = []
        await runQuery()
      } else {
        message.error(res.message || '更新失败')
      }
    } catch (e: any) {
      message.error('更新失败: ' + e.message)
    }
  }
}

function startEdit(rowIdx: number, colIdx: number) {
  const row = allRows.value[rowIdx]
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
  const row = allRows.value[rowIdx]
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

  const cols = activeResult.value?.data?.columns
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
    const relRow = absRow - (page.value - 1) * pageSize.value
    const rowData = allRows.value[relRow]
    if (!rowData) continue

    // ── 新行 → 生成 INSERT ──
    if (_newRowAbsIndices.has(absRow)) {
      const insertCols: string[] = []
      const insertParams: any[] = []
      for (let ci = 0; ci < cols.length; ci++) {
        const newVal = modCols.get(ci)
        // 跳过空字符串（用户未编辑的列）
        if (newVal !== undefined && newVal !== '') {
          insertCols.push(`\`${cols[ci]}\``)
          insertParams.push(newVal)
        }
      }
      if (insertCols.length === 0) continue

      const placeholders = insertCols.map(() => '%s').join(', ')
      const database = props.dbName ? `\`${props.dbName}\`.` : ''
      const sql = `INSERT INTO ${database}\`${tableName}\` (${insertCols.join(', ')}) VALUES (${placeholders});`
      sqls.push({ sql, params: insertParams })
      continue
    }

    // ── 已有行 → 生成 UPDATE ──
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
        const relRow = absRow - (page.value - 1) * pageSize.value
        const rowData = allRows.value[relRow]
        if (rowData) {
          for (const [ci, newVal] of modCols) {
            rowData[ci] = newVal
          }
        }
        // INSERT 成功后移除新行标记
        _newRowAbsIndices.delete(absRow)
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
  if (!activeResult.value?.data || allRows.value.length === 0) {
    message.warning('没有可导出的数据')
    return
  }
  exporting.value = true
  try {
    const cols = activeResult.value.data.columns
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
        <span class="toolbar-title">SQL 查询 <span class="shortcut-hint">Ctrl+Enter</span>
          <n-tag v-if="draftRestored" size="tiny" type="warning" style="margin-left: 6px;">已恢复草稿</n-tag>
        </span>
        <n-space size="small">
          <n-tag v-if="props.dbName" type="info" size="small">{{ props.dbName }}</n-tag>

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
          <n-button size="tiny" @click="formatSql" title="格式化 SQL (Ctrl+Shift+F)">
            ♨ 格式化
          </n-button>
          <n-button size="tiny" @click="runExplain" title="执行 EXPLAIN 分析查询计划">
            📊 EXPLAIN
          </n-button>
          <n-button size="tiny" @click="showHistoryPanel = !showHistoryPanel" :type="showHistoryPanel ? 'info' : 'default'">
            📜 历史
          </n-button>
          <n-button size="tiny" @click="showSnippetPanel = !showSnippetPanel; if (showSnippetPanel) snippetPanelRef?.setCurrentSql(sqlText)" :type="showSnippetPanel ? 'info' : 'default'">
            📋 片段
          </n-button>
        </n-space>
      </div>

      <div class="editor-body" style="position: relative;">
        <div
          class="editor-sql-area"
          :class="{ 'drag-over': isDragOver }"
          @dragover.prevent="isDragOver = true"
          @dragleave="isDragOver = false"
          @drop.prevent="onDrop"
        >
          <SqlEditor
            ref="sqlEditorRef"
            v-model:modelValue="sqlText"
            :connId="props.connId"
            :dbName="props.dbName"
            @execute="runQuery"
          />
        </div>
        <!-- 历史面板 -->
        <div v-if="showHistoryPanel" class="history-panel">
          <div class="history-header">
            <span>查询历史</span>
            <n-space size="small">
              <n-input v-model:value="historySearch" placeholder="搜索历史..." clearable size="tiny" style="width: 150px" />
              <n-button size="tiny" quaternary @click="clearHistory">清除</n-button>
              <n-button size="tiny" quaternary @click="showHistoryPanel = false">✕</n-button>
            </n-space>
          </div>
          <div class="history-body">
            <!-- 收藏列表 -->
            <div v-if="favQueries.length" class="history-section">
              <div class="history-section-title">📌 收藏</div>
              <div v-for="(item, i) in favQueries" :key="'fav' + i" class="history-item" @click="selectFromFav(item)">
                <div class="history-item-name">{{ item.name }}</div>
                <n-button size="tiny" quaternary type="error" @click.stop="deleteFav(item)">✕</n-button>
              </div>
            </div>
            <!-- 历史列表 -->
            <div v-for="(items, date) in groupedHistory" :key="date" class="history-section">
              <div class="history-section-title">{{ date }}</div>
              <div v-for="(item, i) in items" :key="i" class="history-item" @click="selectFromHistory(item)">
                <div class="history-item-time">{{ item.time.split(' ')[1] || '' }}</div>
                <div class="history-item-sql">{{ item.sql.slice(0, 80) }}</div>
                <n-button size="tiny" quaternary @click.stop="toggleFav(item)">
                  {{ isFav(item) ? '★' : '☆' }}
                </n-button>
              </div>
            </div>
            <n-empty v-if="filteredHistory.length === 0 && favQueries.length === 0" description="暂无历史记录" />
          </div>
        </div>
        <!-- 片段面板 -->
        <SnippetPanel
          ref="snippetPanelRef"
          :visible="showSnippetPanel"
          @close="showSnippetPanel = false"
          @select="insertSnippet"
        />
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
    <div class="result-panel" v-if="activeResult?.data?.columns?.length">
      <div class="result-toolbar">
        <span class="toolbar-title">
          查询结果
          <n-tag v-if="results.length > 0 && activeResultIndex >= 0" size="tiny" :type="activeResult?.data?.is_query ? 'success' : 'warning'">
            <template v-if="activeResult?.data?.is_query">
              {{ activeResult?.data?.total_count ?? allRows.length }} 行
            </template>
            <template v-else>
              {{ activeResult?.data?.affected }} 行受影响
            </template>
          </n-tag>
          <!-- 结果选项卡 -->
          <n-space v-if="results.length > 1" size="small" style="margin-left: 12px;">
            <n-button
              v-for="(r, idx) in results"
              :key="r.id"
              size="tiny"
              :type="idx === activeResultIndex ? 'primary' : 'default'"
              @click="switchResult(idx)"
            >
              #{{ idx + 1 }}
              <span style="margin: 0 2px; max-width: 60px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block;">{{ r.sql.slice(0, 20) }}{{ r.sql.length > 20 ? '...' : '' }}</span>
              <n-button size="tiny" quaternary type="error" @click.stop="closeResult(idx)" style="padding: 0 2px; min-width: 0;">✕</n-button>
            </n-button>
          </n-space>
        </span>
        <n-space size="small">
          <!-- 筛选输入 -->
          <n-input
            v-model:value="filterText"
            placeholder="筛选数据..."
            clearable
            size="tiny"
            style="width: 150px"
          />
          <n-tag v-if="filterText && filteredRows.length !== mappedRows.length" size="tiny" type="info">
            {{ filteredRows.length }} / {{ mappedRows.length }}
          </n-tag>
          <!-- 已选行数 -->
          <n-tag v-if="checkedRowKeys.length > 0" size="tiny" type="success">
            已选 {{ checkedRowKeys.length }} 行
          </n-tag>
          <!-- 新增行按钮 -->
          <n-button
            v-if="activeResult?.data?.is_query"
            size="tiny"
            @click="addEmptyRow"
            title="在结果底部添加一行空数据"
          >
            ➕ 新增行
          </n-button>
          <!-- 删除行按钮 -->
          <n-button
            v-if="checkedRowKeys.length > 0"
            size="tiny"
            type="error"
            :loading="deleting"
            @click="deleteSelectedRows"
          >
            🗑️ 删除行
          </n-button>
          <!-- 批量操作 -->
          <n-dropdown
            v-if="checkedRowKeys.length > 0"
            :options="batchOptions"
            @select="handleBatchAction"
          >
            <n-button size="tiny">批量操作 ▾</n-button>
          </n-dropdown>
          <n-tag v-if="queryTime > 0" size="tiny" type="info">{{ queryTime }}ms</n-tag>
          <n-button
            v-if="modifiedCount > 0"
            size="tiny"
            type="warning"
            :loading="saving"
            @click="saveEdits"
          >
            💾 保存 ({{ modifiedCount + (hasNewRows ? 1 : 0) }})
            <template v-if="hasNewRows">(含{{ _newRowAbsIndices.size }}新行)</template>
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
            :data="filteredRows"
            :max-height="tableMaxHeight"
            virtual-scroll
            :row-height="28"
            :row-key="(row: Record<string, any>, idx: number) => (page - 1) * pageSize + idx"
            :checked-row-keys="checkedRowKeys"
            @update:checked-row-keys="(keys: (string | number)[]) => checkedRowKeys = keys"
          />
        </div>
        <button
          class="scroll-btn scroll-btn-right"
          :class="{ visible: canScrollRight }"
          @click="scrollRightStep"
          title="向右滚动"
        >›</button>
      </div>

      <!-- 列右键菜单 -->
      <teleport to="body">
        <div
          v-if="colCtxMenu.visible"
          class="column-context-menu"
          :style="{ left: colCtxMenu.x + 'px', top: colCtxMenu.y + 'px' }"
          @click.stop
        >
          <div class="ctx-item" @click="moveColumnLeft(colCtxMenu.col)">← 向左移动</div>
          <div class="ctx-item" @click="moveColumnRight(colCtxMenu.col)">→ 向右移动</div>
          <div class="ctx-sep"></div>
          <div class="ctx-item" @click="resetColumnOrder">↺ 重置列顺序</div>
        </div>
      </teleport>

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
              { label: '2000 条', value: 2000 },
              { label: '5000 条', value: 5000 },
            ]"
            size="tiny"
            style="width: 110px"
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

    <!-- EXPLAIN 结果面板 -->
    <n-modal v-model:show="showExplain" title="EXPLAIN 执行计划" preset="card" style="width: 900px; max-height: 85vh;" :mask-closable="true">
      <n-tabs v-model:value="explainTab" type="line" size="small">
        <n-tab-pane name="tree" tab="🌳 执行树">
          <n-spin :show="running">
            <div v-if="explainTreeData.length > 0" style="max-height: 500px; overflow: auto; padding: 8px 0;">
              <n-tree
                :data="explainTreeData"
                :default-expanded-keys="['root']"
                block-line
                :render-label="renderExplainNode"
                style="font-size: 13px;"
              />
            </div>
            <n-empty v-else-if="!running" description="无法解析为树形结构，请切换到其他视图" />
          </n-spin>
        </n-tab-pane>
        <n-tab-pane name="table" tab="📊 表格视图">
          <n-spin :show="running">
            <n-data-table
              v-if="explainTableData.length > 0"
              :columns="explainTableCols.map(col => ({ title: col, key: col, ellipsis: true }))"
              :data="explainTableData"
              :bordered="true"
              striped
              :max-height="500"
              size="small"
            />
            <n-empty v-else-if="!running" description="暂无表格数据" />
          </n-spin>
        </n-tab-pane>
        <n-tab-pane name="raw" tab="📄 原始 JSON">
          <n-spin :show="running">
            <n-pre style="max-height: 500px; overflow: auto; background: #1e1e1e; padding: 12px; border-radius: 4px; font-size: 12px;">
              {{ explainResult || (running ? '正在执行...' : '暂无数据') }}
            </n-pre>
          </n-spin>
        </n-tab-pane>
      </n-tabs>
      <template #footer>
        <n-space justify="end">
          <n-button @click="copyExplainResult">复制结果</n-button>
          <n-button type="primary" @click="showExplain = false">关闭</n-button>
        </n-space>
      </template>
    </n-modal>

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

.editor-sql-area.drag-over {
  outline: 2px dashed var(--color-primary);
  outline-offset: -2px;
  background: var(--bg-hover);
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

/* ── 历史面板 ── */
.history-panel {
  position: absolute;
  right: 0;
  top: 0;
  width: 380px;
  height: 100%;
  background: var(--bg-sidebar);
  border-left: 1px solid var(--color-border, #3c3c3c);
  z-index: 10;
  display: flex;
  flex-direction: column;
}
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border, #3c3c3c);
  font-size: 13px;
  font-weight: bold;
  flex-shrink: 0;
}
.history-body {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.history-section {
  margin-bottom: 4px;
}
.history-section-title {
  padding: 4px 10px;
  font-size: 11px;
  color: #888;
  text-transform: uppercase;
}
.history-item {
  display: flex;
  align-items: center;
  padding: 4px 10px;
  cursor: pointer;
  gap: 6px;
  font-size: 12px;
}
.history-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.history-item-time {
  color: #666;
  font-size: 11px;
  width: 40px;
  flex-shrink: 0;
}
.history-item-sql {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #ccc;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 11px;
}
.history-item-name {
  flex: 1;
  color: #e0e0e0;
  font-size: 12px;
}

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