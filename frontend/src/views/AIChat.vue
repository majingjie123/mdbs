<template>
  <div class="ai-chat-container">
    <!-- 多会话 Tab 栏 -->
    <div class="session-tabs">
      <div v-for="sess in sessions" :key="sess.id" class="session-tab"
        :class="{ active: sess.id === activeSessionId }"
        @click="switchSession(sess.id)">
        <span class="session-name">{{ sess.name }}</span>
        <span v-if="sessions.length > 1" class="session-close" @click.stop="closeSession(sess.id)">&times;</span>
      </div>
      <div class="session-add" @click="addSession" title="新建会话">+</div>
      <div class="ctx-cache-badge" v-if="cachedContextInfo" title="已从本地缓存恢复表结构上下文">💾 {{ cachedContextInfo }}</div>
    </div>

    <!-- 主区域：左 SQL + 右 AI -->
    <div class="main-area" ref="mainAreaRef">
      <!-- ============ 左侧 SQL 工作区 ============ -->
      <div class="sql-panel" :style="{ width: leftRatio + '%' }">
        <!-- SQL 编辑器 -->
        <div class="editor-panel" :style="{ height: sqlSplitRatio + '%' }">
          <div class="editor-toolbar">
            <span class="toolbar-title">SQL 编辑器</span>
            <div class="toolbar-actions">
              <n-button size="tiny" quaternary @click="clearSql" :disabled="!sqlText.trim()">清空</n-button>
              <n-button size="tiny" quaternary @click="formatSql">格式化</n-button>
            </div>
          </div>
          <div class="editor-body">
            <SqlEditor
              v-model:modelValue="sqlText"
              :connId="props.connId ?? undefined"
              :dbName="props.dbName"
              @execute="runQuery"
            />
          </div>
        </div>

        <!-- 垂直分割条 -->
        <div class="split-bar" @mousedown.prevent="onSqlSplitMouseDown"></div>

        <!-- 查询结果 -->
        <div class="result-panel" :style="{ height: (100 - sqlSplitRatio) + '%' }">
          <div class="result-toolbar">
            <span class="toolbar-title">查询结果</span>
            <div class="toolbar-actions">
              <n-button size="tiny" type="primary" :loading="running" @click="runQuery">▶ 执行</n-button>
              <n-button size="tiny" quaternary @click="clearResult" :disabled="!result">清空</n-button>
              <span v-if="result && allRows.length" style="color:var(--color-text-muted);font-size:12px;margin-left:4px">{{ totalRows }} 行{{ queryTime ? ` (${queryTime}ms)` : '' }}</span>
            </div>
          </div>
          <div class="result-body">
            <n-spin :show="running">
              <div v-if="!result" class="result-empty">输入 SQL 并点击执行</div>
              <div v-else-if="result.error" class="result-error">{{ result.error }}</div>
              <div v-else-if="!result.is_query && result.affected !== undefined" class="result-affected">影响行数: {{ result.affected }}</div>
              <template v-else-if="result.columns && result.columns.length">
                <div class="result-table-wrap">
                  <n-data-table
                    :columns="tableColumns"
                    :data="displayRows"
                    :max-height="'100%'"
                    :bordered="true"
                    :single-line="false"
                    size="small"
                    striped
                  />
                </div>
                <div class="result-pagination" v-if="totalPages > 1">
                  <n-pagination
                    v-model:page="page"
                    :page-count="totalPages"
                    :page-size="pageSize"
                    :simple="true"
                  />
                </div>
              </template>
              <div v-else class="result-empty">无结果</div>
            </n-spin>
          </div>
        </div>
      </div>

      <!-- 水平分割条 -->
      <div class="vsplit-bar" @mousedown.prevent="onVSplitMouseDown"></div>

      <!-- ============ 右侧 AI 对话区 ============ -->
      <div class="ai-panel" :style="{ width: (100 - leftRatio) + '%' }">
        <!-- 顶栏 -->
        <div class="bar">
          <div class="bar-left">
            <n-select v-model:value="activeConfigId" :options="configOptions" placeholder="AI 配置" style="width:150px" clearable size="small" />
            <n-button size="tiny" @click="openTableSelect" :loading="contextLoading" :disabled="!connId">加载上下文</n-button>
            <span v-if="contextText" class="ctx-dot active" title="已加载上下文"></span>
            <span v-else class="ctx-dot" title="无上下文"></span>
            <n-tag v-if="contextInfo" size="tiny" type="info" style="max-width:150px;overflow:hidden;text-overflow:ellipsis">{{ contextInfo }}</n-tag>
            <n-button v-if="contextText" size="tiny" quaternary @click="showContext=!showContext">预览</n-button>
            <n-button v-if="contextText" size="tiny" quaternary @click="clearContext">✕ 清除</n-button>
          </div>
          <div class="bar-right">
            <n-button size="tiny" quaternary @click="saveChat" :disabled="!messages.length">保存</n-button>
            <n-button size="tiny" quaternary @click="loadHistory">历史</n-button>
            <n-button size="tiny" quaternary @click="showExport=true" :disabled="!messages.length">导出</n-button>
            <n-button size="tiny" quaternary @click="clearChat" :disabled="!messages.length">清空</n-button>
          </div>
        </div>

        <!-- 消息区 -->
        <div ref="msgArea" class="msgs" @scroll="onScrollMsg">
          <!-- 欢迎 -->
          <div v-if="!messages.length" class="welcome">
            <h2>AI 助手</h2>
            <p v-if="!props.connId">选择 AI 配置 → 选择连接并加载上下文 → 开始对话</p>
            <p v-else-if="contextInfo">当前上下文：<strong style="color:var(--color-accent)">{{ contextInfo }}</strong></p>
            <p v-else-if="props.connName"><strong>{{ props.connName }}</strong> 已连接。选择表并加载上下文后开始对话。</p>
            <p v-else>已连接数据库。选择表并加载上下文后开始对话。</p>
            <div class="prompts">
              <n-button size="tiny" secondary @click="useTmpl('列出当前数据库所有表')">列出所有表</n-button>
              <n-button size="tiny" secondary @click="useTmpl('分析这个数据库的设计')">分析架构</n-button>
              <n-button size="tiny" secondary @click="useTmpl('解释外键关系')">外键关系</n-button>
              <n-button size="tiny" secondary @click="useTmpl('生成多表 JOIN')">JOIN 示例</n-button>
            </div>
          </div>

          <div v-for="(m,i) in messages" :key="i" :class="['msg', m.role==='user'?'u':'a']">
            <n-avatar :size="24" :color="m.role==='user'?'var(--color-accent)':'var(--color-success)'">{{ m.role==='user'?'U':'AI' }}</n-avatar>
            <div class="msg-body">
              <div class="msg-name">{{ m.role==='user'?'你':'AI 助手' }}</div>
              <div v-if="m.role==='system'" class="sys-text">{{ m.content }}</div>
              <template v-else-if="m.role==='user'">
                <div v-if="editMsgIdx===i" class="edit-msg-wrap">
                  <n-input v-model:value="editMsgText" type="textarea" :rows="2" :autosize="{minRows:2,maxRows:4}" />
                  <div class="edit-msg-actions">
                    <n-button size="tiny" @click="cancelEditMsg">取消</n-button>
                    <n-button size="tiny" type="primary" @click="confirmEditMsg(i)">确认修改</n-button>
                  </div>
                </div>
                <div v-else class="msg-text user-msg" v-html="renderMD(m.content)" @dblclick="editUserMsg(i)"></div>
              </template>
              <div v-else-if="m.role==='assistant' && !m.content && streaming && i===messages.length-1" class="msg-text loading-text">
                <span class="loading-dot" v-for="n in loadingDots" :key="n">.</span>
              </div>
              <div v-else class="msg-text" v-html="renderMD(m.content)"></div>
            </div>
            <div v-if="m.role!=='system' && editMsgIdx!==i" class="msg-act" @click.stop>
              <span @click="copyMsg(m.content)" title="复制">📋</span>
              <span v-if="m.role==='user'" @click="editUserMsg(i)" title="编辑">✏️</span>
              <span v-if="m.role==='assistant' && i===messages.length-1 && !streaming" @click="regrow" title="重新生成">🔄</span>
              <span @click="delMsg(i)" title="删除">🗑️</span>
            </div>
          </div>

          <n-alert v-if="errMsg" type="error" closable @close="errMsg=''" style="margin:8px 0">{{ errMsg }}</n-alert>
          <div v-if="showScrollBtn" class="scroll-btn" @click="scrollDown">↓</div>
        </div>

        <!-- 输入 -->
        <div class="input-area">
          <div class="quick-row">
            <n-button size="tiny" quaternary @click="openTableSelect" :disabled="!connId || streaming">📋 加载表结构</n-button>
            <n-button v-if="contextText" size="tiny" quaternary @click="clearContext" :disabled="streaming">🧹 清空上下文</n-button>
          </div>
          <div class="input-wrapper">
            <n-input v-model:value="input" type="textarea" :rows="2" :autosize="{minRows:2,maxRows:4}"
              placeholder="输入消息，Enter 发送，Shift+Enter 换行..." :disabled="streaming"
              @keydown="onKey" />
            <div class="send-btn-wrap" :class="{ streaming }" @click="streaming?stop():send()" :title="streaming?'停止':'发送'">
              <svg v-if="!streaming" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="5" height="12"/><rect x="13" y="6" width="5" height="12"/>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 上下文预览 -->
    <n-modal v-model:show="showContext" title="数据库上下文" preset="card" style="width:600px">
      <pre style="white-space:pre-wrap;max-height:350px;overflow:auto;font-size:12px;color:var(--color-text);background:var(--bg-app);padding:8px;border-radius:4px">{{ contextText }}</pre>
    </n-modal>

    <!-- 表选择对话框 -->
    <n-modal v-model:show="showTableSelect"
      title="选择表结构" preset="card" style="width:500px"
      mask-closable>
      <template #header>
        <span style="font-size:14px">选择要加载结构的数据表</span>
      </template>
      <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px">
        <n-input v-model:value="tableFilter" placeholder="搜索表名…" clearable size="small" style="flex:1" />
        <span style="color:var(--color-text-muted);font-size:12px;white-space:nowrap">{{ filteredTableList.length }} / {{ tableList.length }} 张表，已选 {{ tableList.filter(t=>t.checked).length }} 张</span>
        <n-space>
          <n-button size="tiny" @click="selectAllTables">全选</n-button>
          <n-button size="tiny" @click="deselectAllTables">取消全选</n-button>
        </n-space>
      </div>
      <n-spin :show="tableLoading">
        <div style="max-height:280px;overflow-y:auto;border:1px solid var(--color-border);border-radius:4px;padding:4px 0">
          <div v-for="t in filteredTableList" :key="t.name" style="display:flex;align-items:center;padding:5px 8px;cursor:pointer;border-bottom:1px solid var(--color-border)"
            :style="{background:t.checked?'rgba(32,128,240,0.1)':'transparent'}"
            @click="t.checked=!t.checked">
            <n-checkbox :checked="t.checked" style="margin-right:6px" />
            <span style="font-size:13px;color:var(--color-text)">{{ t.name }}</span>
            <span v-if="t.comment" style="margin-left:6px;font-size:11px;color:var(--color-text-muted)">— {{ t.comment }}</span>
          </div>
          <div v-if="!tableLoading && tableList.length===0" style="padding:20px;text-align:center;color:var(--color-text-muted)">该数据库无表</div>
        </div>
      </n-spin>
      <template #footer>
        <n-space justify="space-between">
          <n-button size="small" @click="showTableSelect=false">取消</n-button>
          <n-button size="small" type="primary" :loading="contextLoading" @click="confirmBuildContext">
            确认导入 ({{ tableList.filter(t=>t.checked).length }} 张表)
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 导出 -->
    <n-modal v-model:show="showExport" title="导出对话" preset="card" style="width:360px">
      <n-space vertical>
        <n-button @click="doExport('markdown')">导出 Markdown</n-button>
        <n-button @click="doExport('text')">导出纯文本</n-button>
      </n-space>
    </n-modal>

    <!-- 历史 -->
    <n-modal v-model:show="showHistory" title="聊天历史" preset="card" style="width:600px">
      <n-data-table :columns="histCols" :data="histList" :loading="histLoading" striped @row-click="loadHist" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed, onUnmounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api, ExecResult } from '../api'
