<script setup lang="ts">
import { ref, watch, h } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../../api'
import { useTemplate } from '../../composables/useTemplate'

const props = defineProps<{
  visible: boolean
  connId?: number
  dbName?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const message = useMessage()
const loading = ref(false)
const parsedData = ref<any>(null)

// ── 导入模式：single / batch ──
// ── 模板管理 ──
const { templates, saveTemplate, deleteTemplate } = useTemplate('import')
const showTemplateSelector = ref(false)
const templateName = ref('')

function getCurrentConfig() {
  return {
    tab: dialogMode.value,
    importType: importType.value,
    encoding: encoding.value,
    targetTable: targetTable.value,
    importMode: importMode.value,
    ignoreErrors: ignoreErrors.value,
  }
}

function applyTemplate(tmpl: any) {
  if (!tmpl) return
  const d = tmpl.data || tmpl
  if (d.importType) importType.value = d.importType
  if (d.encoding) encoding.value = d.encoding
  if (d.targetTable) targetTable.value = d.targetTable
  if (d.importMode) importMode.value = d.importMode
  if (d.ignoreErrors !== undefined) ignoreErrors.value = d.ignoreErrors
  if (d.tab) dialogMode.value = d.tab
  showTemplateSelector.value = false
  message.success('已加载模板: ' + (tmpl.name || ''))
}

const dialogMode = ref<'single' | 'batch'>('single')

// ── 导入类型 ──
const importType = ref<'sql' | 'csv'>('csv')

// ── 文件上传 ──
const uploadedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

// ── CSV 导入选项 ──
const encoding = ref('utf8')
const ignoreErrors = ref(false)
const targetTable = ref('')
const importMode = ref<'append' | 'replace' | 'create'>('append')

const modeOptions = [
  { label: '追加数据', value: 'append', description: '向已有表追加数据' },
  { label: '替换数据', value: 'replace', description: '清空表后插入数据' },
  { label: '创建新表', value: 'create', description: '根据数据推断创建新表' },
]

// ── 预览数据 ──
const previewColumns = ref<string[]>([])
const previewRows = ref<any[][]>([])
const totalRows = ref(0)
const columnMapping = ref<Record<string, string>>({})

// ── 批量导入 ──
const batchFiles = ref<any[]>([])
const batchFileMappings = ref<Record<string, string>>({})
const batchFileModes = ref<Record<string, string>>({})
const batchFileInputRef = ref<HTMLInputElement | null>(null)
function triggerFileSelect() {
  fileInputRef.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    const file = input.files[0]
    // 校验扩展名
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (importType.value === 'csv' && ext !== 'csv') {
      message.warning('请选择 .csv 文件')
      return
    }
    if (importType.value === 'sql' && ext !== 'sql') {
      message.warning('请选择 .sql 文件')
      return
    }
    uploadedFile.value = file
    message.success(`已选择文件: ${file.name}`)
  }
  // 清空 input 以便重复选择同一文件
  input.value = ''
}

// ── 解析 CSV ──
async function parseCsvFile() {
  if (!uploadedFile.value || !props.connId) return

  loading.value = true
  parsedData.value = null
  previewColumns.value = []
  previewRows.value = []
  columnMapping.value = {}

  try {
    const formData = new FormData()
    formData.append('file', uploadedFile.value)
    formData.append('encoding', encoding.value)
    formData.append('conn_id', String(props.connId))

    const res: any = await api.importParse(formData)
    if (res.success && res.data) {
      parsedData.value = res.data
      previewColumns.value = res.data.columns || []
      previewRows.value = (res.data.preview_rows || []).slice(0, 10)
      totalRows.value = res.data.total_rows || 0

      // 初始化列映射（默认同名映射）
      const mapping: Record<string, string> = {}
      ;(res.data.columns || []).forEach((col: string) => {
        mapping[col] = col
      })
      columnMapping.value = mapping
      message.success(`解析完成，共 ${totalRows.value} 行数据`)
    } else {
      message.error(res.message || '解析失败')
    }
  } catch (e: any) {
    message.error(e.message || '解析文件失败')
  } finally {
    loading.value = false
  }
}

