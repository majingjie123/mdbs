<template>
  <div class="ai-assistant-panel">
    <!-- 顶栏：配置 + 操作 -->
    <div class="ai-toolbar">
      <n-select
        v-model:value="activeConfigId"
        :options="configOptions"
        placeholder="AI 配置"
        size="tiny"
        style="flex:1;min-width:0"
        clearable
      />
      <n-button size="tiny" quaternary @click="openTableSelect" :loading="contextLoading" :disabled="!connId" title="加载表结构">
        📋
      </n-button>
      <span v-if="contextText" class="ctx-dot active" title="已加载上下文"></span>
      <span v-else class="ctx-dot" title="无上下文"></span>
      <n-button v-if="contextText" size="tiny" quaternary @click="clearContext" title="清除上下文">✕</n-button>
    </div>

    <!-- 消息区 -->
    <div ref="msgArea" class="ai-msgs" @scroll="onScrollMsg" @click="onMsgClick">
      <div v-if="!messages.length" class="ai-welcome">
        <div class="ai-welcome-title">AI 助手</div>
        <p v-if="!connId">选择 AI 配置 &rarr; 选择连接 &rarr; 开始对话</p>
        <p v-else>输入消息开始对话，或先加载表结构作为上下文。</p>
      </div>
      <div v-for="(m,i) in messages" :key="i" :class="['ai-msg', m.role==='user'?'u':'a']">
        <div class="ai-msg-body">
          <div class="ai-msg-name">{{ m.role==='user'?'你':'AI' }}</div>
          <div v-if="m.role==='user'" class="ai-msg-text">{{ m.content }}</div>
          <div v-else-if="!m.content && streaming && i===messages.length-1" class="ai-msg-text loading-text">
            <span>.</span><span>.</span><span>.</span>
          </div>
          <div v-else class="ai-msg-text" v-html="renderMD(m.content)"></div>
        </div>
        <div v-if="m.content" class="ai-msg-actions">
          <span @click="copyMsg(m.content)" title="复制">📋</span>
          <span v-if="m.role==='user'" @click="editMsg(i)" title="编辑">✏️</span>
          <span v-if="m.role==='assistant' && i===messages.length-1 && !streaming" @click="regrow" title="重新生成">🔄</span>
          <span @click="delMsg(i)" title="删除">🗑️</span>
        </div>
      </div>
      <n-alert v-if="errMsg" type="error" closable @close="errMsg=''" style="margin:4px 0;font-size:12px">{{ errMsg }}</n-alert>
      <div v-if="showScrollBtn" class="scroll-btn" @click="scrollDown">↓</div>
    </div>

    <!-- 编辑消息弹窗 -->
    <n-modal v-model:show="showEditModal" title="编辑消息" preset="card" style="width:400px" :mask-closable="false">
      <n-input v-model:value="editText" type="textarea" :rows="3" />
      <template #footer>
        <n-space justify="end">
          <n-button size="small" @click="showEditModal=false">取消</n-button>
          <n-button size="small" type="primary" @click="confirmEdit">确认</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 输入区 -->
    <div class="ai-input-area">
      <div class="ai-input-wrapper">
        <n-input
          v-model:value="inputText"
          type="textarea"
          :rows="2"
          :autosize="{minRows:2,maxRows:4}"
          placeholder="输入消息，Enter 发送..."
          :disabled="streaming"
          size="small"
          @keydown="onKey"
        />
        <div class="send-btn" :class="{ streaming }" @click="streaming?stop():send()">
          <svg v-if="!streaming" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="5" height="12"/><rect x="13" y="6" width="5" height="12"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- 表选择对话框 -->
    <n-modal v-model:show="showTableSelect" title="选择表结构" preset="card" style="width:480px" mask-closable>
      <template #header>
        <span style="font-size:13px;color:#e0e0e0">选择要加载结构的数据表</span>
      </template>
      <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px">
        <n-input v-model:value="tableFilter" placeholder="搜索表名…" clearable size="small" style="flex:1" />
        <span style="color:#888;font-size:11px;white-space:nowrap">{{ filteredTableList.length }} / {{ tableList.length }}，已选 {{ tableList.filter(t=>t.checked).length }}</span>
        <n-space><n-button size="tiny" @click="selectAllTables">全选</n-button><n-button size="tiny" @click="deselectAllTables">取消</n-button></n-space>
      </div>
      <n-spin :show="tableLoading">
        <div style="max-height:250px;overflow-y:auto;border:1px solid #3c3c3c;border-radius:4px;padding:4px 0">
          <div v-for="t in filteredTableList" :key="t.name" style="display:flex;align-items:center;padding:4px 8px;cursor:pointer;border-bottom:1px solid #333"
            :style="{background:t.checked?'rgba(32,128,240,0.1)':'transparent'}"
            @click="t.checked=!t.checked">
            <n-checkbox :checked="t.checked" style="margin-right:6px" size="small" />
            <span style="font-size:12px;color:#ccc">{{ t.name }}</span>
            <span v-if="t.comment" style="margin-left:6px;font-size:10px;color:#666">— {{ t.comment }}</span>
          </div>
          <div v-if="!tableLoading && tableList.length===0" style="padding:16px;text-align:center;color:#666">该数据库无表</div>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../api'