import { useAppStore } from '../stores/app'
import SqlEditor from '../components/SqlEditor.vue'

const props = withDefaults(defineProps<{
  connId?: number | null; db?: string; dbName?: string; schemaName?: string; tableName?: string; nodeType?: string; connName?: string;
  _sessionTables?: string[]; _sessionViews?: string[]
}>(), { connId: null, db: '', dbName: '', schemaName: '', tableName: '', nodeType: '', connName: '', _sessionTables: () => [], _sessionViews: () => [] })

const msg = useMessage(), dialog = useDialog(), store = useAppStore()

// ════════════════════════════════════════
// SQL 工作区
// ════════════════════════════════════════
const sqlText = ref('SELECT 1')
const result = ref<ExecResult | null>(null)
const running = ref(false)
const queryTime = ref(0)
const abortController = ref<AbortController | null>(null)

// 可拖拽分屏：SQL 编辑器高度百分比
const sqlSplitRatio = ref(40)
const sqlDragging = ref(false)

function onSqlSplitMouseDown(e: MouseEvent) {
  sqlDragging.value = true; e.preventDefault()
}
function onSqlSplitMouseMove(e: MouseEvent) {
  if (!sqlDragging.value) return
  const container = document.querySelector('.sql-panel') as HTMLElement
  if (!container) return
  const rect = container.getBoundingClientRect()
  const y = e.clientY - rect.top
  sqlSplitRatio.value = Math.max(15, Math.min(75, (y / rect.height) * 100))
}
function onSqlSplitMouseUp() { sqlDragging.value = false }
onMounted(() => {
  document.addEventListener('mousemove', onSqlSplitMouseMove)
  document.addEventListener('mouseup', onSqlSplitMouseUp)
})
onUnmounted(() => {
  document.removeEventListener('mousemove', onSqlSplitMouseMove)
  document.removeEventListener('mouseup', onSqlSplitMouseUp)
})

