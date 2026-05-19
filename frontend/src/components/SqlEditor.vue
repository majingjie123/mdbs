<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { EditorView, keymap } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { sql, MySQL } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import { autocompletion, CompletionContext } from '@codemirror/autocomplete'
import { defaultKeymap, indentWithTab } from '@codemirror/commands'
import { searchKeymap } from '@codemirror/search'

const props = withDefaults(defineProps<{
  modelValue: string
  connId?: number
  dbName?: string
}>(), {
  modelValue: '',
})

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
  (e: 'execute'): void
}>()

// 自动补全 - 表名/列名/视图名/函数名缓存
const schemaCache = ref<{
  tables: string[]
  views: string[]
  functions: string[]
  columns: Record<string, string[]>
}>({ tables: [], views: [], functions: [], columns: {} })

const completions = computed(() => {
  const cache = schemaCache.value
  const items: { label: string; type: string; detail?: string }[] = []
  for (const t of cache.tables) items.push({ label: t, type: 'table' })
  for (const v of cache.views) items.push({ label: v, type: 'view' })
  for (const f of cache.functions) items.push({ label: f, type: 'function' })
  for (const [t, cols] of Object.entries(cache.columns)) {
    for (const c of cols) items.push({ label: c, type: 'column', detail: t })
  }
  return items
})

// 加载元数据用于补全
async function loadSchema() {
  if (!props.connId) return
  try {
    const { api } = await import('../api')
    const [tablesRes, viewsRes, funcRes] = await Promise.all([
      api.listTables(props.connId, props.dbName),
      api.listViews(props.connId, props.dbName),
      api.listFunctions(props.connId, props.dbName),
    ])
    const tables = (tablesRes.data || []).map((t: any) => t.name || t)
    const views = (viewsRes.data || []).map((v: any) => v.name || v)
    const functions = (funcRes.data || []).map((f: any) => f.name || f)
    const columns: Record<string, string[]> = {}
    // 取前 10 个表/视图的列名做补全
    const allObjects = [...tables, ...views].slice(0, 10)
    for (const t of allObjects) {
      try {
        const colRes: any = await api.getTableColumns(props.connId, t, props.dbName)
        if (colRes.success && colRes.data) {
          columns[t] = colRes.data.map((c: any) => c.Field || c.column_name || c.name)
        }
      } catch { /* ignore */ }
    }
    schemaCache.value = { tables, views, functions, columns }
  } catch { /* ignore */ }
}

onMounted(() => loadSchema())
watch(() => props.connId, () => loadSchema())

// 自动补全函数
function sqlCompletions(context: CompletionContext) {
  const word = context.matchBefore(/\w+/)
  if (!word || (word.from === word.to && !context.explicit)) return null

  const options = completions.value.map((c: { label: string; type: string; detail?: string }) => ({
    label: c.label,
    type: c.type === 'table' ? 'keyword' : 'variable',
    detail: c.type === 'column' ? c.detail : undefined,
    apply: c.label,
  }))

  // 添加 SQL 关键字
  const keywords = [
    'SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
    'TABLE', 'INTO', 'VALUES', 'SET', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
    'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'LIKE', 'BETWEEN', 'IS', 'NULL',
    'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'AS', 'DISTINCT', 'COUNT',
    'SUM', 'AVG', 'MIN', 'MAX', 'UNION', 'ALL', 'INDEX', 'VIEW', 'FUNCTION',
    'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES', 'CASCADE', 'DEFAULT', 'CHECK',
    'INT', 'INTEGER', 'VARCHAR', 'TEXT', 'BOOLEAN', 'FLOAT', 'DOUBLE', 'DECIMAL',
    'DATE', 'DATETIME', 'TIMESTAMP', 'CHAR', 'BLOB', 'ENUM', 'JSON',
  ]
  const prefix = word.text.toUpperCase()
  for (const kw of keywords) {
    if (kw.startsWith(prefix)) {
      options.push({ label: kw, type: 'keyword', detail: undefined, apply: kw })
    }
  }

  return { from: word.from, options }
}

// 快捷键：Ctrl+Enter / F5 执行 + 搜索（数组恒稳定，避免重初始化 CodeMirror）
const extensions = [
  sql({ dialect: MySQL }),
  oneDark,
  EditorView.lineWrapping,
  autocompletion({ override: [sqlCompletions] }),
  keymap.of([
    { key: 'Mod-Enter', run: () => { emit('execute'); return true } },
    { key: 'F5', run: () => { emit('execute'); return true } },
    ...searchKeymap,
    indentWithTab,
    ...defaultKeymap,
  ]),
]
</script>

<template>
  <codemirror
    :model-value="modelValue"
    :extensions="extensions"
    :style="{ height: '100%', minHeight: '120px', fontSize: '13px' }"
    :placeholder="'输入 SQL 语句... Ctrl+Enter 执行'"
    @update:model-value="(v: string) => emit('update:modelValue', v)"
    class="sql-cm-editor"
  />
</template>

<style scoped>
.sql-cm-editor {
  border: 1px solid #3c3c3c;
  border-radius: 4px;
  overflow: hidden;
}
.sql-cm-editor :deep(.cm-editor) {
  height: 100%;
}
.sql-cm-editor :deep(.cm-scroller) {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace !important;
  font-size: 13px !important;
}
.sql-cm-editor :deep(.cm-gutters) {
  background: var(--bg-sidebar);
  border-right: 1px solid var(--color-border);
}
</style>
