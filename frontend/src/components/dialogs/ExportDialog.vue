<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { api } from '../../api'

const props = defineProps<{
  visible: boolean
  connId?: number
  dbName?: string
  tableName?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const message = useMessage()
const loading = ref(false)
const activeTab = ref('structure')

// ── 导出格式 ──
const structureFormat = ref('excel')
const erFormat = ref('html')
const dataFormat = ref('csv')

const structureFormatOptions = [
  { label: 'Excel (.xlsx)', value: 'excel' },
  { label: 'PDF', value: 'pdf' },
  { label: 'HTML', value: 'html' },
  { label: 'Markdown', value: 'markdown' },
]
const dataFormatOptions = [
  { label: 'CSV', value: 'csv' },
  { label: 'Excel (.xlsx)', value: 'excel' },
]

// ── 选项 ──
const includeDropTable = ref(false)
const includeIfNotExists = ref(false)
const selectedTables = ref<string[]>([])
const tableOptions = ref<{ label: string; value: string }[]>([])
const includeRelations = ref(true)
const showComments = ref(true)
const includeData = ref(true)

// ── 加载表列表 ──
async function loadTables() {
  if (!props.connId) return
  try {
    const res: any = await api.listTables(props.connId, props.dbName)
    if (res.success && res.data) {
      tableOptions.value = res.data.map((t: any) => ({
        label: t.comment ? `${t.name} (${t.comment})` : t.name,
        value: t.name,
      }))
    }
  } catch {
    tableOptions.value = []
  }
}

watch(() => props.visible, (v) => {
  if (v) loadTables()
})

// ── 文件下载 ──
async function downloadBlob(url: string, body: any, filename: string) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = '导出失败'
    try {
      const err = await res.json()
      detail = err.detail || detail
    } catch {}
    throw new Error(detail)
  }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

// ── 执行导出 ──
async function doExport() {
  if (!props.connId) {
    message.warning('请先选择连接')
    return
  }

  loading.value = true
  const baseUrl = '/api'

  try {
    if (activeTab.value === 'structure') {
      const params = {
        conn_id: props.connId,
        database: props.dbName || null,
        format: structureFormat.value,
        tables: selectedTables.value,
        drop_table: includeDropTable.value,
        if_not_exists: includeIfNotExists.value,
      }
      const extMap: Record<string, string> = { excel: 'xlsx', pdf: 'pdf', html: 'html', markdown: 'md' }
      const ext = extMap[structureFormat.value] || 'xlsx'
      await downloadBlob(`${baseUrl}/export/structure`, params, `table_structure.${ext}`)
      message.success('表结构导出成功')
    } else if (activeTab.value === 'er') {
      const params = {
        conn_id: props.connId,
        database: props.dbName || null,
        format: erFormat.value,
        include_relations: includeRelations.value,
        show_comments: showComments.value,
      }
      const extMap: Record<string, string> = { html: 'html', pdf: 'pdf', excel: 'xlsx', markdown: 'md' }
      const ext = extMap[erFormat.value] || 'html'
      await downloadBlob(`${baseUrl}/export/er`, params, `er_diagram.${ext}`)
      message.success('ER 图导出成功')
    } else if (activeTab.value === 'data') {
      if (!props.tableName) {
        message.warning('请先选择要导出的表')
        return
      }
      const params = {
        conn_id: props.connId,
        database: props.dbName || null,
        table: props.tableName,
        format: dataFormat.value,
        include_data: includeData.value,
      }
      const ext = dataFormat.value === 'csv' ? 'csv' : 'xlsx'
      await downloadBlob(`${baseUrl}/export/data`, params, `data_${props.tableName}.${ext}`)
      message.success('数据导出成功')
    } else if (activeTab.value === 'navicat') {
      // 导出所有连接（当前连接）
      const params = { conn_ids: [props.connId] }
      await downloadBlob(`${baseUrl}/export/navicat`, params, `navicat_connections.ncx`)
      message.success('Navicat 配置导出成功')
    }
    emit('update:visible', false)
  } catch (e: any) {
    message.error(e.message || '导出失败')
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:visible', false)
}
</script>

<template>
  <n-modal
    :show="visible"
    @update:show="(v: boolean) => emit('update:visible', v)"
    :mask-closable="false"
    preset="card"
    title="导出"
    style="width: 600px"
    :bordered="true"
    :segmented="{ content: true }"
  >
    <n-tabs v-model:value="activeTab" type="line">
      <!-- 导出表结构 -->
      <n-tab-pane name="structure" tab="导出表结构">
        <n-form label-placement="left" label-width="110">
          <n-form-item label="导出格式">
            <n-select v-model:value="structureFormat" :options="structureFormatOptions" />
          </n-form-item>
          <n-form-item label="包含 DROP TABLE">
            <n-switch v-model:value="includeDropTable" />
          </n-form-item>
          <n-form-item label="IF NOT EXISTS">
            <n-switch v-model:value="includeIfNotExists" />
          </n-form-item>
          <n-form-item label="选择表（可选）">
            <n-transfer
              v-model:value="selectedTables"
              :options="tableOptions"
              style="width: 100%"
            />
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <!-- 导出 ER 图 -->
      <n-tab-pane name="er" tab="导出 ER 图">
        <n-alert type="info" closable>
          ER 图将使用 Mermaid 格式生成交互式 HTML 文件。
        </n-alert>
        <n-form label-placement="left" label-width="100" style="margin-top: 16px">
          <n-form-item label="导出格式">
            <n-select v-model:value="erFormat" :options="[
              { label: 'HTML（推荐）', value: 'html' },
              { label: 'PDF', value: 'pdf' },
              { label: 'Excel', value: 'excel' },
              { label: 'Markdown', value: 'markdown' },
            ]" />
          </n-form-item>
          <n-form-item label="包含外键关系">
            <n-switch v-model:value="includeRelations" />
          </n-form-item>
          <n-form-item label="显示列注释">
            <n-switch v-model:value="showComments" />
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <!-- 导出数据 -->
      <n-tab-pane name="data" tab="导出数据">
        <n-form label-placement="left" label-width="100">
          <n-form-item label="导出格式">
            <n-select v-model:value="dataFormat" :options="dataFormatOptions" />
          </n-form-item>
          <n-form-item label="导出表">
            <n-input :value="tableName || '（未选择）'" disabled />
          </n-form-item>
          <n-form-item label="包含数据">
            <n-switch v-model:value="includeData" />
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <!-- 导出 Navicat -->
      <n-tab-pane name="navicat" tab="导出 Navicat">
        <n-alert type="info" closable>
          导出为 Navicat (.ncx) 格式，兼容 Navicat 导入功能。将导出当前连接配置。
        </n-alert>
      </n-tab-pane>
    </n-tabs>

    <template #footer>
      <n-space justify="end">
        <n-button @click="close">取消</n-button>
        <n-button type="primary" @click="doExport" :loading="loading">导出</n-button>
      </n-space>
    </template>
  </n-modal>
</template>