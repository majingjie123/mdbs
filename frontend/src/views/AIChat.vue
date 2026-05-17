<template>
  <div class="ai-chat-container">
    <!-- Top toolbar -->
    <div class="chat-toolbar">
      <div class="toolbar-left">
        <n-select
          v-model:value="activeConfigId"
          :options="configOptions"
          placeholder="选择 AI 配置"
          style="width: 220px"
          clearable
        />
        <n-button size="small" @click="buildContext" :loading="contextLoading" :disabled="!props.connId">
          加载上下文
        </n-button>
        <n-tag v-if="contextInfo" size="small" type="info">
          {{ contextInfo }}
        </n-tag>
      </div>
      <div class="toolbar-right">
        <n-button size="small" quaternary @click="saveChat" :disabled="messages.length === 0">
          保存
        </n-button>
        <n-button size="small" quaternary @click="loadHistory">
          历史
        </n-button>
        <n-button size="small" quaternary @click="clearChat" :disabled="messages.length === 0">
          清空
        </n-button>
        <n-button size="small" quaternary @click="goAISettings">
          设置
        </n-button>
      </div>
    </div>

    <!-- Message area -->
    <div ref="msgContainer" class="chat-messages">
      <div v-if="messages.length === 0" class="chat-welcome">
        <n-icon size="48" color="#18a058">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
        </n-icon>
        <h2>AI 助手</h2>
        <p>选择一个 AI 配置，然后开始对话。<br/>如需数据库上下文，请先选择连接并点击"加载上下文"。</p>
      </div>

      <div v-for="(msg, idx) in messages" :key="idx" :class="['msg-bubble', msg.role === 'user' ? 'msg-user' : 'msg-assistant', msg.role === 'system' ? 'msg-system' : '']">
        <div class="msg-avatar">
          <n-avatar :size="32" :color="msg.role === 'user' ? '#2080f0' : '#18a058'">
            {{ msg.role === 'user' ? 'U' : 'AI' }}
          </n-avatar>
        </div>
        <div class="msg-content">
          <div class="msg-name">{{ msg.role === 'user' ? '你' : 'AI 助手' }}</div>
          <div v-if="msg.role === 'system'" class="msg-system-text">{{ msg.content }}</div>
          <div v-else class="msg-text" v-html="renderMarkdown(msg.content)"></div>
        </div>
        <div v-if="idx === messages.length - 1 && isStreaming" class="streaming-indicator">
          <n-spin size="small" />
        </div>
      </div>

      <!-- Error messages -->
      <n-alert v-if="errorMsg" type="error" closable @close="errorMsg = ''" style="margin: 8px 0">
        {{ errorMsg }}
      </n-alert>

      <!-- History selector modal -->
      <n-modal v-model:show="showHistory" title="聊天历史" preset="card" style="width: 600px">
        <n-data-table
          :columns="historyColumns"
          :data="historyList"
          :loading="historyLoading"
          striped
          @row-click="loadHistoryRecord"
        />
      </n-modal>
    </div>

    <!-- Input area -->
    <div class="chat-input-area">
      <div class="chat-input-wrapper">
        <n-input
          v-model:value="inputText"
          type="textarea"
          :rows="2"
          :autosize="{ minRows: 2, maxRows: 6 }"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行..."
          :disabled="isStreaming"
          @keydown="handleKeydown"
        />
        <n-button
          type="primary"
          :loading="isStreaming"
          @click="sendMessage"
          style="margin-left: 8px; align-self: flex-end"
        >
          {{ isStreaming ? '停止' : '发送' }}
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../api'

const props = withDefaults(defineProps<{
  connId?: number
  db?: string
}>(), {
  connId: 0,
  db: '',
})

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

// State
const messages = ref<{ role: string; content: string }[]>([])
const inputText = ref('')
const isStreaming = ref(false)
const abortController = ref<AbortController | null>(null)
const errorMsg = ref('')
const msgContainer = ref<HTMLElement | null>(null)

// Config
const configs = ref<any[]>([])
const activeConfigId = ref<number | null>(null)
const configOptions = ref<{ label: string; value: number }[]>([])