const props = withDefaults(defineProps<{
  connId?: number | null
  dbName?: string
  schemaName?: string
}>(), { connId: null, dbName: '', schemaName: '' })

const msg = useMessage()

// ── 状态 ──
const inputText = ref('')
const messages = ref<{role:string;content:string}[]>([])
const streaming = ref(false)
const errMsg = ref('')
const abortCtrl = ref<AbortController | null>(null)
const msgArea = ref<HTMLElement | null>(null)
const showScrollBtn = ref(false)

// ── AI 配置 ──
const configs = ref<any[]>([])
const activeConfigId = ref<number | null>(null)
const configOptions = ref<{label:string;value:number}[]>([])

async function loadConfigs() {
  try {
    const r: any = await api.aiListConfigs()
    if (r.success && r.data) {
      configs.value = r.data
      configOptions.value = r.data.map((c: any) => ({ label: `${c.name} (${c.model})`, value: c.id }))
      if (!activeConfigId.value && r.data.length) {
        const d = r.data.find((c: any) => c.is_default)
        activeConfigId.value = d ? d.id : r.data[0].id
      }
    }
  } catch {}
}

// ── 上下文 ──
const contextText = ref('')
const contextInfo = ref('')
const contextLoading = ref(false)
const showTableSelect = ref(false)
const tableList = ref<{name:string;comment:string;checked:boolean}[]>([])
const tableLoading = ref(false)
const tableFilter = ref('')

const filteredTableList = computed(() => {
  const q = tableFilter.value.trim().toLowerCase()
  if (!q) return tableList.value
  return tableList.value.filter(t => t.name.toLowerCase().includes(q) || (t.comment || '').toLowerCase().includes(q))
})

async function openTableSelect() {
  if (!props.connId) { msg.warning('请先选择连接'); return }
  showTableSelect.value = true
  tableLoading.value = true
  try {
    const r: any = await api.listTables(props.connId, props.dbName || undefined, props.schemaName || undefined)
    if (r.success && r.data) {
      tableList.value = r.data.map((t: any) => ({ name: t.name, comment: t.comment || '', checked: false }))
    } else {
      msg.error(r.message || '获取表列表失败')
    }
  } catch (e: any) {
    msg.error('获取表列表失败: ' + (e.message || ''))
  } finally {
    tableLoading.value = false
  }
}

function selectAllTables() { tableList.value.forEach(t => t.checked = true) }
function deselectAllTables() { tableList.value.forEach(t => t.checked = false) }

