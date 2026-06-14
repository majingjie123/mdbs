<script setup lang="ts">
import { ref, watch } from 'vue'
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
const columns = ref<any[]>([])
const rowCount = ref(100)
const selectedTable = ref('')
const databases = ref<string[]>([])
const selectedDb = ref('')
const tables = ref<string[]>([])
const previewRows = ref<any[][]>([])
const previewLoading = ref(false)
const showPreview = ref(false)
const insertResult = ref<{ inserted: number } | null>(null)
const inserting = ref(false)

watch(() => props.visible, async (val) => {
  if (val) {
    insertResult.value = null
    previewRows.value = []
    showPreview.value = false
    selectedTable.value = props.tableName || ''
    selectedDb.value = props.dbName || ''
    rowCount.value = 100
    if (props.connId) {
      await loadDatabases()
      if (selectedDb.value) await loadTables()
    }
  }
})

async function loadDatabases() {
  if (!props.connId) return
  try {
    const res: any = await api.listDatabases(props.connId)
    if (res.success) databases.value = res.data || []
  } catch (e: any) {
    message.error('加载数据库列表失败: ' + e.message)
  }
}

async function loadTables() {
  if (!props.connId || !selectedDb.value) return
  try {
    const res: any = await api.listTables(props.connId, selectedDb.value)
    if (res.success) tables.value = (res.data || []).map((t: any) => typeof t === 'string' ? t : t.name)
  } catch (e: any) {
    message.error('加载表列表失败: ' + e.message)
  }
}

watch(selectedDb, () => {
  selectedTable.value = ''
  tables.value = []
  if (selectedDb.value) loadTables()
})

