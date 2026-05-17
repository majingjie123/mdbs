<script setup lang="ts">
import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../../api'

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

// ── 选择文件 ──
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

function close() {
  emit('update:visible', false)
}

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
    <!-- 隐藏的文件 input -->
    <input
      ref="fileInputRef"
      type="file"
      :accept="importType === 'csv' ? '.csv' : '.sql'"
      style="display: none"
      @change="handleFileChange"
    />

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

    <n-alert type="warning" closable>
      导入功能需要连接到数据库执行，请确保文件内容安全可靠。建议先备份目标数据库。
    </n-alert>

    <template #footer>
      <n-space justify="end">
        <n-button @click="close">取消</n-button>
        <n-button type="primary" @click="doImport" :loading="loading">
          {{ importType === 'csv' && !parsedData ? '解析并导入' : '开始导入' }}
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>