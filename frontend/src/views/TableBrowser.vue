<script setup lang="ts">
import { ref, onMounted, inject, h, computed } from 'vue'
import { api } from '../api'
import type { ColumnDetail } from '../api'
import { useAppStore } from '../stores/app'
import { useMessage, useDialog } from 'naive-ui'

const props = withDefaults(defineProps<{
  connId?: number
  tableName?: string
  dbName?: string
}>(), {
  connId: 0,
  tableName: '',
  dbName: '',
})

const store = useAppStore()
const message = useMessage()
const dialog = useDialog()
const statusText = inject('statusText', ref('就绪'))

// ── 数据状态 ─────────────────────────────────────
const columns = ref<ColumnDetail[]>([])
const editedColumns = ref<ColumnDetail[]>([])
const ddl = ref('')
const indexes = ref<any[]>([])
const editingIndexes = ref<any[]>([])
const loading = ref(false)
const activeTab = ref('columns')

// 字段编辑状态
const editCell = ref<{ row: number; col: string } | null>(null)
const editValue = ref('')
const alterPreview = ref('')
const showAlterPreview = ref(false)

// 表选项编辑
const optComment = ref('')
const optEngine = ref('')
const optCharset = ref('')
const optAutoInc = ref<number | null>(null)
const originalOptions = ref<Record<string, string>>({})

// ── 计算属性 ─────────────────────────────────────
const hasColumnEdits = computed(() => {
  if (columns.value.length !== editedColumns.value.length) return true
  return editedColumns.value.some((ec, i) => {
    const oc = columns.value[i]
    if (!oc) return true
    return ec.Field !== oc.Field || ec.Type !== oc.Type || ec.Default !== oc.Default || ec.Comment !== oc.Comment || ec.Null !== oc.Null
  })
})

const hasOptionsEdits = computed(() => {
  const orig = originalOptions.value
  return optComment.value !== (orig.Comment || '')
    || (optEngine.value || '') !== (orig.Engine || '')
    || (optCharset.value || '') !== (orig.Collation || '')
    || String(optAutoInc.value ?? '') !== (orig.Auto_increment || '')
})

// ── 字段编辑方法 ─────────────────────────────────
function startEdit(rowIdx: number, field: string, value: string) {
  editCell.value = { row: rowIdx, col: field }
  editValue.value = value
}

function commitEdit() {
  if (!editCell.value) return
  const { row, col } = editCell.value
  const target = editedColumns.value[row]
  if (!target) return
  ;(target as any)[col] = editValue.value
  editCell.value = null
  generateAlterPreview()
}

function onNullInput(e: Event) {
  editValue.value = (e.target as HTMLSelectElement).value
}

function addColumn() {
  editedColumns.value.push({
    Field: 'new_field',
    Type: 'VARCHAR(255)',
    Null: 'YES',
    Key: '',
    Default: null,
    Extra: '',
    Comment: '',
    Collation: '',
  })
  generateAlterPreview()
}

function removeColumn(idx: number) {
  const colName = editedColumns.value[idx]?.Field || ''
  dialog.warning({
    title: '确认删除',
    content: `确定删除字段 "${colName}" ？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => {
      editedColumns.value.splice(idx, 1)
      generateAlterPreview()
    },
  })
}

function moveColumn(idx: number, direction: number) {
  const newIdx = idx + direction
  if (newIdx < 0 || newIdx >= editedColumns.value.length) return
  const arr = editedColumns.value
  ;[arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]]
  generateAlterPreview()
}

function escId(name: string): string {
  return `\`${name.replace(/`/g, '``')}\``
}

function escVal(v: any): string {
  if (v === null || v === undefined) return 'NULL'
  return `'${String(v).replace(/'/g, "''")}'`
}