// 水平分屏：左 SQL / 右 AI 比例
const leftRatio = ref(50)
const vsplitDragging = ref(false)
const mainAreaRef = ref<HTMLElement | null>(null)

function onVSplitMouseDown(e: MouseEvent) {
  vsplitDragging.value = true; e.preventDefault()
}
function onVSplitMouseMove(e: MouseEvent) {
  if (!vsplitDragging.value) return
  const el = mainAreaRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const x = e.clientX - rect.left
  leftRatio.value = Math.max(20, Math.min(80, (x / rect.width) * 100))
}
function onVSplitMouseUp() { vsplitDragging.value = false }
onMounted(() => {
  document.addEventListener('mousemove', onVSplitMouseMove)
  document.addEventListener('mouseup', onVSplitMouseUp)
})
onUnmounted(() => {
  document.removeEventListener('mousemove', onVSplitMouseMove)
  document.removeEventListener('mouseup', onVSplitMouseUp)
})

// ── SQL 执行 ──
const page = ref(1)
const pageSize = ref(100)
const allRows = ref<any[][]>([])
const displayRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return allRows.value.slice(start, start + pageSize.value)
})
const totalPages = computed(() => Math.max(1, Math.ceil(allRows.value.length / pageSize.value)))
const totalRows = computed(() => allRows.value.length)

const tableColumns = computed(() => {
  if (!result.value?.columns) return []
  return result.value.columns.map((col: string) => ({
    title: col, key: col, width: 160, resizable: true,
    ellipsis: { tooltip: true },
    render: (row: any) => {
      const v = row[col]; return v === null || v === undefined ? '<span style="color:var(--color-text-muted)">NULL</span>' : String(v)
    }
  }))
})

async function runQuery() {
  if (!props.connId || !sqlText.value.trim()) { msg.warning('请输入 SQL 并选择连接'); return }
  running.value = true; result.value = null; page.value = 1; allRows.value = []
  const startTime = performance.now()
  abortController.value = new AbortController()
  try {
    const r: any = await api.executeSQL(props.connId, sqlText.value, props.db || props.dbName || undefined, props.schemaName || undefined, abortController.value.signal)
    queryTime.value = Math.round(performance.now() - startTime)
    if (r.success && r.data) {
      result.value = r.data
      allRows.value = r.data.rows || []
    } else {
      result.value = { columns: [], rows: [], is_query: false, affected: 0, error: r.message || '执行失败' }
    }
  } catch (e: any) {
    queryTime.value = Math.round(performance.now() - startTime)
    result.value = { columns: [], rows: [], is_query: false, affected: 0, error: e.message || '请求失败' }
  } finally { running.value = false; abortController.value = null }
}

function clearSql() { sqlText.value = ''; result.value = null; allRows.value = []; page.value = 1 }