// Context
const contextText = ref('')
const contextInfo = ref('')
const contextLoading = ref(false)

// History
const showHistory = ref(false)
const historyList = ref<any[]>([])
const historyLoading = ref(false)

const historyColumns = [
  { title: 'ID', key: 'id', width: 50 },
  { title: '数据库', key: 'db_name', width: 100 },
  { title: '摘要', key: 'context_summary', ellipsis: { tooltip: true } },
  { title: '时间', key: 'updated_at', width: 160 },
]

// ── Markdown render ─────────────────────────────────────

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = escapeHtml(text)
  // Code blocks (``` ... ```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="code-block"><code>${code.trim()}</code></pre>`
  })
  // Inline code (`...`)
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  // Bold (**...**)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
  // Unordered lists
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
  // Line breaks
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br/>')
  return `<p>${html}</p>`
}

// ── Load configs ────────────────────────────────────────

async function loadConfigs() {
  try {
    const res: any = await api.aiListConfigs()
    if (res.success && res.data) {
      configs.value = res.data
      configOptions.value = res.data.map((c: any) => ({
        label: `${c.name} (${c.model})`,
        value: c.id,
      }))
      if (!activeConfigId.value && res.data.length > 0) {
        const def = res.data.find((c: any) => c.is_default)
        activeConfigId.value = def ? def.id : res.data[0].id
      }
    }
  } catch (e: any) {
    message.warning('加载 AI 配置失败: ' + (e.message || ''))
  }
}

// ── Build context ────────────────────────────────────────

async function buildContext() {
  if (!props.connId) {
    message.warning('请先选择数据库连接')
    return
  }
  contextLoading.value = true
  try {
    const res: any = await api.aiBuildContext({
      conn_id: props.connId,
      database: props.db || undefined,
    })
    if (res.success && res.data) {
      contextText.value = res.data.context
      contextInfo.value = `${res.data.db_name} (${res.data.db_type})`
      message.success('上下文已加载')
    } else {
      message.error(res.message || '加载上下文失败')
    }
  } catch (e: any) {
    message.error('加载上下文失败: ' + (e.message || ''))
  } finally {
    contextLoading.value = false
  }
}

// ── Send message (SSE) ──────────────────────────────────

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) {
    if (isStreaming.value) {
      abortController.value?.abort()
      isStreaming.value = false
    }
    return
  }

  if (!activeConfigId.value) {
    message.warning('请先选择 AI 配置')
    return
  }

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  errorMsg.value = ''
  scrollToBottom()

  messages.value.push({ role: 'assistant', content: '' })
  isStreaming.value = true

  const apiMessages: { role: string; content: string }[] = []
  if (contextText.value) {
    apiMessages.push({
      role: 'system',
      content: `你是一个专业的数据库助手。以下是当前数据库的结构信息：\n\n${contextText.value}\n\n请根据以上表结构信息回答用户的问题。`,
    })
  }
  for (const m of messages.value.slice(0, -1)) {
    apiMessages.push({ role: m.role, content: m.content })
  }

  abortController.value = new AbortController()

  try {
    const response = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        config_id: activeConfigId.value,
        messages: apiMessages,
      }),
      signal: abortController.value.signal,
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({ message: '请求失败' }))
      throw new Error(err.message || err.detail || '请求失败')
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullContent = ''
    let idx = messages.value.length - 1

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) {
              errorMsg.value = parsed.error
              messages.value.pop()
              isStreaming.value = false
              return
            }
            if (parsed.content) {
              fullContent += parsed.content
              if (messages.value[idx]) {
                messages.value[idx] = { ...messages.value[idx], content: fullContent }
              }
              scrollToBottom()
            }
          } catch {}
        }
      }
    }
    messages.value[idx] = { ...messages.value[idx], content: fullContent }
  } catch (e: any) {
    if (e.name === 'AbortError') {
      messages.value.pop()
      message.info('已停止生成')
    } else {
      errorMsg.value = e.message || '请求失败'
      messages.value.pop()
    }
  } finally {
    isStreaming.value = false
    abortController.value = null
  }
}

