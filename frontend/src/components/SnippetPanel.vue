<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'

export interface SqlSnippet {
  id: string
  name: string
  sql: string
  description: string
  createdAt: string
}

const props = withDefaults(defineProps<{
  visible?: boolean
}>(), {
  visible: false,
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', sql: string): void
}>()

const message = useMessage()
const dialog = useDialog()

const SNIPPETS_KEY = 'mdbs_sql_snippets'

const snippets = ref<SqlSnippet[]>([])
const searchText = ref('')
const showAddDialog = ref(false)
const editName = ref('')
const editDesc = ref('')
const editSql = ref('')
const editingId = ref<string | null>(null)
const currentSql = ref('')

// ── 暴露方法供父组件设置当前 SQL ──
function setCurrentSql(sql: string) {
  currentSql.value = sql
}

defineExpose({ setCurrentSql })

// ── 加载/保存 ──
function loadSnippets() {
  try {
    const raw = localStorage.getItem(SNIPPETS_KEY)
    if (raw) snippets.value = JSON.parse(raw)
  } catch { /* ignore */ }
}

function saveSnippets() {
  try {
    localStorage.setItem(SNIPPETS_KEY, JSON.stringify(snippets.value))
  } catch { /* ignore */ }
}

// ── 搜索 ──
const filteredSnippets = computed(() => {
  if (!searchText.value.trim()) return snippets.value
  const kw = searchText.value.toLowerCase()
  return snippets.value.filter(s =>
    s.name.toLowerCase().includes(kw) ||
    s.sql.toLowerCase().includes(kw) ||
    s.description.toLowerCase().includes(kw)
  )
})

// ── 选择插入 ──
function selectSnippet(snippet: SqlSnippet) {
  emit('select', snippet.sql)
  message.success(`已插入:「${snippet.name}」`)
}

// ── 保存当前 SQL 为片段 ──
function openAddDialog() {
  editName.value = ''
  editDesc.value = ''
  editSql.value = currentSql.value
  editingId.value = null
  showAddDialog.value = true
}

function doSaveSnippet() {
  if (!editName.value.trim()) {
    message.warning('请输入片段名称')
    return
  }
  if (!editSql.value.trim()) {
    message.warning('请输入 SQL 内容')
    return
  }

  if (editingId.value) {
    // 编辑已有
    const idx = snippets.value.findIndex(s => s.id === editingId.value)
    if (idx >= 0) {
      snippets.value[idx] = {
        ...snippets.value[idx],
        name: editName.value.trim(),
        sql: editSql.value.trim(),
        description: editDesc.value.trim(),
      }
    }
  } else {
    // 新增
    snippets.value.unshift({
      id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
      name: editName.value.trim(),
      sql: editSql.value.trim(),
      description: editDesc.value.trim(),
      createdAt: new Date().toISOString(),
    })
  }

  saveSnippets()
  showAddDialog.value = false
  message.success(editingId.value ? '片段已更新' : '片段已保存')
}

// ── 删除 ──
function deleteSnippet(snippet: SqlSnippet) {
  dialog.warning({
    title: '删除片段',
    content: `确定要删除片段「${snippet.name}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => {
      snippets.value = snippets.value.filter(s => s.id !== snippet.id)
      saveSnippets()
      message.success('已删除')
    },
  })
}

// ── 编辑 ──
function editSnippet(snippet: SqlSnippet) {
  editName.value = snippet.name
  editDesc.value = snippet.description
  editSql.value = snippet.sql
  editingId.value = snippet.id
  showAddDialog.value = true
}

onMounted(loadSnippets)
</script>

<template>
  <div v-if="visible" class="snippet-panel">
    <div class="snippet-header">
      <span>SQL 片段</span>
      <n-space size="small">
        <n-button size="tiny" quaternary @click="openAddDialog" title="将当前 SQL 保存为片段">➕ 新增</n-button>
        <n-button size="tiny" quaternary @click="$emit('close')">✕</n-button>
      </n-space>
    </div>
    <div class="snippet-search">
      <n-input
        v-model:value="searchText"
        placeholder="搜索片段..."
        clearable
        size="tiny"
      />
    </div>
    <div class="snippet-body">
      <div
        v-for="snippet in filteredSnippets"
        :key="snippet.id"
        class="snippet-item"
        @click="selectSnippet(snippet)"
      >
        <div class="snippet-item-header">
          <span class="snippet-item-name">{{ snippet.name }}</span>
          <n-space size="small">
            <n-button size="tiny" quaternary @click.stop="editSnippet(snippet)">✏️</n-button>
            <n-button size="tiny" quaternary type="error" @click.stop="deleteSnippet(snippet)">🗑️</n-button>
          </n-space>
        </div>
        <div class="snippet-item-sql">{{ snippet.sql.slice(0, 100) }}{{ snippet.sql.length > 100 ? '...' : '' }}</div>
        <div v-if="snippet.description" class="snippet-item-desc">{{ snippet.description }}</div>
      </div>
      <n-empty v-if="filteredSnippets.length === 0" :description="searchText ? '无匹配片段' : '暂无片段，点击「➕ 新增」添加'" />
    </div>

    <!-- 新增/编辑对话框 -->
    <n-modal v-model:show="showAddDialog" title="SQL 片段" preset="card" style="width: 500px" :mask-closable="false">
      <n-space vertical>
        <n-input
          v-model:value="editName"
          placeholder="片段名称（必填）"
        />
        <n-input
          v-model:value="editDesc"
          placeholder="描述（可选）"
        />
        <n-input
          v-model:value="editSql"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 12 }"
          placeholder="SQL 语句"
        />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showAddDialog = false">取消</n-button>
          <n-button type="primary" @click="doSaveSnippet">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.snippet-panel {
  width: 320px;
  min-width: 280px;
  border-left: 1px solid var(--color-border, #3c3c3c);
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideIn 0.2s ease;
}
@keyframes slideIn {
  from { width: 0; min-width: 0; opacity: 0; }
  to { width: 320px; min-width: 280px; opacity: 1; }
}
.snippet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border, #3c3c3c);
  font-size: 13px;
  font-weight: bold;
  flex-shrink: 0;
}
.snippet-search {
  padding: 6px 10px;
  flex-shrink: 0;
}
.snippet-body {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.snippet-item {
  padding: 6px 10px;
  cursor: pointer;
  border-bottom: 1px solid #2a2a2a;
  transition: background 0.1s;
}
.snippet-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.snippet-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.snippet-item-name {
  color: #e0e0e0;
  font-size: 12px;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.snippet-item-sql {
  font-family: 'Consolas', monospace;
  font-size: 11px;
  color: #888;
  margin-top: 2px;
  white-space: pre-wrap;
  word-break: break-all;
}
.snippet-item-desc {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
  font-style: italic;
}
</style>