// ── 执行导入 ──
async function doImport() {
  if (!uploadedFile.value) {
    message.warning('请先选择文件')
    return
  }
  if (!props.connId) {
    message.warning('请先选择连接')
    return
  }

  loading.value = true

  try {
    if (importType.value === 'sql') {
      // SQL 文件：直接上传执行
      const formData = new FormData()
      formData.append('file', uploadedFile.value)
      formData.append('conn_id', String(props.connId))
      formData.append('encoding', encoding.value)
      formData.append('ignore_errors', String(ignoreErrors.value))
      if (props.dbName) formData.append('database', props.dbName)

      const res: any = await api.importSQL(formData)
      if (res.success) {
        message.success(res.message || 'SQL 导入成功')
      } else {
        throw new Error(res.message || '导入失败')
      }
    } else {
      // CSV 文件：需要先解析
      if (!parsedData.value) {
        // 未解析时先解析
        await parseCsvFile()
        if (!parsedData.value) return
      }

      if (!targetTable.value && importMode.value !== 'create') {
        message.warning('请输入目标表名')
        return
      }

      const res: any = await api.importExecute({
        conn_id: props.connId,
        database: props.dbName || null,
        file_path: parsedData.value.file_path,
        file_type: 'csv',
        table_name: targetTable.value || uploadedFile.value.name.replace(/\.csv$/i, ''),
        mode: importMode.value,
        encoding: encoding.value,
        ignore_errors: ignoreErrors.value,
        column_mapping: columnMapping.value,
      })
      if (res.success) {
        message.success(`导入完成，共处理 ${res.data?.imported_rows || 0} 行`)
      } else {
        throw new Error(res.message || '导入失败')
      }
    }
    emit('update:visible', false)
  } catch (e: any) {
    message.error(e.message || '导入失败')
  } finally {
    loading.value = false
  }
}

// ── 批量导入 ──
function triggerBatchFileSelect() {
  batchFileInputRef.value?.click()
}

function handleBatchFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    const files = Array.from(input.files)
    batchFiles.value.push(...files.map((f) => ({
      file: f,
      filename: f.name,
      status: 'pending' as 'pending' | 'parsed' | 'error',
      columns: [] as string[],
      preview_rows: [] as any[][],
      total_rows: 0,
      file_path: '',
      target_table: f.name.replace(/\.(csv|xlsx)$/i, '').replace(/[^a-zA-Z0-9_一-龥]/g, '_'),
    })))
  }
  input.value = ''
}

function removeBatchFile(index: number) {
  batchFiles.value.splice(index, 1)
}

async function parseAllBatchFiles() {
  if (!batchFiles.value.length) {
    message.warning('请先选择文件')
    return
  }
  loading.value = true
  try {
    const formData = new FormData()
    batchFiles.value.forEach((item) => {
      formData.append('files', item.file)
    })
    formData.append('encoding', 'utf-8')
    const res: any = await api.importBatchParse(formData)
    if (res.success && res.data?.files) {
      res.data.files.forEach((parsed: any, idx: number) => {
        if (idx < batchFiles.value.length) {
          if (parsed.success) {
            batchFiles.value[idx].status = 'parsed'
            batchFiles.value[idx].columns = parsed.columns || []
            batchFiles.value[idx].preview_rows = parsed.preview_rows || []
            batchFiles.value[idx].total_rows = parsed.total_rows || 0
            batchFiles.value[idx].file_path = parsed.file_path
            batchFiles.value[idx].target_table = parsed.default_table_name
          } else {
            batchFiles.value[idx].status = 'error'
            batchFiles.value[idx].error = parsed.message
          }
        }
      })
      message.success('文件解析完成')
    } else {
      message.error(res.message || '解析失败')
    }
  } catch (e: any) {
    message.error(e.message || '解析失败')
  } finally {
    loading.value = false
  }
}