function generateAlterPreview() {
  const stmts: string[] = []
  let changes = 0
  for (let i = 0; i < Math.max(columns.value.length, editedColumns.value.length); i++) {
    if (changes >= 10) { stmts.push('-- ... 还有更多修改'); break }
    const orig = columns.value[i]
    const edit = editedColumns.value[i]
    if (!orig && edit) {
      const afterClause = i > 0 ? ` AFTER ${escId(editedColumns.value[i-1].Field)}` : ' FIRST'
      stmts.push(`ADD COLUMN ${escId(edit.Field)} ${edit.Type}${edit.Null === 'NO' ? ' NOT NULL' : ''}${edit.Default !== null ? ` DEFAULT ${escVal(edit.Default)}` : ''}${edit.Comment ? ` COMMENT ${escVal(edit.Comment)}` : ''}${afterClause}`)
      changes++
    } else if (orig && !edit) {
      stmts.push(`DROP COLUMN ${escId(orig.Field)}`)
      changes++
    } else if (orig && edit && (edit.Field !== orig.Field || edit.Type !== orig.Type || edit.Default !== orig.Default || edit.Comment !== orig.Comment || edit.Null !== orig.Null)) {
      stmts.push(`CHANGE COLUMN ${escId(orig.Field)} ${escId(edit.Field)} ${edit.Type}${edit.Null === 'NO' ? ' NOT NULL' : ''}${edit.Default !== null ? ` DEFAULT ${escVal(edit.Default)}` : ''}${edit.Comment ? ` COMMENT ${escVal(edit.Comment)}` : ''}`)
      changes++
    }
  }
  if (stmts.length === 0) {
    alterPreview.value = '-- 没有需要修改的字段'
  } else {
    alterPreview.value = `ALTER TABLE ${escId(props.tableName)}\n  ${stmts.join(',\n  ')};`
  }
  showAlterPreview.value = hasColumnEdits.value
}

function generateFullAlterSQL(): string[] {
  const sqls: string[] = []

  // 字段变更
  const fieldChanges: string[] = []
  for (let i = 0; i < Math.max(columns.value.length, editedColumns.value.length); i++) {
    const orig = columns.value[i]
    const edit = editedColumns.value[i]
    if (!orig && edit) {
      const afterClause = i > 0 ? ` AFTER ${escId(editedColumns.value[i-1].Field)}` : ' FIRST'
      fieldChanges.push(`ADD COLUMN ${escId(edit.Field)} ${edit.Type}${edit.Null === 'NO' ? ' NOT NULL' : ''}${edit.Default !== null ? ` DEFAULT ${escVal(edit.Default)}` : ''}${edit.Comment ? ` COMMENT ${escVal(edit.Comment)}` : ''}${afterClause}`)
    } else if (orig && !edit) {
      fieldChanges.push(`DROP COLUMN ${escId(orig.Field)}`)
    } else if (orig && edit && (edit.Field !== orig.Field || edit.Type !== orig.Type || edit.Default !== orig.Default || edit.Comment !== orig.Comment || edit.Null !== orig.Null)) {
      fieldChanges.push(`CHANGE COLUMN ${escId(orig.Field)} ${escId(edit.Field)} ${edit.Type}${edit.Null === 'NO' ? ' NOT NULL' : ''}${edit.Default !== null ? ` DEFAULT ${escVal(edit.Default)}` : ''}${edit.Comment ? ` COMMENT ${escVal(edit.Comment)}` : ''}`)
    }
  }
  if (fieldChanges.length > 0) {
    sqls.push(`ALTER TABLE ${escId(props.tableName)}\n  ${fieldChanges.join(',\n  ')};`)
  }

  // 选项变更
  const origOpts = originalOptions.value
  if (optComment.value !== (origOpts.Comment || '')) {
    sqls.push(`ALTER TABLE ${escId(props.tableName)} COMMENT = ${escVal(optComment.value)};`)
  }
  if (optEngine.value && optEngine.value !== (origOpts.Engine || '')) {
    sqls.push(`ALTER TABLE ${escId(props.tableName)} ENGINE = ${optEngine.value};`)
  }
  if (optCharset.value && optCharset.value !== (origOpts.Collation || '')) {
    sqls.push(`ALTER TABLE ${escId(props.tableName)} DEFAULT CHARSET = ${optCharset.value};`)
  }
  if (optAutoInc.value !== null && String(optAutoInc.value) !== (origOpts.Auto_increment || '')) {
    sqls.push(`ALTER TABLE ${escId(props.tableName)} AUTO_INCREMENT = ${optAutoInc.value};`)
  }
  return sqls
}

function previewFullSQL() {
  const sqls = generateFullAlterSQL()
  if (sqls.length === 0) {
    message.warning('没有检测到任何变更')
    return
  }
  alterPreview.value = sqls.join('\n\n')
showAlterPreview.value = true
}