// ── Keyboard ─────────────────────────────────────────────

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// ── Scroll ───────────────────────────────────────────────

function scrollToBottom() {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight
    }
  })
}

// ── Clear ────────────────────────────────────────────────

function clearChat() {
  dialog.warning({
    title: '清空对话',
    content: '确定清空当前对话吗？',
    positiveText: '确定',
    onPositiveClick: () => {
      messages.value = []
      contextText.value = ''
      contextInfo.value = ''
    },
  })
}

// ── Save / Load history ─────────────────────────────────

async function saveChat() {
  if (messages.value.length === 0) {
    message.warning('没有消息可保存')
    return
  }
  try {
    const summary = messages.value[0]?.content?.slice(0, 100) || ''
    const res: any = await api.aiSaveHistory({
      conn_id: props.connId || null,
      db_name: props.db || null,
      messages: messages.value,
      context_summary: summary,
    })
    if (res.success) message.success('聊天已保存')
    else message.error(res.message || '保存失败')
  } catch (e: any) {
    message.error('保存失败: ' + (e.message || ''))
  }
}

async function loadHistory() {
  showHistory.value = true
  historyLoading.value = true
  try {
    const res: any = await api.aiListHistory()
    if (res.success) historyList.value = res.data || []
  } catch (e: any) {
    message.error('加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function loadHistoryRecord(row: any, _: any) {
  try {
    const res: any = await api.aiGetHistory(row.id)
    if (res.success && res.data) {
      const msgs = res.data.messages || []
      if (Array.isArray(msgs)) messages.value = msgs
      contextInfo.value = res.data.db_name || ''
      showHistory.value = false
      message.success('已加载历史记录')
      scrollToBottom()
    }
  } catch (e: any) {
    message.error('加载失败')
  }
}

// ── Navigation ──────────────────────────────────────────

function goAISettings() {
  router.push('/ai/settings')
}

// ── Init ─────────────────────────────────────────────────

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.ai-chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1e1e1e;
}
.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid #3c3c3c;
  background: #252526;
  flex-shrink: 0;
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #888;
  text-align: center;
  gap: 8px;
}
.chat-welcome h2 { margin: 0; color: #e0e0e0; }
.msg-bubble { display: flex; gap: 10px; margin-bottom: 16px; position: relative; }
.msg-user { flex-direction: row-reverse; }
.msg-system { justify-content: center; }
.msg-system .msg-content { background: transparent; padding: 0; }
.msg-system-text { color: #888; font-style: italic; font-size: 0.9em; }
.msg-content { max-width: 70%; padding: 10px 14px; border-radius: 8px; background: #2d2d2d; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
.msg-user .msg-content { background: #2080f0; color: #fff; }
.msg-user .msg-content :deep(a) { color: #fff; text-decoration: underline; }
.msg-name { font-size: 0.8em; color: #888; margin-bottom: 4px; }
.msg-user .msg-name { color: rgba(255,255,255,0.8); text-align: right; }
.msg-text { line-height: 1.6; word-break: break-word; }
.msg-text :deep(p) { margin: 0 0 8px; }
.msg-text :deep(p:last-child) { margin-bottom: 0; }
.msg-text :deep(pre.code-block) { background: #1e1e1e; border: 1px solid #3c3c3c; border-radius: 4px; padding: 10px; overflow-x: auto; font-size: 0.9em; margin: 8px 0; color: #d4d4d4; }
.msg-text :deep(code.inline-code) { background: #2d2d2d; padding: 1px 5px; border-radius: 3px; font-size: 0.9em; }
.msg-text :deep(h2), .msg-text :deep(h3), .msg-text :deep(h4) { margin: 12px 0 6px; }
.msg-text :deep(ul) { margin: 4px 0; padding-left: 20px; }
.msg-text :deep(li) { margin: 2px 0; }
.streaming-indicator { position: absolute; bottom: -4px; right: -8px; }
.msg-user .streaming-indicator { left: -8px; right: auto; }
.chat-input-area { padding: 12px 16px; border-top: 1px solid #3c3c3c; background: #252526; flex-shrink: 0; }
.chat-input-wrapper { display: flex; align-items: flex-start; }
</style>