async function doBatchImport() {
  if (!props.connId) {
    message.warning('请先选择连接')
    return
  }
  const items = batchFiles.value
    .filter((f) => f.status === 'parsed' && f.file_path)
    .map((f) => ({
      file_path: f.file_path,
      table_name: f.target_table,
      mode: batchFileModes.value[f.filename] || 'append',
    }))
  if (!items.length) {
    message.warning('没有可导入的文件，请先上传并解析')
    return
  }
  loading.value = true
  try {
    const res: any = await api.importBatchExecute({
      conn_id: props.connId,
      database: props.dbName || null,
      items,
      encoding: 'utf-8',
    })
    if (res.success) {
      message.success(res.message || '批量导入完成')
      emit('update:visible', false)
    } else {
      message.error(res.message || '批量导入失败')
    }
  } catch (e: any) {
    message.error(e.message || '批量导入失败')
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:visible', false)
}

watch(() => dialogMode.value, () => {
  // 切换到批量模式时重置
  if (dialogMode.value === 'batch') {
    batchFiles.value = []
    batchFileMappings.value = {}
    batchFileModes.value = {}
  }
})

watch(() => props.visible, (v) => {
  if (v) {
    // 重置状态
    uploadedFile.value = null
    parsedData.value = null
    previewColumns.value = []
    previewRows.value = []
    totalRows.value = 0
    columnMapping.value = {}
    targetTable.value = ''
    importMode.value = 'append'
  }
})

watch(importType, () => {
  uploadedFile.value = null
  parsedData.value = null
  previewColumns.value = []
  previewRows.value = []
})
</script>

<template>
  <n-modal
    :show="visible"
    @update:show="(v: boolean) => emit('update:visible', v)"
    :mask-closable="false"
    preset="card"
    title="导入数据"
    style="width: 680px"
    :bordered="true"
    :segmented="{ content: true }"
  >
    <!-- 隐藏的文件 input（单文件） -->
    <input
      ref="fileInputRef"
      type="file"
      :accept="importType === 'csv' ? '.csv' : '.sql'"
      style="display: none"
      @change="handleFileChange"
    />

    <!-- 隐藏的文件 input（批量） -->
    <input
      ref="batchFileInputRef"
      type="file"
      accept=".csv,.xlsx"
      multiple
      style="display: none"
      @change="handleBatchFileChange"
    />

    <n-tabs v-model:value="dialogMode" type="line" size="small" style="margin-bottom: 12px">
      <n-tab-pane name="single" tab="单文件导入">
        <n-form label-placement="left" label-width="100">
          <!-- 导入类型 -->
          <n-form-item label="导入类型">
            <n-radio-group v-model:value="importType">
              <n-radio-button value="sql">SQL 文件</n-radio-button>
              <n-radio-button value="csv">CSV 文件</n-radio-button>
            </n-radio-group>
          </n-form-item>

          <!-- 文件选择 -->
          <n-form-item label="选择文件">
            <n-space>
              <n-button @click="triggerFileSelect" :disabled="loading">选择文件</n-button>
              <span v-if="uploadedFile" style="line-height: 34px; color: #666">
                {{ uploadedFile.name }}
              </span>
              <span v-else style="line-height: 34px; color: #999">未选择文件</span>
            </n-space>
          </n-form-item>

          <!-- 字符编码 -->
          <n-form-item v-if="importType === 'csv'" label="字符编码">
            <n-select v-model:value="encoding" :options="[
              { label: 'UTF-8', value: 'utf8' },
              { label: 'UTF-8 BOM', value: 'utf-8-sig' },
              { label: 'GBK', value: 'gbk' },
              { label: 'Latin-1', value: 'latin1' },
            ]" />
          </n-form-item>

          <!-- 目标表名（CSV 模式） -->
      <template v-if="importType === 'csv'">
        <n-form-item label="目标表名">
          <n-input v-model:value="targetTable" placeholder="输入表名（创建/追加/替换）" />
        </n-form-item>
        <n-form-item label="导入模式">
          <n-radio-group v-model:value="importMode">
            <n-radio v-for="opt in modeOptions" :key="opt.value" :value="opt.value" :title="opt.description">
              {{ opt.label }}
            </n-radio>
          </n-radio-group>
        </n-form-item>
      </template>

      <!-- SQL 导入选项 -->
      <template v-if="importType === 'sql'">
        <n-form-item label="目标数据库">
          <n-input :value="dbName || '当前连接'" disabled />
        </n-form-item>
      </template>

      <!-- 忽略错误 -->
      <n-form-item label="忽略错误">
        <n-switch v-model:value="ignoreErrors" />
      </n-form-item>
    </n-form>

    <!-- 解析按钮（CSV） -->
    <div v-if="importType === 'csv' && uploadedFile && !parsedData" style="margin-bottom: 12px">
      <n-button @click="parseCsvFile" :loading="loading" secondary type="info">
        解析预览
      </n-button>
    </div>

    <!-- CSV 预览 -->
    <div v-if="previewColumns.length > 0" style="margin-bottom: 16px">
      <n-h5 style="margin: 0 0 8px">
        数据预览（前 {{ Math.min(previewRows.length, 10) }} 行 / 共 {{ totalRows }} 行）
      </n-h5>
      <n-data-table
        :columns="previewColumns.map(col => ({
          title: col,
          key: col,
          ellipsis: { tooltip: true },
          width: 120,
        }))"
        :data="previewRows.map((row, idx) => {
          const obj: Record<string, any> = { _index: idx }
          previewColumns.forEach((col, ci) => { obj[col] = row[ci] })
          return obj
        })"
        :max-height="300"
        size="small"
        bordered
      />
    </div>
    </n-tab-pane>

    <!-- 批量导入 -->
    <n-tab-pane name="batch" tab="批量导入">
      <n-space vertical>
        <n-space>
          <n-button @click="triggerBatchFileSelect" :disabled="loading">选择多个文件</n-button>
          <span style="line-height: 34px; color: #999">
            {{ batchFiles.length > 0 ? `已选择 ${batchFiles.length} 个文件` : '未选择文件' }}
          </span>
        </n-space>

        <n-data-table
          v-if="batchFiles.length > 0"
          :columns="[
            { title: '文件名', key: 'filename', ellipsis: true, width: 200 },
            { title: '状态', key: 'status', width: 80,
              render: (row: any) => {
                if (row.status === 'parsed') return h('span', { style: 'color:#18a058' }, '已解析')
                if (row.status === 'error') return h('span', { style: 'color:#d03050' }, '失败')
                return h('span', { style: 'color:#909399' }, '待解析')
              }
            },
            { title: '行数', key: 'total_rows', width: 60 },
            { title: '目标表名', key: 'target_table', width: 180,
              render: (row: any) => h('input', {
                value: row.target_table,
                style: 'width:100%;border:1px solid #d9d9d9;border-radius:3px;padding:2px 6px;font-size:12px',
                onInput: (e: any) => { row.target_table = e.target.value },
              })
            },
            { title: '操作', key: 'action', width: 60,
              render: (_: any, idx: number) => h('button', {
                style: 'color:#d03050;border:none;background:none;cursor:pointer',
                onClick: () => removeBatchFile(idx),
              }, '✕')
            },
          ]"
          :data="batchFiles"
          :max-height="250"
          size="small"
          bordered
          striped
        />

        <n-space v-if="batchFiles.length > 0">
          <n-button @click="parseAllBatchFiles" :loading="loading" secondary type="info">
            解析全部文件
          </n-button>
        </n-space>

        <template v-for="(f, idx) in batchFiles.filter((f: any) => f.status === 'parsed' && f.columns.length > 0)" :key="idx">
          <n-collapse>
            <n-collapse-item :title="`预览: ${f.filename}（${f.columns.join(', ')}...）`">
              <n-data-table
                :columns="f.columns.map((col: string) => ({ title: col, key: col, ellipsis: true, width: 120 }))"
                :data="f.preview_rows.map((row: any[], ri: number) => {
                  const obj: Record<string, any> = { _index: ri }
                  f.columns.forEach((col: string, ci: number) => { obj[col] = row[ci] })
                  return obj
                })"
                :max-height="200"
                size="small"
                bordered
              />
            </n-collapse-item>
          </n-collapse>
        </template>
      </n-space>
    </n-tab-pane>
  </n-tabs>

  <n-alert type="warning" closable>
    导入功能需要连接到数据库执行，请确保文件内容安全可靠。建议先备份目标数据库。
  </n-alert>

  <template #footer>
    <n-space justify="space-between">
      <n-space>
        <n-button size="small" quaternary @click="showTemplateSelector = !showTemplateSelector">
          📋 模板
        </n-button>
        <n-popover v-if="showTemplateSelector" trigger="manual" :show="showTemplateSelector" placement="top-start">
          <template #trigger>
            <span></span>
          </template>
          <n-space vertical size="small" style="max-width: 280px">
            <n-text depth="3" style="font-size: 12px">保存当前配置为模板</n-text>
            <n-input v-model:value="templateName" placeholder="模板名称" size="small" />
            <n-button size="tiny" type="primary" @click="saveTemplate(templateName, getCurrentConfig()); templateName = ''; message.success('模板已保存')">
              保存模板
            </n-button>
            <n-divider style="margin: 4px 0" />
            <n-text depth="3" style="font-size: 12px">加载已有模板</n-text>
            <n-data-table
              v-if="templates.length > 0"
              :columns="[
                { title: '名称', key: 'name', ellipsis: true },
                { title: '操作', key: 'action', width: 60,
                  render: (r: any) => h('span', [
                    h('n-button', { size: 'tiny', quaternary: true, type: 'info', onClick: () => applyTemplate(r) }, '载入'),
                    h('n-button', { size: 'tiny', quaternary: true, type: 'error', onClick: () => { deleteTemplate(r.id); message.success('已删除') } }, '✕'),
                  ]),
                },
              ]"
              :data="templates"
              size="small"
              :max-height="200"
            />
            <n-empty v-else description="暂无模板" style="font-size: 12px" />
          </n-space>
        </n-popover>
      </n-space>
      <n-space>
        <n-button @click="close">取消</n-button>
        <n-button v-if="dialogMode === 'single'" type="primary" @click="doImport" :loading="loading">
          {{ importType === 'csv' && !parsedData ? '解析并导入' : '开始导入' }}
        </n-button>
        <n-button v-else type="primary" @click="doBatchImport" :loading="loading">
          批量导入 ({{ batchFiles.filter((f: any) => f.status === 'parsed').length }})
        </n-button>
      </n-space>
    </n-space>
  </template>
</n-modal>
</template>