function formatSql() {
  let s = sqlText.value.trim()
  if (!s) return
  const kw = /\b(SELECT|FROM|WHERE|AND|OR|ORDER BY|GROUP BY|HAVING|LIMIT|OFFSET|INSERT INTO|VALUES|UPDATE|SET|DELETE|CREATE|ALTER|DROP|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN|ON|UNION|ALL|INTO|LIKE|BETWEEN|EXISTS|NOT|IN|AS|DISTINCT|COUNT|SUM|AVG|MIN|MAX)\b/gi
  s = s.replace(kw, m => m.toUpperCase())
  const breakKw = /\b(WHERE|ORDER BY|GROUP BY|HAVING|LIMIT|OFFSET|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN|ON|UNION|AND|OR)\b/gi
  const parts: string[] = []; let last = 0; let match: RegExpExecArray | null
  while ((match = breakKw.exec(s)) !== null) {
    const pos = match.index
    if (pos > last) parts.push(s.slice(last, pos))
    const before = s.slice(0, pos)
    const quotes = (before.match(/'/g)||[]).length
    parts.push(quotes % 2 === 1 ? match[0] : '\n  ' + match[0])
    last = breakKw.lastIndex
  }
  if (last < s.length) parts.push(s.slice(last))
  sqlText.value = parts.join('').trim()
}

function clearResult() { result.value = null; allRows.value = []; page.value = 1 }

// ════════════════════════════════════════
// 表结构上下文缓存持久化
// ════════════════════════════════════════
const cachedContextInfo = ref('')

function getContextCacheKey(): string {
  return `ai_ctx_${props.connId}_${props.db || props.dbName || ''}`
}

function saveContextToCache() {
  if (!props.connId) return
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess || !sess.ctxText) return
  try {
    const key = getContextCacheKey()
    const data = { contextText: sess.ctxText, contextInfo: sess.ctxInfo, timestamp: Date.now() }
    localStorage.setItem(key, JSON.stringify(data))
  } catch {}
}

function loadContextFromCache(): boolean {
  if (!props.connId) return false
  try {
    const key = getContextCacheKey()
    const raw = localStorage.getItem(key)
    if (!raw) return false
    const data = JSON.parse(raw)
    if (!data.contextText) return false
    const sess = sessions.value.find(s=>s.id===activeSessionId.value)
    if (sess) { sess.ctxText = data.contextText; sess.ctxInfo = data.contextInfo }
    cachedContextInfo.value = data.contextInfo || ''
    return true
  } catch { return false }
}

// 表筛选
const tableFilter = ref('')
const filteredTableList = computed(() => {
  const q = tableFilter.value.trim().toLowerCase()
  if (!q) return tableList.value
  return tableList.value.filter(t =>
    t.name.toLowerCase().includes(q) ||
    (t.comment || '').toLowerCase().includes(q)
  )
})

// 用户消息编辑
const editMsgIdx = ref<number | null>(null)
const editMsgText = ref('')

// 会话管理
let sid = 0
const sessions = ref([{ id: ++sid, name: '会话 1', msgs: [] as {role:string;content:string}[], ctxText: '', ctxInfo: '', historyId: null as number|null }])
const activeSessionId = ref(1)
const activeSession = computed(() => sessions.value.find(s=>s.id===activeSessionId.value))
const messages = computed(() => activeSession.value?.msgs||[])
// 上下文（按会话隔离，通过 computed 从当前会话读取）
const contextText = computed(() => activeSession.value?.ctxText ?? '')
const contextInfo = computed(() => activeSession.value?.ctxInfo ?? '')

function switchSession(id: number) { activeSessionId.value = id }
function addSession() {
  sessions.value.push({ id: ++sid, name: `会话 ${sid}`, msgs: [], ctxText: '', ctxInfo: '', historyId: null })
  activeSessionId.value = sid
}
function closeSession(id: number) {
  if (sessions.value.length <= 1) return
  const idx = sessions.value.findIndex(s=>s.id===id)
  sessions.value.splice(idx, 1)
  activeSessionId.value = sessions.value[Math.min(idx, sessions.value.length-1)].id
}

// 配置
const configs = ref<any[]>([])
const activeConfigId = ref<number|null>(null)
const configOptions = ref<{label:string;value:number}[]>([])
async function loadConfigs() {
  try {
    const r:any = await api.aiListConfigs()
    if (r.success && r.data) {
      configs.value = r.data
      configOptions.value = r.data.map((c:any)=>({label:`${c.name} (${c.model})`,value:c.id}))
      if (!activeConfigId.value && r.data.length) {
        const d = r.data.find((c:any)=>c.is_default)
        activeConfigId.value = d ? d.id : r.data[0].id
      }
    }
  } catch {}
}

// 上下文 - 表选择对话框
const contextLoading = ref(false)
const showContext = ref(false)

// 表选择
const showTableSelect = ref(false)
const tableList = ref<{name:string;comment:string;checked:boolean}[]>([])
const tableLoading = ref(false)

// 点击"加载上下文"→先获取表列表，弹出选择对话框
async function openTableSelect() {
  if (!props.connId) { msg.warning('请先选择连接'); return }
  showTableSelect.value = true
  tableLoading.value = true
  try {
    const r:any = await api.listTables(props.connId, props.db||props.dbName||undefined, props.schemaName||undefined)
    if (r.success && Array.isArray(r.data)) {
      tableList.value = r.data.map((t:any) => ({
        name: t.name || t,
        comment: t.comment || '',
        checked: true,  // 默认全选
      }))
    } else {
      tableList.value = []
      msg.error(r.message||'获取表列表失败')
    }
  } catch (e:any) {
    msg.error('获取表列表失败: '+(e.message||''))
    tableList.value = []
  } finally {
    tableLoading.value = false
  }
}

function selectAllTables() { tableList.value.forEach(t => t.checked = true) }
function deselectAllTables() { tableList.value.forEach(t => t.checked = false) }

// 确认选择后，根据选中的表构建上下文
async function confirmBuildContext() {
  const selected = tableList.value.filter(t => t.checked).map(t => t.name)
  if (!selected.length) { msg.warning('请至少选择一张表'); return }
  showTableSelect.value = false
  contextLoading.value = true
  try {
    const r:any = await api.aiBuildContext({
      conn_id: props.connId,
      database: props.db||props.dbName||undefined,
      schema_name: props.schemaName||undefined,
      tables: selected,
    })
    if (r.success && r.data) {
      const sess = sessions.value.find(s=>s.id===activeSessionId.value)
      if (sess) { sess.ctxText = r.data.context; sess.ctxInfo = `${props.dbName||props.db||''} (${r.data.db_type}) - ${selected.length} 张表` }
      saveContextToCache()
      cachedContextInfo.value = ''
      const loadedCount = r.data.tables ?? 0
      if (loadedCount === 0) {
        msg.warning('未能查到任何表的字段信息，请检查数据库连接及表名是否正确')
      } else if (loadedCount < selected.length) {
        msg.warning(`仅成功加载 ${loadedCount}/${selected.length} 张表的结构，其余表可能不存在或无权限访问`)
      } else {
        msg.success(`已加载 ${loadedCount} 张表的结构`)
      }
    } else msg.error(r.message||'构建上下文失败')
  } catch (e:any) { msg.error('构建失败: '+(e.message||''))
  } finally { contextLoading.value = false }
}

function useTmpl(t: string) { input.value = t; nextTick(()=>send()) }

// 用户消息编辑
function editUserMsg(idx: number) {
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess || !sess.msgs[idx] || sess.msgs[idx].role !== 'user') return
  editMsgIdx.value = idx
  editMsgText.value = sess.msgs[idx].content
}
function confirmEditMsg(idx: number) {
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess || !sess.msgs[idx]) return
  sess.msgs[idx].content = editMsgText.value
  editMsgIdx.value = null
}
function cancelEditMsg() { editMsgIdx.value = null }

