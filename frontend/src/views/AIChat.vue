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
    </div>

<!-- 顶栏 -->
    <div class="bar">
      <div class="bar-left">
        <n-select v-model:value="activeConfigId" :options="configOptions" placeholder="AI 配置" style="width:180px" clearable />
        <n-button size="small" @click="openTableSelect" :loading="contextLoading" :disabled="!connId">加载上下文</n-button>
        <n-tag v-if="contextInfo" size="small" type="info">{{ contextInfo }}</n-tag>
        <n-button v-if="contextText" size="small" quaternary @click="showContext=!showContext">预览</n-button>
      </div>
      <div class="bar-right">
        <n-button size="small" quaternary @click="saveChat" :disabled="!messages.length">保存</n-button>
        <n-button size="small" quaternary @click="loadHistory">历史</n-button>
        <n-button size="small" quaternary @click="showExport=true" :disabled="!messages.length">导出</n-button>
        <n-button size="small" quaternary @click="clearChat" :disabled="!messages.length">清空</n-button>
        <n-button size="small" quaternary @click="goAISettings">设置</n-button>
      </div>
    </div>

    <!-- 消息区 -->
    <div ref="msgArea" class="msgs" @scroll="onScrollMsg">
      <!-- 欢迎 -->
      <div v-if="!messages.length" class="welcome">
        <h2>AI 助手</h2>
        <p>选择 AI 配置 &rarr; 选择连接并加载上下文 &rarr; 开始对话</p>
        <div class="prompts">
          <n-button size="tiny" secondary @click="useTmpl('列出当前数据库所有表')">列出所有表</n-button>
          <n-button size="tiny" secondary @click="useTmpl('分析这个数据库的设计')">分析架构</n-button>
          <n-button size="tiny" secondary @click="useTmpl('解释外键关系')">外键关系</n-button>
          <n-button size="tiny" secondary @click="useTmpl('生成多表 JOIN')">JOIN 示例</n-button>
        </div>
      </div>

      <div v-for="(m,i) in messages" :key="i" :class="['msg', m.role==='user'?'u':'a']">
        <n-avatar :size="28" :color="m.role==='user'?'#2080f0':'#18a058'">{{ m.role==='user'?'U':'AI' }}</n-avatar>
        <div class="msg-body">
          <div class="msg-name">{{ m.role==='user'?'你':'AI 助手' }}</div>
          <div v-if="m.role==='system'" class="sys-text">{{ m.content }}</div>
          <div v-else class="msg-text" v-html="renderMD(m.content)"></div>
        </div>
        <div v-if="m.role!=='system'" class="msg-act" @click.stop>
          <span @click="copyMsg(m.content)" title="复制"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg></span>
          <span v-if="m.role==='assistant' && i===messages.length-1 && !streaming" @click="regrow" title="重新生成"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L22 10"/></svg></span>
          <span @click="delMsg(i)" title="删除"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg></span>
        </div>
      </div>

      <n-alert v-if="errMsg" type="error" closable @close="errMsg=''" style="margin:8px 0">{{ errMsg }}</n-alert>
      <div v-if="showScrollBtn" class="scroll-btn" @click="scrollDown">&darr;</div>
    </div>

    <!-- 输入 -->
    <div class="input-area">
      <div class="input-wrapper">
        <n-input v-model:value="input" type="textarea" :rows="2" :autosize="{minRows:2,maxRows:6}"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行..." :disabled="streaming"
          @keydown="onKey" />
        <n-button type="primary" :loading="streaming" @click="streaming?stop():send()" style="margin-left:8px;align-self:flex-end">
          {{ streaming?'停止':'发送' }}
        </n-button>
      </div>
    </div>

    <!-- 上下文预览 -->
    <n-modal v-model:show="showContext" title="数据库上下文" preset="card" style="width:680px">
      <pre style="white-space:pre-wrap;max-height:400px;overflow:auto;">{{ contextText }}</pre>
    </n-modal>

    <!-- 表选择对话框 -->
    <n-modal v-model:show="showTableSelect"
      title="选择表结构" preset="card" style="width:520px"
      mask-closable>
      <template #header>
        <span style="font-size:14px;color:#e0e0e0">选择要加载结构的数据表</span>
      </template>
      <div style="margin-bottom:10px;display:flex;align-items:center;justify-content:space-between">
        <span style="color:#888;font-size:12px">{{ tableList.length }} 张表，已选 {{ tableList.filter(t=>t.checked).length }} 张</span>
        <n-space>
          <n-button size="tiny" @click="selectAllTables">全选</n-button>
          <n-button size="tiny" @click="deselectAllTables">取消全选</n-button>
        </n-space>
      </div>
      <n-spin :show="tableLoading">
        <div style="max-height:340px;overflow-y:auto;border:1px solid #3c3c3c;border-radius:4px;padding:4px 0">
          <div v-for="t in tableList" :key="t.name" style="display:flex;align-items:center;padding:6px 10px;cursor:pointer;border-bottom:1px solid #333"
            :style="{background:t.checked?'rgba(32,128,240,0.1)':'transparent'}"
            @click="t.checked=!t.checked">
            <n-checkbox :checked="t.checked" style="margin-right:8px" />
            <span style="font-size:13px;color:#ccc">{{ t.name }}</span>
            <span v-if="t.comment" style="margin-left:8px;font-size:11px;color:#666">— {{ t.comment }}</span>
          </div>
          <div v-if="!tableLoading && tableList.length===0" style="padding:20px;text-align:center;color:#666">该数据库无表</div>
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
    <n-modal v-model:show="showExport" title="导出对话" preset="card" style="width:400px">
      <n-space vertical>
        <n-button @click="doExport('markdown')">导出 Markdown</n-button>
        <n-button @click="doExport('text')" style="margin-top:8px">导出纯文本</n-button>
      </n-space>
    </n-modal>

    <!-- 历史 -->
    <n-modal v-model:show="showHistory" title="聊天历史" preset="card" style="width:600px">
      <n-data-table :columns="histCols" :data="histList" :loading="histLoading" striped @row-click="loadHist" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../api'