async function confirmBuildContext() {
  const selected = tableList.value.filter(t => t.checked).map(t => t.name)
  if (!selected.length) { msg.warning('请至少选择一张表'); return }
  showTableSelect.value = false
  contextLoading.value = true
  try {
    const r: any = await api.aiBuildContext({
      conn_id: props.connId,
      database: props.dbName || undefined,
      schema_name: props.schemaName || undefined,
      tables: selected,
    })
    if (r.success && r.data) {
      contextText.value = r.data.context
      contextInfo.value = `${props.dbName || ''} (${r.data.db_type}) - ${selected.length} 张表`
      const loadedCount = r.data.tables ?? 0
      if (loadedCount === 0) {
        msg.warning('未能查到任何表的字段信息')
      } else if (loadedCount < selected.length) {
        msg.warning(`仅成功加载 ${loadedCount}/${selected.length} 张表`)
      } else {
        msg.success(`已加载 ${loadedCount} 张表的结构`)
      }
    } else msg.error(r.message || '构建上下文失败')
  } catch (e: any) {
    msg.error('构建失败: ' + (e.message || ''))
  } finally {
    contextLoading.value = false
  }
}

function clearContext() {
  contextText.value = ''
  contextInfo.value = ''
}

// ── 编辑消息 ──
const showEditModal = ref(false)
const editMsgIdx = ref<number | null>(null)
const editText = ref('')

function editMsg(idx: number) {
  editMsgIdx.value = idx
  editText.value = messages.value[idx]?.content || ''
  showEditModal.value = true
}

function confirmEdit() {
  if (editMsgIdx.value !== null) {
    messages.value[editMsgIdx.value] = { ...messages.value[editMsgIdx.value], content: editText.value }
  }
  showEditModal.value = false
  editMsgIdx.value = null
}

function copyMsg(content: string) {
  navigator.clipboard.writeText(content).then(() => msg.success('已复制')).catch(() => msg.error('复制失败'))
}

function onMsgClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const btn = target.closest('.code-copy-btn') as HTMLElement | null
  if (btn && btn.dataset.copyCode) {
    navigator.clipboard.writeText(btn.dataset.copyCode).then(() => {
      btn.textContent = '✓'
      setTimeout(() => { btn.textContent = '📋' }, 1500)
    }).catch(() => msg.error('复制失败'))
  }
}

function delMsg(idx: number) {
  messages.value.splice(idx, 1)
}

function regrow() {
  if (messages.value.length < 2) return
  let lastUserIdx = -1
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') { lastUserIdx = i; break }
  }
  if (lastUserIdx === -1) return
  if (messages.value[messages.value.length - 1].role === 'assistant') messages.value.pop()
  inputText.value = messages.value[lastUserIdx].content
  messages.value.splice(lastUserIdx)
  nextTick(() => send())
}

// ── 发送 / 接收 ──
async function send() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return
  if (!activeConfigId.value) { msg.warning('请选择 AI 配置'); return }

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  errMsg.value = ''
  scrollDown()

  messages.value.push({ role: 'assistant', content: '' })
  streaming.value = true

  const msgs: {role:string;content:string}[] = []
  if (contextText.value) {
msgs.push({ role: 'system', content: `你是数据库助手。当前数据库结构：\n\n${contextText.value}\n\n根据结构生成正确、可执行的 SQL 语句。注意：SQL 关键字（如 FROM、LEFT JOIN、ORDER BY、WHERE 等）前面必须加空格，不能紧跟前一个单词或标识符。` })
  }
  for (const m of messages.value.slice(0, -1)) msgs.push({ role: m.role, content: m.content })

  abortCtrl.value = new AbortController()
  try {
    const resp = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config_id: activeConfigId.value, messages: msgs }),
      signal: abortCtrl.value.signal,
    })
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({ message: '请求失败' }))
      throw new Error(e.message || e.detail || '请求失败')
    }
    if (!resp.headers.get('content-type')?.includes('text/event-stream')) {
      const json = await resp.json()
      throw new Error(json.message || '请求失败')
    }

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buf = '', full = '', idx = messages.value.length - 1
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '[DONE]') continue
        try {
          const parsed = JSON.parse(data)
          if (parsed.error) {
            errMsg.value = parsed.error
            messages.value.pop()
            streaming.value = false
            return
          }
          if (parsed.content) {
            full += parsed.content
            messages.value[idx] = { ...messages.value[idx], content: full }
            scrollDown()
          }
        } catch {}
      }
    }
    messages.value[idx] = { ...messages.value[idx], content: full }
  } catch (e: any) {
    if (e.name === 'AbortError') {
      messages.value.pop()
      msg.info('已停止')
    } else {
      errMsg.value = e.message || '请求失败'
      messages.value.pop()
    }
  } finally {
    streaming.value = false
    abortCtrl.value = null
  }
}