async function loadColumns() {
  if (!props.connId || !selectedTable.value) return
  loading.value = true
  try {
    const res: any = await api.getDataGenColumns(props.connId, selectedTable.value, selectedDb.value)
    if (res.success) {
      columns.value = res.data || []
    } else {
      message.warning(res.message || '获取字段信息失败')
    }
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

watch(selectedTable, (val) => {
  columns.value = []
  previewRows.value = []
  showPreview.value = false
  if (val) loadColumns()
})

async function doPreview() {
  if (!props.connId || !selectedTable.value) {
    message.warning('请选择表')
    return
  }
  if (rowCount.value < 1 || rowCount.value > 10000) {
    message.warning('行数须在 1~10000 之间')
    return
  }
  previewLoading.value = true
  showPreview.value = true
  try {
    const res: any = await api.dataGenPreview(props.connId, {
      table_name: selectedTable.value,
      row_count: rowCount.value,
      database: selectedDb.value,
    })
    if (res.success) {
      previewRows.value = res.data?.preview_rows || []
      columns.value = res.data?.columns || []
    } else {
      message.warning(res.message || '预览失败')
    }
  } catch (e: any) {
    message.error(e.message)
  } finally {
    previewLoading.value = false
  }
}

async function doInsert() {
  if (!props.connId || !selectedTable.value) {
    message.warning('请选择表')
    return
  }
  if (rowCount.value < 1 || rowCount.value > 100000) {
    message.warning('行数须在 1~100000 之间')
    return
  }
  inserting.value = true
  try {
    const res: any = await api.dataGenInsert(props.connId, {
      table_name: selectedTable.value,
      row_count: rowCount.value,
      database: selectedDb.value,
    })
    if (res.success && res.data) {
      insertResult.value = res.data
      message.success(res.message || `成功插入 ${res.data.inserted} 行`)
    } else {
      message.warning(res.message || '插入失败')
    }
  } catch (e: any) {
    message.error(e.message)
  } finally {
    inserting.value = false
  }
}

function mockTypeLabel(mt: string) {
  const map: Record<string, string> = {
    name: '姓名', email: '邮箱', phone: '手机号', city: '城市',
    company: '公司', url: '链接', ip: 'IP 地址', id_card: '身份证',
    sentence: '短文本', text: '长文本', int: '整数', decimal: '小数',
    date: '日期', datetime: '日期时间', time: '时间', boolean: '布尔',
    enum: '枚举', set: '集合', json: 'JSON', password: '密码', binary: '二进制',
  }
  return map[mt] || mt
}
</script>
<template>
  <n-modal
    :show="props.visible"
    @update:show="(v: boolean) => emit('update:visible', v)"
    :mask-closable="false"
    preset="card"
    style="width: 820px; max-height: 90vh;"
    title="📊 数据生成器"
    segmented
  >
    <template #header-extra>
      <n-tag type="info" size="small">模拟数据填充工具</n-tag>
    </template>

    <n-space vertical :size="16">
      <n-grid :cols="3" :x-gap="12">
        <n-gi>
          <n-form-item label="数据库">
            <n-select
              v-model:value="selectedDb"
              :options="databases.map(d => ({ label: d, value: d }))"
              filterable
              placeholder="选择数据库"
              :disabled="!!props.dbName"
            />
          </n-form-item>
        </n-gi>
        <n-gi>
          <n-form-item label="表">
            <n-select
              v-model:value="selectedTable"
              :options="tables.map(t => ({ label: t, value: t }))"
              filterable
              placeholder="选择表"
              :disabled="!!props.tableName"
            />
          </n-form-item>
        </n-gi>
        <n-gi>
          <n-form-item label="生成行数">
            <n-input-number
              v-model:value="rowCount"
              :min="1"
              :max="100000"
              :step="100"
              style="width: 100%"
            />
          </n-form-item>
        </n-gi>
      </n-grid>

      <n-card title="字段映射规则" size="small" v-if="columns.length > 0">
        <n-table :bordered="false" :single-line="false" size="small">
          <thead>
            <tr>
              <th>字段名</th>
              <th>类型</th>
              <th>模拟类型</th>
              <th>可空</th>
              <th>主键</th>
              <th>自增</th>
              <th>注释</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="col in columns" :key="col.field">
              <td><n-text code>{{ col.field }}</n-text></td>
              <td><n-tag size="small">{{ col.type }}</n-tag></td>
              <td>
                <n-tag :type="col.auto ? 'default' : 'success'" size="small">
                  {{ col.auto ? '—（自增）' : mockTypeLabel(col.mock_type) }}
                </n-tag>
              </td>
              <td>
                <n-tag :type="col.nullable ? 'warning' : 'info'" size="small">
                  {{ col.nullable ? '可空' : '非空' }}
                </n-tag>
              </td>
              <td>
                <n-tag v-if="col.key === 'PRI'" type="error" size="small">主键</n-tag>
                <span v-else>—</span>
              </td>
              <td>
                <n-tag v-if="col.auto" type="warning" size="small">自增</n-tag>
                <span v-else>—</span>
              </td>
              <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis;">{{ col.comment || '—' }}</td>
            </tr>
          </tbody>
        </n-table>
      </n-card>

      <n-collapse-transition :show="showPreview">
        <n-card title="数据预览" size="small" v-if="previewRows.length > 0">
          <template #header-extra>
            <n-tag type="primary" size="small">共 {{ rowCount }} 行（预览前 {{ previewRows.length }} 行）</n-tag>
          </template>
          <div style="max-height: 260px; overflow: auto;">
            <n-table :bordered="false" :single-line="false" size="tiny">
              <thead>
                <tr>
                  <th>#</th>
                  <th v-for="col in columns" :key="col.field">{{ col.field }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in previewRows" :key="ri">
                  <td>{{ ri + 1 }}</td>
                  <td v-for="(val, ci) in row" :key="ci">
                    <span v-if="val === null" style="color: #aaa;">NULL</span>
                    <span v-else-if="typeof val === 'object'">{{ JSON.stringify(val) }}</span>
                    <span v-else>{{ val }}</span>
                  </td>
                </tr>
              </tbody>
            </n-table>
          </div>
        </n-card>
      </n-collapse-transition>

      <n-alert v-if="insertResult" :type="insertResult.inserted > 0 ? 'success' : 'warning'" closable>
        <template #header>
          插入完成：共 {{ insertResult.inserted }} 行
        </template>
      </n-alert>
    </n-space>

    <template #footer>
      <n-space justify="space-between">
        <n-space>
          <n-button @click="emit('update:visible', false)">取消</n-button>
        </n-space>
        <n-space>
          <n-button
            @click="doPreview"
            :loading="previewLoading"
            :disabled="!selectedTable || loading"
            secondary
          >
            👁️ 预览数据
          </n-button>
          <n-button
            type="primary"
            @click="doInsert"
            :loading="inserting"
            :disabled="!selectedTable || loading"
          >
            🚀 生成并插入
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>