async function saveColumnChanges() {
  if (!hasColumnEdits.value && !hasOptionsEdits.value) {
    message.warning('没有需要保存的修改')
    return
  }
  const sqls = generateFullAlterSQL()
  if (sqls.length === 0) {
    message.warning('没有检测到任何变更')
    return
  }
  dialog.info({
    title: '确认执行修改',
    content: `即将执行 ${sqls.length} 条 SQL 语句，确定要执行吗？`,
    positiveText: '确定执行',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        for (const sql of sqls) {
          const res: any = await api.executeSQL(props.connId, sql, props.dbName || undefined)
if (!res.success) {
            message.error('执行失败: ' + (res.message || '执行错误'))
            return
          }
        }
        message.success('表结构已更新')
        showAlterPreview.value = false
        await reload()
      } catch (e: any) {
        message.error('保存失败: ' + (e.message || '未知错误'))
      }
    },
  })
}

function renderEditableCell(rowIdx: number, field: string, value: any) {
  const isEditing = editCell.value?.row === rowIdx && editCell.value?.col === field
  if (isEditing) {
    return h('input', {
      value: editValue.value,
      onInput: (e: any) => { editValue.value = e.target.value },
      onBlur: () => commitEdit(),
      onKeydown: (e: any) => {
        if (e.key === 'Enter') commitEdit()
        if (e.key === 'Escape') editCell.value = null
      },
      style: { width: '100%', border: '2px solid #3498db', background: '#2a2a2a', color: '#e0e0e0', padding: '2px 4px', borderRadius: '2px', outline: 'none', fontSize: '13px' },
      autofocus: '',
    })
  }
  const orig = columns.value[rowIdx]
  const edit = editedColumns.value[rowIdx]
  const isChanged = !!orig && !!edit && (edit as any)[field] !== (orig as any)[field]
  return h('span', {
    onDblclick: () => startEdit(rowIdx, field, String(value ?? '')),
    style: { cursor: 'text', background: isChanged ? '#2d4a2d' : 'transparent', padding: '2px 4px', display: 'block', minHeight: '22px' },
    title: isChanged ? `原值: ${orig ? (orig as any)[field] : '—'}` : (value === null ? 'NULL' : String(value)),
  }, value === null ? 'NULL' : String(value))
}

// ── 数据预览 ─────────────────────────────────────
const previewRows = ref<any[][]>([])
const previewCols = ref<string[]>([])
const previewLoading = ref(false)

const previewScrollX = computed(() => {
  if (!previewCols.value.length) return 0
  return Math.max(previewCols.value.length * 160, 600)
})

async function loadPreview() {
  previewLoading.value = true
  try {
    const res: any = await api.executeSQL(props.connId, `SELECT * FROM \`${props.tableName}\` LIMIT 100`, props.dbName || undefined)
    if (res.success && res.data) {
      previewCols.value = res.data.columns || []
      previewRows.value = res.data.rows || []
    }
  } finally {
    previewLoading.value = false
  }
}

// ── 解析 DDL 中的表选项 ──────────────────────────
function parseTableOptions(sql: string) {
  const opts: Record<string, string> = {}
  const engineMatch = sql.match(/ENGINE\s*=\s*(\w+)/i)
  if (engineMatch) opts.Engine = engineMatch[1]
  const charsetMatch = sql.match(/DEFAULT CHARSET\s*=\s*(\w+)/i)
  if (charsetMatch) opts.Collation = charsetMatch[1]
  const autoIncMatch = sql.match(/AUTO_INCREMENT\s*=\s*(\d+)/i)
  if (autoIncMatch) opts.Auto_increment = autoIncMatch[1]
  const commentMatch = sql.match(/COMMENT\s*=\s*'([^']+)'/i)
  if (commentMatch) opts.Comment = commentMatch[1]
  originalOptions.value = opts
  optComment.value = opts.Comment || ''
  optEngine.value = opts.Engine || ''
  optCharset.value = opts.Collation || ''
  optAutoInc.value = opts.Auto_increment ? Number(opts.Auto_increment) : null
}

// ── 工具栏动作 ────────────────────────────────────
function newQuery() {
  store.openTab('sql-workbench', `查询 - ${props.tableName}`, { connId: props.connId, dbName: props.dbName, initialSql: `SELECT * FROM \`${props.tableName}\` LIMIT 100` })
}

function copyName() {
  navigator.clipboard.writeText(props.tableName)
}