// 清空上下文
function clearContext() {
  dialog.warning({title:'清空上下文',content:'确定清空表结构上下文吗？清空后 AI 将不再参考表结构信息。',positiveText:'确定',
    onPositiveClick:()=>{
      const sess = sessions.value.find(s=>s.id===activeSessionId.value)
      if (sess) { sess.ctxText = ''; sess.ctxInfo = ''; sess.msgs.push({role:'system',content:'已清空表结构上下文'}) }
    }
  })
}

// 输入
const input = ref('')
const streaming = ref(false)
const abortCtrl = ref<AbortController|null>(null)
const errMsg = ref('')
const msgArea = ref<HTMLElement|null>(null)
const showScrollBtn = ref(false)

// 加载等待点动画
const loadingDots = ref(0)
let loadingTimer: ReturnType<typeof setInterval> | null = null
function startLoadingDots() {
  loadingDots.value = 1
  loadingTimer = setInterval(() => {
    loadingDots.value = (loadingDots.value % 3) + 1
    // 如果流已经收到内容，停止动画
    const sess = sessions.value.find(s=>s.id===activeSessionId.value)
    const last = sess?.msgs?.[sess.msgs.length-1]
    if (last && last.content) stopLoadingDots()
  }, 500)
}
function stopLoadingDots() {
  if (loadingTimer) { clearInterval(loadingTimer); loadingTimer = null }
  loadingDots.value = 0
}

// 导出
const showExport = ref(false)

// 历史
const showHistory = ref(false)
const histList = ref<any[]>([])
const histLoading = ref(false)
const histCols = [
  { title:'ID', key:'id', width:50 },
  { title:'数据库', key:'db_name', width:100 },
  { title:'摘要', key:'context_summary', ellipsis:{tooltip:true} },
  { title:'时间', key:'updated_at', width:160 },
]

// ── 渲染 Markdown ──
function escapeHTML(s: string): string {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
}

