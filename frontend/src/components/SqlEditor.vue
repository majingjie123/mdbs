<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { keymap } from '@codemirror/view'
import { sql, MySQL } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import { autocompletion, CompletionContext } from '@codemirror/autocomplete'
import { defaultKeymap, indentWithTab } from '@codemirror/commands'
import { searchKeymap } from '@codemirror/search'
import { format } from 'sql-formatter'

const props = withDefaults(defineProps<{
  modelValue: string
  connId?: number
  dbName?: string
  dbType?: string
}>(), {
  modelValue: '',
  dbType: 'MySQL',
})

const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
  (e: 'execute'): void
  (e: 'format'): void
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

    // 完整加载所有表/视图的列名
    const allObjects = [...tables, ...views]
    // 使用 Promise.all 并行加载，但限制并发数避免请求过多
    const batchSize = 5
    for (let i = 0; i < allObjects.length; i += batchSize) {
      const batch = allObjects.slice(i, i + batchSize)
      const results = await Promise.all(
        batch.map(async (t: string) => {
          try {
            const colRes: any = await api.getTableColumns(props.connId!, t, props.dbName)
            if (colRes.success && colRes.data) {
              return [t, colRes.data.map((c: any) => c.Field || c.column_name || c.name)] as [string, string[]]
            }
          } catch { /* ignore */ }
          return [t, []] as [string, string[]]
        })
      )
      for (const [table, cols] of results) {
        columns[table] = cols
      }
    }

    schemaCache.value = { tables, views, functions, columns }
  } catch { /* ignore */ }
}

// 解析当前光标前的文本，判断是否需要表名.列名补全
function parseTablePrefix(text: string): { table: string; prefix: string } | null {
  // 匹配 "表名." 后面的部分
  const match = text.match(/([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_]*)$/)
  if (match) {
    return { table: match[1], prefix: match[2] }
  }
  return null
}

onMounted(() => loadSchema())
watch(() => props.connId, () => loadSchema())

// 自动补全函数
function sqlCompletions(context: CompletionContext) {
  const cache = schemaCache.value

  // 获取当前光标前的文本
  const pos = context.pos
  const line = context.state.doc.lineAt(pos)
  const lineText = line.text.slice(0, pos - line.from)

  // 检查是否是表名.列名 的补全
  const tablePrefix = parseTablePrefix(lineText)
  if (tablePrefix && cache.columns[tablePrefix.table]) {
    const tableColumns = cache.columns[tablePrefix.table]
    const colPrefix = tablePrefix.prefix.toLowerCase()
    const options = tableColumns
      .filter(c => c.toLowerCase().startsWith(colPrefix))
      .map(c => ({
        label: c,
        type: 'variable' as const,
        detail: cache.tables.includes(tablePrefix.table) ? 'table' : 'view',
        apply: c,
      }))
    if (options.length > 0) {
      // 找到列名的起始位置（.之后）
      const dotIndex = lineText.lastIndexOf('.')
      return { from: line.from + dotIndex + 1, options }
    }
  }

  // 普通单词补全
  const word = context.matchBefore(/\w+/)
  if (!word || (word.from === word.to && !context.explicit)) return null

  const options: { label: string; type: string; detail?: string; apply: string }[] = []
  const items: { label: string; type: string; detail?: string }[] = []

  // 添加表名/视图名/函数名
  for (const t of cache.tables) items.push({ label: t, type: 'table' })
  for (const v of cache.views) items.push({ label: v, type: 'view' })
  for (const f of cache.functions) items.push({ label: f, type: 'function' })
  for (const [t, cols] of Object.entries(cache.columns)) {
    for (const c of cols) items.push({ label: c, type: 'column', detail: t })
  }

  const prefix = word.text.toLowerCase()
  for (const item of items) {
    if (item.label.toLowerCase().startsWith(prefix)) {
      options.push({
        label: item.label,
        type: item.type === 'table' ? 'keyword' : 'variable',
        detail: item.type === 'column' ? item.detail : undefined,
        apply: item.label,
      })
    }
  }

  // 添加 SQL 关键字
  const keywords = [
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'OFFSET',
    'INSERT INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE FROM', 'CREATE', 'ALTER', 'DROP',
    'TABLE', 'INDEX', 'VIEW', 'DATABASE', 'SCHEMA',
    'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN', 'FULL JOIN', 'CROSS JOIN',
    'ON', 'AS', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
    'UNION', 'ALL', 'EXISTS', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL', 'TRUE', 'FALSE',
    'PRIMARY KEY', 'FOREIGN KEY', 'REFERENCES', 'CASCADE', 'DEFAULT', 'CHECK', 'UNIQUE',
    'INT', 'INTEGER', 'BIGINT', 'SMALLINT', 'TINYINT',
    'VARCHAR', 'CHAR', 'TEXT', 'LONGTEXT', 'MEDIUMTEXT',
    'FLOAT', 'DOUBLE', 'DECIMAL', 'NUMERIC',
    'DATE', 'DATETIME', 'TIMESTAMP', 'TIME', 'YEAR',
    'BOOLEAN', 'BOOL', 'BLOB', 'JSON', 'ENUM',
    'ASC', 'DESC', 'NULLS FIRST', 'NULLS LAST',
    'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'IF', 'NULLIF', 'COALESCE', 'CONCAT', 'LENGTH', 'SUBSTRING', 'TRIM',
  ]
  for (const kw of keywords) {
    if (kw.toLowerCase().startsWith(prefix)) {
      options.push({ label: kw, type: 'keyword', detail: undefined, apply: kw })
    }
  }

  return { from: word.from, options }
}

// 快捷键：Ctrl+Enter / F5 执行 + 搜索（数组恒稳定，避免重初始化 CodeMirror）
const extensions = [
  sql({ dialect: MySQL }),
  oneDark,
  autocompletion({ override: [sqlCompletions] }),
  keymap.of([
    { key: 'Mod-Enter', run: () => { emit('execute'); return true } },
    { key: 'F5', run: () => { emit('execute'); return true } },
    { key: 'Mod-Shift-f', run: () => { handleFormat(); return true } },
    ...searchKeymap,
    indentWithTab,
    ...defaultKeymap,
  ]),
]

// SQL 格式化
function handleFormat() {
  if (!props.modelValue.trim()) return
  try {
    const language = props.dbType === 'PostgreSQL' ? 'postgresql' : 'mysql'
    const formatted = format(props.modelValue, {
      language,
      tabWidth: 2,
      keywordCase: 'upper',
      linesBetweenQueries: 2,
    })
    emit('update:modelValue', formatted)
    emit('format')
  } catch (e) {
    console.error('SQL格式化失败:', e)
  }
}

// 暴露格式化方法供外部调用
defineExpose({
  format: handleFormat,
})
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