function generateSelect() {
  const cols = columns.value.map(c => `\`${c.Field}\``).join(', ')
  navigator.clipboard.writeText(`SELECT ${cols} FROM \`${props.tableName}\` LIMIT 100`)
}

function copyDDL() {
  navigator.clipboard.writeText(ddl.value)
}

function openWorkbench() {
  store.openTab('sql-workbench', 'SQL 工作台', { connId: props.connId, dbName: props.dbName })
}

// ── 全部刷新 ───────────────────────────────────────
async function reload() {
  loading.value = true
  statusText.value = `加载表 ${props.tableName} 信息...`
  try {
    const [colRes, ddlRes, idxRes] = await Promise.all([
      api.getTableColumns(props.connId, props.tableName, props.dbName || undefined),
      api.getTableDDL(props.connId, props.tableName, props.dbName || undefined),
      api.getTableIndexes(props.connId, props.tableName, props.dbName || undefined),
    ])
    if (colRes.success && colRes.data) {
      columns.value = colRes.data
      editedColumns.value = colRes.data.map((c: ColumnDetail) => ({ ...c }))
    }
    if (ddlRes.success && ddlRes.data) {
      ddl.value = ddlRes.data
      parseTableOptions(ddlRes.data)
    }
    if (idxRes.success && idxRes.data) {
      indexes.value = idxRes.data
      editingIndexes.value = idxRes.data.map((i: any) => ({ ...i }))
    }
    statusText.value = `表 ${props.tableName} 已加载`
    await loadPreview()
  } catch (e) {
    statusText.value = `加载表 ${props.tableName} 失败`
  } finally {
    loading.value = false
  }
}

// ── 索引编辑 ─────────────────────────────────────
function addIndex() {
  editingIndexes.value.push({
    Key_name: 'idx_new',
    Column_name: '',
    Non_unique: 1,
    Seq_in_index: 1,
    Index_type: 'BTREE',
    Comment: '',
  })
}

function removeIndex(idx: number) {
  editingIndexes.value.splice(idx, 1)
}

function saveIndexChanges() {
  const sqls: string[] = []
  for (const orig of indexes.value) {
    if (!editingIndexes.value.find((e: any) => e.Key_name === orig.Key_name)) {
      sqls.push(`ALTER TABLE \`${props.tableName}\` DROP INDEX \`${orig.Key_name}\`;`)
    }
  }
  for (const edit of editingIndexes.value) {
    if (!indexes.value.find((i: any) => i.Key_name === edit.Key_name)) {
      const unique = edit.Non_unique === 0 ? 'UNIQUE ' : ''
      sqls.push(`ALTER TABLE \`${props.tableName}\` ADD ${unique}INDEX \`${edit.Key_name}\` (\`${edit.Column_name}\`);`)
    }
  }
  if (sqls.length === 0) {
    message.warning('没有索引变更')
    return
  }
  dialog.info({
    title: '确认执行索引修改',
    content: `即将执行 ${sqls.length} 条 SQL：\n${sqls.join('\n')}`,
    positiveText: '确定执行',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        for (const sql of sqls) {
          const res: any = await api.executeSQL(props.connId, sql, props.dbName || undefined)
          if (!res.success) {
            message.error('索引修改失败: ' + (res.message || ''))
            return
          }
        }
        message.success('索引已更新')
        await reload()
      } catch (e: any) {
        message.error('保存失败: ' + (e.message || ''))
      }
    },
  })
}

// ── 复制列名 ─────────────────────────────────────
function copyColumn(name: string) {
  navigator.clipboard.writeText(name)
}

// ── 初始化 ───────────────────────────────────────
onMounted(() => {
  reload()
})
</script>