import { useAppStore } from '../stores/app'

const props = withDefaults(defineProps<{
  connId?: number | null; db?: string; dbName?: string; schemaName?: string; tableName?: string; nodeType?: string; connName?: string
}>(), { connId: null, db: '', dbName: '', schemaName: '', tableName: '', nodeType: '', connName: '' })

const msg = useMessage(), dialog = useDialog(), store = useAppStore()

// 会话管理
let sid = 0
const sessions = ref([{ id: ++sid, name: '会话 1', msgs: [] as {role:string;content:string}[] }])
const activeSessionId = ref(1)
const messages = computed(() => sessions.value.find(s=>s.id===activeSessionId.value)?.msgs||[])

function switchSession(id: number) { activeSessionId.value = id }
function addSession() {
  sessions.value.push({ id: ++sid, name: `会话 ${sid}`, msgs: [] })
  activeSessionId.value = sid
  contextText.value = ''; contextInfo.value = ''
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
const contextText = ref('')
const contextInfo = ref('')
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
      contextText.value = r.data.context
      const db = (props.dbName||props.db||'')
      contextInfo.value = `${db} (${r.data.db_type}) - ${selected.length} 张表`
      msg.success(`已加载 ${selected.length} 张表的结构`)
    } else msg.error(r.message||'构建上下文失败')
  } catch (e:any) { msg.error('构建失败: '+(e.message||''))
  } finally { contextLoading.value = false }
}

function useTmpl(t: string) { input.value = t; nextTick(()=>send()) }

// 输入
const input = ref('')
const streaming = ref(false)
const abortCtrl = ref<AbortController|null>(null)
const errMsg = ref('')
const msgArea = ref<HTMLElement|null>(null)
const showScrollBtn = ref(false)

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
  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="ic">$1</code>')
  // 加粗
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // 标题
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
  // 无序列表
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
  // 表格
  html = html.replace(/\n\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)*)/g, (_, h, b) => {
    const heads = h.split('|').filter(Boolean).map((s:string)=>`<th>${s.trim()}</th>`).join('')
    const rows = b.trim().split('\n').map((r:string)=>`<tr>${r.split('|').filter(Boolean).map((c:string)=>`<td>${c.trim()}</td>`).join('')}</tr>`).join('')
    return `<table><thead><tr>${heads}</tr></thead><tbody>${rows}</tbody></table>`
  })
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
          if (parsed.error) { errMsg.value = parsed.error; sess.msgs.pop(); streaming.value=false; return }
          if (parsed.content) { full += parsed.content; sess.msgs[idx] = {...sess.msgs[idx], content: full}; scrollDown() }
        } catch {}
      }
    }
    sess.msgs[idx] = {...sess.msgs[idx], content: full}
  } catch (e:any) {
    if (e.name==='AbortError') { sess.msgs.pop(); msg.info('已停止') }
    else { errMsg.value = e.message||'请求失败'; sess.msgs.pop() }
  } finally {
    streaming.value = false; abortCtrl.value = null
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
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `ai-chat-${Date.now()}.${format==='markdown'?'md':'txt'}`; a.click()
  URL.revokeObjectURL(url)
  showExport.value = false
  msg.success('导出成功')
}