function stop() {
  abortCtrl.value?.abort()
  streaming.value = false
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

// ── 滚动 ──
function scrollDown() {
  nextTick(() => {
    if (msgArea.value) {
      msgArea.value.scrollTop = msgArea.value.scrollHeight
    }
  })
}

function onScrollMsg() {
  if (!msgArea.value) return
  const el = msgArea.value
  showScrollBtn.value = el.scrollHeight - el.scrollTop - el.clientHeight > 100
}

// ── 渲染 MD ──
function escapeHTML(s: string): string {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}

function normalizeSQL(s: string): string {
  const kw = '(?:FROM|LEFT\\s+JOIN|RIGHT\\s+JOIN|INNER\\s+JOIN|OUTER\\s+JOIN|CROSS\\s+JOIN|JOIN|WHERE|ORDER\\s+BY|GROUP\\s+BY|HAVING|LIMIT|OFFSET|UNION(?:\\s+ALL)?|VALUES|SET|INTO|ON|AND|OR|LIKE|BETWEEN|EXISTS|IN|ASC|DESC)'
  return s.replace(new RegExp('([^\\s,;(\\])(\\s*)(' + kw + ')\\b', 'gi'), '$1 $3')
}

function renderMD(text: string): string {
  if (!text) return ''
  let html = escapeHTML(text)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const trimmed = normalizeSQL(code.trim())
    const escaped = escapeHTML(trimmed)
    return `<div class="code-wrap"><span class="code-lang">${lang||'code'}</span><button class="code-copy-btn" data-copy-code="${escaped}" title="复制代码">📋</button><pre class="code-block"><code>${escaped}</code></pre></div>`
  })
  html = html.replace(/^---+\s*$/gm, '<hr/>')
  html = html.replace(/^&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="ol">$1</li>')
  html = html.replace(/(<li class="ol">.*<\/li>\n?)+/g, '<ol>$&</ol>')
  html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/\n\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)*)/g, (_, h, b) => {
    const heads = h.split('|').filter(Boolean).map((s: string) => `<th>${s.trim()}</th>`).join('')
    const rows = b.trim().split('\n').map((r: string) => `<tr>${r.split('|').filter(Boolean).map((c: string) => `<td>${c.trim()}</td>`).join('')}</tr>`).join('')
    return `<table><thead><tr>${heads}</tr></thead><tbody>${rows}</tbody></table>`
  })
  html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/`([^`]+)`/g, '<code class="ic">$1</code>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br/>')
  return `<p>${html}</p>`
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.ai-assistant-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-left: 1px solid var(--color-border, #333);
  background: var(--bg-app, #1e1e1e);
  min-width: 0;
  width: 100%;
}

.ai-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border-bottom: 1px solid var(--color-border, #333);
  background: var(--bg-sidebar, #252526);
  flex-shrink: 0;
}

.ctx-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #555;
  flex-shrink: 0;
}
.ctx-dot.active {
  background: #18a058;
  box-shadow: 0 0 4px #18a058;
}

.ai-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
}

.ai-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
  text-align: center;
  gap: 6px;
}
.ai-welcome-title {
  font-size: 14px;
  font-weight: 600;
  color: #ccc;
}
.ai-welcome p {
  margin: 0;
  font-size: 11px;
}

.ai-msg {
  display: flex;
  gap: 4px;
  max-width: 100%;
}
.ai-msg.u { flex-direction: row-reverse; }
.ai-msg-body {
  background: #2d2d2d;
  border-radius: 6px;
  padding: 6px 8px;
  max-width: 90%;
}
.ai-msg.u .ai-msg-body {
  background: #1a3a5c;
}
.ai-msg-name {
  font-size: 10px;
  color: #888;
  margin-bottom: 2px;
}
.ai-msg-text {
  color: #ddd;
  line-height: 1.4;
  word-break: break-word;
}
.ai-msg-text :deep(.code-wrap) {
  margin: 4px 0;
  border: 1px solid #3c3c3c;
  border-radius: 4px;
  overflow: hidden;
}
.ai-msg-text :deep(.code-lang) {
  display: block;
  padding: 2px 6px;
  font-size: 10px;
  background: #333;
  color: #888;
}
.ai-msg-text :deep(.code-block) {
  margin: 0;
  padding: 6px;
  background: #1e1e1e;
  overflow-x: auto;
  font-size: 11px;
}
.ai-msg-text :deep(.ic) {
  background: #333;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}
.ai-msg-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 4px 0;
  font-size: 11px;
}
.ai-msg-text :deep(th), .ai-msg-text :deep(td) {
  border: 1px solid #444;
  padding: 2px 4px;
}
.ai-msg-text :deep(blockquote) {
  border-left: 3px solid #555;
  padding-left: 8px;
  margin: 4px 0;
  color: #aaa;
}
.ai-msg-text :deep(hr) {
  border: none;
  border-top: 1px solid #444;
  margin: 6px 0;
}
.ai-msg-text :deep(strong) { color: #e0e0e0; }
.ai-msg-text :deep(a) { color: #2080f0; }

.ai-msg-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
  font-size: 11px;
  cursor: pointer;
  color: #666;
}
.ai-msg:hover .ai-msg-actions {
  opacity: 1;
}
.ai-msg-actions span:hover {
  color: #ccc;
}

.loading-text span {
  animation: dotPulse 1.4s infinite;
  font-size: 16px;
  line-height: 1;
}
.loading-text span:nth-child(2) { animation-delay: 0.2s; }
.loading-text span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}

.scroll-btn {
  position: sticky;
  bottom: 4px;
  text-align: center;
  cursor: pointer;
  color: #888;
  font-size: 14px;
  background: #333;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  line-height: 24px;
  align-self: center;
}
.scroll-btn:hover {
  background: #444;
  color: #fff;
}

.ai-input-area {
  flex-shrink: 0;
  border-top: 1px solid var(--color-border, #333);
  padding: 4px 6px;
  background: var(--bg-sidebar, #252526);
}

.ai-input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 4px;
}
.ai-input-wrapper :deep(.n-input) {
  flex: 1;
}
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  cursor: pointer;
  color: #2080f0;
  flex-shrink: 0;
}
.send-btn:hover {
  background: rgba(32,128,240,0.15);
}
.send-btn.streaming {
  color: #e74c3c;
}
.send-btn.streaming:hover {
  background: rgba(231,76,60,0.15);
}

.ai-msg-text :deep(.code-copy-btn) {
  position: absolute;
  top: 2px;
  right: 4px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 11px;
  padding: 2px 4px;
  color: #888;
  border-radius: 3px;
  line-height: 1;
}
.ai-msg-text :deep(.code-copy-btn:hover) {
  background: rgba(255,255,255,0.1);
  color: #ddd;
}
.ai-msg-text :deep(.code-wrap) {
  position: relative;
}
</style>