<template>
  <div class="page">
    <!-- 表头工具栏 -->
    <div class="page-header">
      <div class="page-title">
        <h2>{{ props.tableName }}</h2>
        <n-tag v-if="props.dbName" type="info" size="small">{{ props.dbName }}</n-tag>
      </div>
      <n-space size="small">
        <n-button size="tiny" @click="reload">刷新</n-button>
        <n-button size="tiny" @click="newQuery">新建查询</n-button>
        <n-button size="tiny" @click="copyName">复制表名</n-button>
        <n-button size="tiny" @click="generateSelect">生成 SELECT</n-button>
        <n-button size="tiny" @click="copyDDL">复制 DDL</n-button>
        <n-button size="tiny" @click="openWorkbench">SQL 工作台</n-button>
      </n-space>
    </div>

    <n-tabs v-model:value="activeTab" type="line">
      <!-- ═══════ 字段标签页 ═══════ -->
      <n-tab-pane name="columns" tab="字段">
        <div class="columns-toolbar">
          <n-space size="small">
            <n-button size="tiny" type="primary" @click="addColumn">+ 添加字段</n-button>
            <n-button v-if="hasColumnEdits" size="tiny" type="warning" @click="saveColumnChanges">保存修改</n-button>
            <n-button size="tiny" type="info" @click="previewFullSQL">预览 SQL</n-button>
          </n-space>
          <n-button v-if="showAlterPreview" size="tiny" @click="showAlterPreview = !showAlterPreview">
            {{ showAlterPreview ? '隐藏' : '显示' }} ALTER SQL
          </n-button>
        </div>
        <n-alert v-if="showAlterPreview" type="info" closable @close="showAlterPreview = false" :style="{ marginBottom: '8px' }">
          <pre class="alter-preview">{{ alterPreview }}</pre>
        </n-alert>
        <n-data-table
          :columns="[
            { title: '字段名', key: 'Field', width: 160,
              render: (r: ColumnDetail, ri: number) => renderEditableCell(ri, 'Field', r.Field)
            },
            { title: '类型', key: 'Type', width: 180,
              render: (r: ColumnDetail, ri: number) => renderEditableCell(ri, 'Type', r.Type)
            },
            { title: '排序规则', key: 'Collation', width: 140,
              render: (r: ColumnDetail, ri: number) => renderEditableCell(ri, 'Collation', r.Collation ?? '')
            },
            { title: '允许NULL', key: 'Null', width: 90,
              render: (r: ColumnDetail, ri: number) => {
                const editing = editCell?.row === ri && editCell?.col === 'Null'
                if (editing) {
                  return h('select', {
                    value: editValue,
                    onInput: onNullInput,
                    onChange: () => commitEdit(),
                    onBlur: () => commitEdit(),
                    style: { width: '100%', border: '2px solid #3498db', background: '#2a2a2a', color: '#e0e0e0', padding: '2px', borderRadius: '2px', outline: 'none', fontSize: '13px' },
                  }, [
                    h('option', { value: 'YES' }, 'YES'),
                    h('option', { value: 'NO' }, 'NO'),
                  ])
                }
                return h('span', {
                  onDblclick: () => startEdit(ri, 'Null', r.Null),
                  style: { cursor: 'text', padding: '2px 4px', display: 'block', minHeight: '22px', color: r.Null === 'NO' ? '#6a9955' : '#e0e0e0' },
                }, r.Null)
              }
            },
            { title: '键', key: 'Key', width: 70,
              render: (r: ColumnDetail) => r.Key ? h('n-tag', { size: 'tiny', type: r.Key === 'PRI' ? 'error' : r.Key === 'UNI' ? 'warning' : 'info' }, r.Key) : '-'
            },
            { title: '默认值', key: 'Default', width: 120,
              render: (r: ColumnDetail, ri: number) => renderEditableCell(ri, 'Default', r.Default)
            },
            { title: '额外', key: 'Extra', width: 100,
              render: (r: ColumnDetail) => r.Extra ? h('n-tag', { size: 'tiny', type: 'success' }, r.Extra) : '-'
            },
            { title: '注释', key: 'Comment',
              render: (r: ColumnDetail, ri: number) => renderEditableCell(ri, 'Comment', r.Comment ?? '')
            },
            { title: '操作', key: '_actions', width: 140,
              render: (r: ColumnDetail, ri: number) => h('div', { style: 'display:flex;gap:4px' }, [
                h('n-button', { size: 'tiny', onClick: () => moveColumn(ri, -1), disabled: ri === 0 }, '↑'),
                h('n-button', { size: 'tiny', onClick: () => moveColumn(ri, 1), disabled: ri === editedColumns.length - 1 }, '↓'),
                h('n-button', { size: 'tiny', type: 'error', onClick: () => removeColumn(ri), disabled: columns.length <= 1 }, '删除'),
              ])
            },
          ]"
          :data="editedColumns"
          :loading="loading"
          :bordered="true"
          striped
        />
      </n-tab-pane>

      <!-- ═══════ 索引标签页 ═══════ -->
      <n-tab-pane name="indexes" tab="索引">
        <div class="columns-toolbar">
          <n-space size="small">
            <n-button size="tiny" type="primary" @click="addIndex">+ 添加索引</n-button>
            <n-button size="tiny" type="warning" @click="saveIndexChanges">保存索引</n-button>
          </n-space>
        </div>
        <n-data-table
          :columns="[
            { title: '索引名', key: 'Key_name', width: 160 },
            { title: '字段', key: 'Column_name', width: 160,
              render: (r: any) => h('span', {
                style: { cursor: 'pointer', color: '#7ec8e3' },
                onClick: () => copyColumn(r.Column_name),
                title: '点击复制'
              }, r.Column_name)
            },
            { title: '唯一', key: 'Non_unique', width: 70,
              render: (r: any) => h('n-tag', { size: 'tiny', type: r.Non_unique === 0 ? 'success' : 'default' }, r.Non_unique === 0 ? '是' : '否')
            },
            { title: '顺序', key: 'Seq_in_index', width: 60 },
            { title: '基数', key: 'Cardinality', width: 80 },
            { title: '类型', key: 'Index_type', width: 100 },
            { title: '注释', key: 'Comment' },
            { title: '操作', key: '_actions', width: 60,
              render: (r: any, ri: number) => h('n-button', {
                size: 'tiny',
                type: 'error',
                onClick: () => removeIndex(ri),
              }, '删除')
            },
          ]"
          :data="editingIndexes"
          :loading="loading"
          :bordered="true"
          striped
        />
      </n-tab-pane>

      <!-- ═══════ 选项标签页 ═══════ -->
      <n-tab-pane name="options" tab="选项">
        <div class="options-form">
          <div class="option-row">
            <label>表注释：</label>
            <n-input v-model:value="optComment" placeholder="表注释" size="small" />
          </div>
          <div class="option-row">
            <label>引擎：</label>
            <n-select v-model:value="optEngine" placeholder="存储引擎" size="small" style="width:200px" :options="[
              { label: 'InnoDB', value: 'InnoDB' },
              { label: 'MyISAM', value: 'MyISAM' },
              { label: 'MEMORY', value: 'MEMORY' },
            ]" />
          </div>
          <div class="option-row">
            <label>字符集：</label>
            <n-select v-model:value="optCharset" placeholder="字符集" size="small" style="width:200px" :options="[
              { label: 'utf8mb4', value: 'utf8mb4' },
              { label: 'utf8', value: 'utf8' },
              { label: 'latin1', value: 'latin1' },
            ]" />
          </div>
          <div class="option-row">
            <label>自增起始：</label>
            <n-input-number v-model:value="optAutoInc" placeholder="自增值" size="small" :min="0" style="width:200px" />
          </div>
          <div v-if="hasOptionsEdits" class="option-row" style="margin-top:16px">
            <n-button type="warning" size="small" @click="saveColumnChanges">保存选项修改</n-button>
          </div>
        </div>
      </n-tab-pane>

      <!-- ═══════ DDL 标签页 ═══════ -->
      <n-tab-pane name="ddl" tab="DDL">
        <div style="margin-bottom:8px">
          <n-button size="tiny" @click="copyDDL">复制 DDL</n-button>
        </div>
        <n-code :code="ddl" language="sql" />
      </n-tab-pane>

      <!-- ═══════ 数据预览标签页 ═══════ -->
      <n-tab-pane name="preview" tab="数据预览">
        <n-data-table
          :scroll-x="previewScrollX"
          :columns="previewCols.map(col => ({
            title: col,
            key: col,
            width: 160,
            ellipsis: { tooltip: true },
            render: (row: any) => String(row[col] ?? ''),
          }))"
          :data="previewRows.map((row: any[]) => {
            const obj: any = {}
            previewCols.forEach((col, ci) => { obj[col] = row[ci] })
            return obj
          })"
          :loading="previewLoading"
          :bordered="true"
          striped
          :max-height="600"
          virtual-scroll
        />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.page {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title h2 {
  color: #e0e0e0;
  font-size: 20px;
  margin: 0;
}
.columns-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.alter-preview {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  margin: 0;
}
.options-form {
  padding: 20px;
  max-width: 500px;
}
.option-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  gap: 12px;
}
.option-row label {
  min-width: 80px;
  color: #e0e0e0;
  font-size: 14px;
  text-align: right;
}
</style>