// 保存
async function saveChat() {
  const sess = sessions.value.find(s=>s.id===activeSessionId.value)
  if (!sess || !sess.msgs.length) { msg.warning('没有消息'); return }
  try {
    const summary = sess.msgs[0]?.content?.slice(0,100)||''
    const r:any = await api.aiSaveHistory({
      conn_id: props.connId||null, db_name: props.db||null,
      messages: sess.msgs, context_summary: summary,
    })
    if (r.success) msg.success('已保存')
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
  try {
    const r:any = await api.aiGetHistory(row.id)
    if (r.success && r.data) {
      const ms = r.data.messages||[]
      if (Array.isArray(ms)) {
        const sess = sessions.value.find(s=>s.id===activeSessionId.value)
        if (sess) sess.msgs = ms
      }
      contextInfo.value = r.data.db_name||''
      showHistory.value = false; msg.success('已加载'); scrollDown()
    }
  } catch(e:any) { msg.error('加载失败') }
}

async function clearChat() {
  dialog.warning({title:'清空对话',content:'确定清空吗？',positiveText:'确定',
    onPositiveClick:()=>{
      const sess = sessions.value.find(s=>s.id===activeSessionId.value)
      if (sess) sess.msgs = []
      contextText.value = ''; contextInfo.value = ''
    }
  })
}

function goAISettings() { store.openTab('ai-settings','AI 设置',{},true) }

onMounted(loadConfigs)
</script>

<style scoped>
.ai-chat-container{display:flex;flex-direction:column;height:100%;background:#1e1e1e}
.session-tabs{display:flex;background:#252526;border-bottom:1px solid #3c3c3c;min-height:30px;overflow-x:auto;flex-shrink:0}
.session-tab{display:flex;align-items:center;gap:4px;padding:5px 12px;font-size:12px;color:#999;cursor:pointer;border-right:1px solid #3c3c3c;white-space:nowrap;user-select:none}
.session-tab:hover{background:#2d2d2d;color:#ccc}
.session-tab.active{background:#1e1e1e;color:#fff;border-bottom:2px solid #0078d4}
.session-close{display:flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:3px;font-size:10px;color:#666;cursor:pointer}
.session-close:hover{background:#3c3c3c;color:#fff}
.session-add{display:flex;align-items:center;padding:5px 12px;font-size:14px;color:#888;cursor:pointer;user-select:none}
.session-add:hover{color:#fff}
.bar{display:flex;align-items:center;justify-content:space-between;padding:6px 12px;border-bottom:1px solid #3c3c3c;background:#252526;flex-shrink:0}
.bar-left,.bar-right{display:flex;align-items:center;gap:6px}
.msgs{flex:1;overflow-y:auto;padding:12px}
.welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:#888;text-align:center;gap:8px}
.welcome h2{margin:0;color:#e0e0e0}
.prompts{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;justify-content:center}
.msg{display:flex;gap:8px;margin-bottom:14px;position:relative}
.msg.u{flex-direction:row-reverse}
.msg-body{max-width:70%;padding:8px 12px;border-radius:8px;background:#2d2d2d}
.msg.u .msg-body{background:#2080f0;color:#fff}
.msg-name{font-size:0.78em;color:#888;margin-bottom:3px}
.msg.u .msg-name{color:rgba(255,255,255,0.8);text-align:right}
.msg-text{line-height:1.6;word-break:break-word;font-size:13px}
.msg-text :deep(p){margin:0 0 6px}
.msg-text :deep(p:last-child){margin-bottom:0}
.msg-text :deep(.code-wrap){position:relative;background:#1e1e1e;border:1px solid #3c3c3c;border-radius:4px;margin:6px 0}
.msg-text :deep(.code-lang){position:absolute;top:2px;left:8px;font-size:11px;color:#888;text-transform:uppercase}
.msg-text :deep(.code-copy){position:absolute;top:2px;right:4px;background:#3c3c3c;border:none;color:#aaa;cursor:pointer;padding:2px 8px;font-size:11px;border-radius:3px}
.msg-text :deep(.code-copy:hover){background:#555;color:#fff}
.msg-text :deep(.code-block){padding:22px 10px 8px;overflow-x:auto;font-size:0.9em;margin:0;color:#d4d4d4}
.msg-text :deep(code.ic){background:#3c3c3c;padding:1px 5px;border-radius:3px;font-size:0.9em}
.msg-text :deep(h2),.msg-text :deep(h3),.msg-text :deep(h4){margin:10px 0 5px}
.msg-text :deep(ul){margin:4px 0;padding-left:18px}
.msg-text :deep(li){margin:2px 0}
.msg-text :deep(table){border-collapse:collapse;margin:6px 0;font-size:12px;width:100%}
.msg-text :deep(th),.msg-text :deep(td){border:1px solid #3c3c3c;padding:4px 8px;text-align:left}
.msg-text :deep(th){background:#2d2d2d;font-weight:600}
.msg-act{display:none;flex-direction:column;gap:4px;position:absolute;right:-2px;top:0;padding:2px}
.msg.u .msg-act{right:auto;left:-2px}
.msg:hover .msg-act{display:flex}
.msg-act span{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:4px;cursor:pointer;color:#888;background:rgba(0,0,0,0.3)}
.msg-act span:hover{background:#3c3c3c;color:#fff}
.scroll-btn{position:sticky;bottom:8px;left:50%;transform:translateX(-50%);width:32px;height:32px;border-radius:50%;background:#3c3c3c;color:#ccc;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:16px;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,0.3)}
.scroll-btn:hover{background:#555;color:#fff}
.input-area{padding:10px 12px;border-top:1px solid #3c3c3c;background:#252526;flex-shrink:0}
.input-wrapper{display:flex;align-items:flex-start}
.sys-text{color:#888;font-style:italic;font-size:0.9em}
</style>