function renderMD(text: string): string {
  if (!text) return ''
  let html = escapeHTML(text)
  // 代码块 ```lang ... ```
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const trimmed = code.trim()
    const langLabel = lang ? `<span class="code-lang">${lang}</span>` : ''
    return `<div class="code-wrap">${langLabel}<button class="code-copy" onclick="(function(b){var ta=document.createElement('textarea');ta.value=b;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove()})(this.parentElement.querySelector('code').textContent)">复制</button><pre class="code-block"><code>${escapeHTML(trimmed)}</code></pre></div>`
  })
  // 分割线 (前移，避免被其它规则误匹配)
  html = html.replace(/^---+\s*$/gm, '<hr/>')
  // 引用
  html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>')
  // 有序列表
  html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="ol">$1</li>')
  html = html.replace(/(<li class="ol">.*<\/li>\n?)+/g, '<ol>$&</ol>')
  // 无序列表
  html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
  // 标题
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
  // 表格
  html = html.replace(/\n\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)*)/g, (_, h, b) => {
    const heads = h.split('|').filter(Boolean).map((s:string)=>`<th>${s.trim()}</th>`).join('')
    const rows = b.trim().split('\n').map((r:string)=>`<tr>${r.split('|').filter(Boolean).map((c:string)=>`<td>${c.trim()}</td>`).join('')}</tr>`).join('')
    return `<table><thead><tr>${heads}</tr></thead><tbody>${rows}</tbody></table>`
  })
  // 行内格式 (顺序: 删除线 > 粗体 > 斜体 > 行内代码 > 链接)
  html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/`([^`]+)`/g, '<code class="ic">$1</code>')
  // 链接 [text](url) — 在转义后的文本中匹配，避免干扰之前的替换
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  // 段落
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br/>')
  return `<p>${html}</p>`
}

function scrollDown() {
  nextTick(() => { if (msgArea.value) msgArea.value.scrollTop = msgArea.value.scrollHeight })
}

function onScrollMsg() {
  if (!msgArea.value) return
  const el = msgArea.value
  showScrollBtn.value = el.scrollHeight - el.scrollTop - el.clientHeight > 80
}

// ── 发送 ──
async function send() {
  const text = input.value.trim()
  if (!text || streaming.value) return
  if (!activeConfigId.value) { msg.warning('请选择 AI 配置'); return }

  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess) return

  sess.msgs.push({ role:'user', content: text })
  input.value = ''
  errMsg.value = ''
  scrollDown()

  sess.msgs.push({ role:'assistant', content: '' })
  streaming.value = true
  startLoadingDots()

  const msgs: {role:string;content:string}[] = []
  if (contextText.value) {
    msgs.push({ role:'system', content: `你是数据库助手。当前数据库结构：\n\n${contextText.value}\n\n根据结构回答。` })
  }
  for (const m of sess.msgs.slice(0,-1)) msgs.push({ role: m.role, content: m.content })

  abortCtrl.value = new AbortController()
  try {
    const resp = await fetch('/api/ai/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ config_id: activeConfigId.value, messages: msgs }),
      signal: abortCtrl.value.signal,
    })
    if (!resp.ok) { const e=await resp.json().catch(()=>({message:'请求失败'})); throw new Error(e.message||e.detail||'请求失败') }

    // Bug 3 修复：检查响应类型，非 SSE 直接解析 JSON 错误
    if (!resp.headers.get('content-type')?.includes('text/event-stream')) {
      const json = await resp.json()
      throw new Error(json.message || '请求失败')
    }

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buf = '', full = '', idx = sess.msgs.length - 1
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, {stream:true})
      const lines = buf.split('\n'); buf = lines.pop()||''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') continue
        try {
          const parsed = JSON.parse(data)
          if (parsed.error) { errMsg.value = parsed.error; sess.msgs.pop(); streaming.value=false; stopLoadingDots(); return }
          if (parsed.content) { stopLoadingDots(); full += parsed.content; sess.msgs[idx] = {...sess.msgs[idx], content: full}; scrollDown() }
        } catch {}
      }
    }
    sess.msgs[idx] = {...sess.msgs[idx], content: full}
  } catch (e:any) {
    if (e.name==='AbortError') { sess.msgs.pop(); msg.info('已停止') }
    else { errMsg.value = e.message||'请求失败'; sess.msgs.pop() }
  } finally {
    streaming.value = false; abortCtrl.value = null; stopLoadingDots()
  }
}

function stop() { abortCtrl.value?.abort(); streaming.value = false }

function onKey(e: KeyboardEvent) {
  if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send() }
}

// 消息操作
function copyMsg(content: string) {
  navigator.clipboard.writeText(content).then(()=>msg.success('已复制')).catch(()=>msg.error('复制失败'))
}

function delMsg(idx: number) {
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (sess) sess.msgs.splice(idx, 1)
}

function regrow() {
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess || sess.msgs.length < 2) return
  // 删除最后一条 AI 最后一条，找到最后一条 user 消息
  let lastUserIdx = -1
  for (let i = sess.msgs.length - 1; i >= 0; i--) {
    if (sess.msgs[i].role === 'user') { lastUserIdx = i; break }
  }
  if (lastUserIdx === -1) return
  // 删除最后一条 assistant
  if (sess.msgs[sess.msgs.length-1].role === 'assistant') sess.msgs.pop()
  // 将 user 消息设为输入并发送
  input.value = sess.msgs[lastUserIdx].content
  // 删除该 user 消息及之后所有
  sess.msgs.splice(lastUserIdx)
  nextTick(() => send())
}

// 导出
function doExport(format: string) {
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess || !sess.msgs.length) return
  const lines: string[] = []
  if (format === 'markdown') {
    lines.push('# AI 对话记录', '', `**时间**: ${new Date().toLocaleString()}`, `**数据库**: ${contextInfo.value||'(无)'}`, '')
    for (const m of sess.msgs) {
      if (m.role === 'user') lines.push('## 用户', '', m.content, '')
      else if (m.role === 'assistant') lines.push('## AI 助手', '', m.content, '')
    }
  } else {
    lines.push(`AI 对话记录 - ${new Date().toLocaleString()}`, `数据库: ${contextInfo.value||'(无)'}`, '', '='.repeat(40), '')
    for (const m of sess.msgs) {
      lines.push(m.role === 'user' ? '[用户]' : '[AI 助手]', '', m.content, '', '-'.repeat(30), '')
    }
  }
  const blob = new Blob([lines.join('\n')], { type: format === 'markdown' ? 'text/markdown' : 'text/plain' })
  const filename = `ai-chat-${Date.now()}.${format==='markdown'?'md':'txt'}`

  // 在 pywebview 环境下使用原生保存对话框
  const pv = (window as any).pywebview
  if (pv?.api) {
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1]
      pv.api.save_file(filename, base64)
    }
    reader.readAsDataURL(blob)
    showExport.value = false
    msg.success('导出成功')
    return
  }

  // 浏览器环境退化方案
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
  showExport.value = false
  msg.success('导出成功')
}

// 保存
async function saveChat() {
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess || !sess.msgs.length) { msg.warning('没有消息'); return }
  try {
    // Bug 6 修复：摘要取第一条 user 消息而非第一条消息
    let summary = ''
    for (const m of sess.msgs) {
      if (m.role === 'user') { summary = m.content.slice(0, 100); break }
    }
    const r:any = await api.aiSaveHistory({
      id: sess.historyId || null,
      conn_id: props.connId||null, db_name: props.db||null,
      messages: sess.msgs, context_summary: summary,
      context_text: sess.ctxText,
    })
    if (r.success) {
      sess.historyId = r.data?.id ?? sess.historyId
      msg.success('已保存')
    }
    else msg.error(r.message||'保存失败')
  } catch(e:any) { msg.error('保存失败: '+(e.message||'')) }
}

async function loadHistory() {
  showHistory.value = true; histLoading.value = true
  try {
    const r:any = await api.aiListHistory()
    if (r.success) histList.value = r.data||[]
  } catch {} finally { histLoading.value = false }
}

async function loadHist(row: any) {
  editMsgIdx.value = null  // Bug 8：重置编辑状态
  try {
    const r:any = await api.aiGetHistory(row.id)
    if (r.success && r.data) {
      const ms = r.data.messages||[]
      if (Array.isArray(ms)) {
        const sess = sessions.value.find(s=>s.id===activeSessionId.value)
        if (sess) {
          sess.msgs = ms
          sess.historyId = row.id  // Bug 2：记录 historyId 以便后续按 id 更新
          sess.ctxText = r.data.context_text||''
          sess.ctxInfo = r.data.db_name||''
        }
      }
      showHistory.value = false; msg.success('已加载'); scrollDown()
    }
  } catch(e:any) { msg.error('加载失败') }
}

async function clearChat() {
  dialog.warning({title:'清空对话',content:'确定清空吗？',positiveText:'确定',
    onPositiveClick:()=>{
      const sess = sessions.value.find(s=>s.id===activeSessionId.value)
      if (sess) sess.msgs = []
    }
  })
}

// 根据 props 自动加载上下文
async function autoLoadContext() {
  if (!props.connId) return
  const database = props.db || props.dbName || ''

  // 从会话向导传入的表/视图列表
  if (props._sessionTables?.length || props._sessionViews?.length) {
    contextLoading.value = true
    try {
      const tables = [...(props._sessionTables || []), ...(props._sessionViews || [])]
      const r:any = await api.aiBuildContext({
        conn_id: props.connId,
        database: database || undefined,
        schema_name: props.schemaName || undefined,
        tables,
      })
      if (r.success && r.data) {
        const sess = sessions.value.find(s=>s.id===activeSessionId.value)
        if (sess) sess.ctxText = r.data.context
        const loadedCount = r.data.tables ?? 0
        if (sess) sess.ctxInfo = `${tables.length} 个对象 (${r.data.db_type})`
        if (loadedCount === 0) {
          msg.warning('未能查到任何表和视图的字段信息，请检查数据库连接及对象名是否正确')
          if (sess) sess.ctxInfo = ''
        } else {
          msg.success(`已加载 ${tables.length} 个对象的上下文`)
        }
      }
    } catch {} finally { contextLoading.value = false }
    return
  }

  // 来自数据库/连接节点 → 弹出选表对话框
  if (props.nodeType === 'database' || props.nodeType === 'connection' || !props.tableName) {
    await openTableSelect()
    return
  }

  // 来自表节点 → 自动加载该表结构
  if (props.tableName) {
    contextLoading.value = true
    try {
      const r:any = await api.aiBuildContext({
        conn_id: props.connId,
        database: database || undefined,
        schema_name: props.schemaName || undefined,
        tables: [props.tableName],
      })
      if (r.success && r.data) {
        const sess = sessions.value.find(s=>s.id===activeSessionId.value)
        if (sess) sess.ctxText = r.data.context
        const loadedCount = r.data.tables ?? 0
        if (sess) sess.ctxInfo = `${props.tableName} (${r.data.db_type}) - ${loadedCount} 张表`
        if (loadedCount === 0) {
          msg.warning(`未能查到表 "${props.tableName}" 的字段信息，请检查表名是否正确`)
          if (sess) sess.ctxInfo = ''
        } else {
          msg.success(`已加载表 "${props.tableName}" 的结构`)
        }
      }
    } catch {} finally { contextLoading.value = false }
  }
}

// 从侧边栏打开时自动检测上下文
onMounted(async () => {
  loadConfigs()
  if (props.connId) {
    // 先从本地缓存恢复表结构上下文
    const cached = loadContextFromCache()
    if (!cached) {
      await autoLoadContext()
    }
  }
})
</script>

<style scoped>
.ai-chat-container{display:flex;flex-direction:column;height:100%;background:var(--bg-app)}
.session-tabs{display:flex;background:var(--bg-sidebar);border-bottom:1px solid var(--color-border);min-height:30px;overflow-x:auto;flex-shrink:0}
.session-tab{display:flex;align-items:center;gap:4px;padding:5px 12px;font-size:12px;color:var(--color-text-muted);cursor:pointer;border-right:1px solid var(--color-border);white-space:nowrap;user-select:none}
.session-tab:hover{background:var(--bg-hover);color:var(--color-text-secondary)}
.session-tab.active{background:var(--bg-app);color:#fff;border-bottom:2px solid var(--color-accent)}
.session-close{display:flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:3px;font-size:10px;color:var(--color-text-muted);cursor:pointer}
.session-close:hover{background:var(--bg-hover);color:#fff}
.session-add{display:flex;align-items:center;padding:5px 12px;font-size:14px;color:var(--color-text-muted);cursor:pointer;user-select:none}
.session-add:hover{color:#fff}
.bar{display:flex;align-items:center;justify-content:space-between;padding:6px 12px;border-bottom:1px solid var(--color-border);background:var(--bg-sidebar);flex-shrink:0}
.bar-left,.bar-right{display:flex;align-items:center;gap:6px}
.msgs{flex:1;overflow-y:auto;padding:12px}
.welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--color-text-muted);text-align:center;gap:8px}
.welcome h2{margin:0;color:var(--color-text)}
.prompts{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;justify-content:center}
.msg{display:flex;gap:8px;margin-bottom:14px;position:relative}
.msg.u{flex-direction:row-reverse}
.msg-body{max-width:70%;padding:8px 12px;border-radius:8px;background:var(--bg-card)}
.msg.u .msg-body{background:var(--color-accent-user);color:#fff}
.msg-name{font-size:0.78em;color:var(--color-text-muted);margin-bottom:3px}
.msg.u .msg-name{color:rgba(255,255,255,0.8);text-align:right}
.msg-text{line-height:1.6;word-break:break-word;font-size:13px}
.msg-text :deep(p){margin:0 0 6px}
.msg-text :deep(p:last-child){margin-bottom:0}
.msg-text :deep(.code-wrap){position:relative;background:var(--bg-app);border:1px solid var(--color-border);border-radius:4px;margin:6px 0}
.msg-text :deep(.code-lang){position:absolute;top:2px;left:8px;font-size:11px;color:var(--color-text-muted);text-transform:uppercase}
.msg-text :deep(.code-copy){position:absolute;top:2px;right:4px;background:var(--bg-hover);border:none;color:var(--color-text-muted);cursor:pointer;padding:2px 8px;font-size:11px;border-radius:3px}
.msg-text :deep(.code-copy:hover){background:var(--bg-hover);color:#fff}
.msg-text :deep(.code-block){padding:22px 10px 8px;overflow-x:auto;font-size:0.9em;margin:0;color:var(--color-text-code)}
.msg-text :deep(code.ic){background:var(--bg-hover);padding:1px 5px;border-radius:3px;font-size:0.9em}
.msg-text :deep(h2),.msg-text :deep(h3),.msg-text :deep(h4){margin:10px 0 5px}
.msg-text :deep(ul){margin:4px 0;padding-left:18px}
.msg-text :deep(li){margin:2px 0}
.msg-text :deep(table){border-collapse:collapse;margin:6px 0;font-size:12px;width:100%}
.msg-text :deep(th),.msg-text :deep(td){border:1px solid var(--color-border);padding:4px 8px;text-align:left}
.msg-text :deep(th){background:var(--bg-hover);font-weight:600}
.msg-act{display:none;flex-direction:column;gap:4px;position:absolute;right:-2px;top:0;padding:2px}
.msg.u .msg-act{right:auto;left:-2px}
.msg:hover .msg-act{display:flex}
.msg-act span{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:4px;cursor:pointer;color:var(--color-text-muted);background:rgba(0,0,0,0.3)}
.msg-act span:hover{background:var(--bg-hover);color:#fff}
.scroll-btn{position:sticky;bottom:8px;left:50%;transform:translateX(-50%);width:32px;height:32px;border-radius:50%;background:var(--bg-hover);color:var(--color-text-secondary);display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:16px;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,0.3)}
.scroll-btn:hover{background:var(--bg-hover);color:#fff}
.input-area{padding:10px 12px;border-top:1px solid var(--color-border);background:var(--bg-sidebar);flex-shrink:0}
.quick-row{display:flex;gap:6px;margin-bottom:6px;flex-shrink:0}
.input-wrapper{display:flex;align-items:flex-start}
.sys-text{color:var(--color-text-muted);font-style:italic;font-size:0.9em}
.ctx-dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--bg-hover);flex-shrink:0}
.ctx-dot.active{background:#4caf50;box-shadow:0 0 4px rgba(76,175,80,0.5)}
.send-btn-wrap{display:flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;background:var(--color-accent);color:#fff;cursor:pointer;flex-shrink:0;margin-left:8px;align-self:flex-end;transition:background .2s}
.send-btn-wrap:hover{background:var(--color-accent)}
.send-btn-wrap.streaming{background:#e53935}
.send-btn-wrap.streaming:hover{background:#ef5350}
.edit-msg-wrap{border:1px solid var(--color-accent);border-radius:6px;padding:6px;background:rgba(0,120,212,0.08)}
.edit-msg-actions{display:flex;gap:6px;justify-content:flex-end;margin-top:6px}
.loading-text{font-size:1.5em;color:var(--color-text-muted);padding:4px 0;letter-spacing:3px}
.loading-dot{animation:blink 1s infinite}
.loading-dot:nth-child(2){animation-delay:0.2s}
.loading-dot:nth-child(3){animation-delay:0.4s}
@keyframes blink{0%,100%{opacity:0.3}50%{opacity:1}}
.msg-text :deep(hr){border:none;border-top:1px solid var(--color-border);margin:10px 0}
.msg-text :deep(blockquote){border-left:3px solid var(--bg-hover);padding:4px 12px;margin:6px 0;color:var(--color-text-muted);background:rgba(255,255,255,0.03)}
.msg-text :deep(ol){margin:4px 0;padding-left:20px}
.msg-text :deep(ol li){margin:2px 0}
.msg-text :deep(del){color:var(--color-text-muted)}
.msg-text :deep(em){color:var(--color-text-secondary)}
.msg-text :deep(a){color:var(--color-accent-alt);text-decoration:underline}
.msg-text :deep(a:hover){color:var(--color-accent-alt)}
.msg-text :deep(.user-msg){cursor:pointer}
.msg-text :deep(.user-msg:hover){opacity:0.85}
/* ════════════════════════════════════════
   三栏布局
   ════════════════════════════════════════ */
.main-area{display:flex;flex:1;overflow:hidden;min-height:0}
.sql-panel{display:flex;flex-direction:column;border-right:1px solid var(--color-border);overflow:hidden}
.ai-panel{display:flex;flex-direction:column;overflow:hidden}
.editor-panel{display:flex;flex-direction:column;overflow:hidden;min-height:60px}
.editor-body{flex:1;overflow:hidden;position:relative;min-height:0}
.editor-toolbar{display:flex;align-items:center;justify-content:space-between;padding:3px 10px;background:var(--bg-sidebar);border-bottom:1px solid var(--color-border);flex-shrink:0}
.toolbar-title{font-size:12px;color:var(--color-text-muted);font-weight:600}
.toolbar-actions{display:flex;align-items:center;gap:4px}
.result-panel{display:flex;flex-direction:column;overflow:hidden;min-height:40px}
.result-toolbar{display:flex;align-items:center;justify-content:space-between;padding:3px 10px;background:var(--bg-sidebar);border-top:1px solid var(--color-border);border-bottom:1px solid var(--color-border);flex-shrink:0}
.result-body{flex:1;overflow:auto;padding:4px 8px;min-height:0}
.result-table-wrap{max-height:calc(100% - 40px);overflow:auto}
.result-empty,.result-error,.result-affected{padding:20px;text-align:center;color:var(--color-text-muted);font-size:13px}
.result-error{color:#e53935}
.result-affected{color:var(--color-text-secondary)}
.result-pagination{display:flex;justify-content:flex-end;padding:6px 0}
.split-bar{height:4px;background:var(--bg-hover);cursor:ns-resize;flex-shrink:0;transition:background .2s;border-top:1px solid var(--color-border);border-bottom:1px solid var(--color-border)}
.split-bar:hover{background:var(--color-accent)}
.vsplit-bar{width:4px;background:var(--bg-hover);cursor:ew-resize;flex-shrink:0;transition:background .2s;border-left:1px solid var(--color-border);border-right:1px solid var(--color-border)}
.vsplit-bar:hover{background:var(--color-accent)}
.ctx-cache-badge{display:flex;align-items:center;padding:3px 8px;font-size:11px;color:var(--color-accent);gap:4px;white-space:nowrap}
</style>