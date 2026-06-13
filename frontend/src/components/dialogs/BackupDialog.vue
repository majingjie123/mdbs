<script setup lang="ts">
import { ref, watch, h } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
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
const dialog = useDialog()
const showPreview = ref(false)
const previewData = ref<any>(null)
const previewLoading = ref(false)
const loading = ref(false)
const activeTab = ref('backup')

// ── 备份 ──
const backupDb = ref('')
const backupOptions = ref<string[]>(['structure', 'data'])

const allOptions = [
  { label: '表结构', value: 'structure' },
  { label: '数据', value: 'data' },
  { label: '视图', value: 'views' },
  { label: '函数/存储过程', value: 'functions' },
  { label: '触发器', value: 'triggers' },
  { label: '事件', value: 'events' },
]

async function doBackup() {
  const cid = props.connId
  if (!cid) {
    message.warning('请先选择连接')
    return
  }

  loading.value = true
  try {
    const res: any = await api.backupCreate(cid, {
      database: backupDb.value || props.dbName || '',
      options: backupOptions.value,
    })
    if (res.success) {
      const data = res.data || {}
      message.success(`备份成功: ${data.file_path || ''}`)
      loadBackupList()
      emit('update:visible', false)
    } else {
      message.error(res.message || '备份失败')
    }
  } catch (e: any) {
    message.error(e.message || '备份失败')
  } finally {
    loading.value = false
  }
}

// ── 恢复 ──
const backupFiles = ref<any[]>([])
const selectedBackup = ref<string | null>(null)
const restoreDb = ref('')

const fileColumns = [
  { title: '文件名', key: 'name', width: 200 },
  { title: '大小', key: 'size_display', width: 80 },
  { title: '日期', key: 'date', width: 140 },
  {
    title: '操作', key: 'actions', width: 130,
    render: (r: any) => h('span', [
      h('n-button', {
        size: 'tiny',
        quaternary: true,
        type: 'info',
        style: 'margin-right: 4px',
        onClick: () => previewBackup(r.name),
      }, '预览'),
      h('n-button', {
        size: 'tiny',
        quaternary: true,
        type: 'error',
        onClick: () => deleteBackup(r.name),
      }, '删除'),
    ]),
  },
]

async function loadBackupList() {
  const cid = props.connId
  if (!cid) return
  try {
    const res: any = await api.backupList(cid)
    if (res.success && res.data) {
      backupFiles.value = res.data.map((f: any) => ({
        ...f,
        size_display: f.size_display || `${(f.size / 1024).toFixed(1)} KB`,
      }))
    }
  } catch {
    backupFiles.value = []
  }
}

async function doRestore() {
  const cid = props.connId
  if (!selectedBackup.value) {
    message.warning('请选择要恢复的备份文件')
    return
  }
  if (!cid) {
    message.warning('请先选择连接')
    return
  }

  dialog.warning({
    title: '确认恢复',
    content: '恢复操作将覆盖目标数据库数据，不可撤销！确认继续？',
    positiveText: '确认恢复',
    negativeText: '取消',
    onPositiveClick: async () => {
      loading.value = true
      try {
        const res: any = await api.backupRestore(cid, {
          file_path: selectedBackup.value,
          database: restoreDb.value || props.dbName || '',
        })
        if (res.success) {
          message.success(res.message || '恢复完成')
          emit('update:visible', false)
        } else {
          message.error(res.message || '恢复失败')
        }
      } catch (e: any) {
        message.error(e.message || '恢复失败')
      } finally {
        loading.value = false
      }
    },
  })
}

// ── 删除备份 ──
async function deleteBackup(name: string) {
  dialog.warning({
    title: '确认删除',
    content: `确定删除备份文件 "${name}"？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res: any = await api.backupDelete(name)
        if (res.success) {
          message.success('删除成功')
          loadBackupList()
        } else {
          message.error(res.message || '删除失败')
        }
      } catch (e: any) {
        message.error(e.message || '删除失败')
      }
    },
  })
}

// ── 预览备份 ──
async function previewBackup(name: string) {
  previewLoading.value = true
  showPreview.value = true
  previewData.value = null
  try {
    const res: any = await api.backupPreview(name)
    if (res.success) {
      previewData.value = res.data
    } else {
      message.error(res.message || '预览失败')
      showPreview.value = false
    }
  } catch (e: any) {
    message.error(e.message || '预览失败')
    showPreview.value = false
  } finally {
    previewLoading.value = false
  }
}

watch(() => props.visible, (v) => {
  if (v) {
    backupDb.value = props.dbName || ''
    restoreDb.value = props.dbName || ''
    loadBackupList()
  }
})

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
    title="备份 / 恢复"
    style="width: 640px"
    :bordered="true"
    :segmented="{ content: true }"
  >
    <n-tabs v-model:value="activeTab" type="line">
      <!-- 备份 -->
      <n-tab-pane name="backup" tab="备份">
        <n-form label-placement="left" label-width="110">
          <n-form-item label="数据库">
            <n-input v-model:value="backupDb" :placeholder="props.dbName || '默认数据库'" />
          </n-form-item>
          <n-form-item label="备份内容">
            <n-checkbox-group v-model:value="backupOptions">
              <n-space>
                <n-checkbox v-for="opt in allOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </n-checkbox>
              </n-space>
            </n-checkbox-group>
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <!-- 恢复 -->
      <n-tab-pane name="restore" tab="恢复">
        <n-form label-placement="left" label-width="110">
          <n-form-item label="目标数据库">
            <n-input v-model:value="restoreDb" :placeholder="props.dbName || '原始数据库'" />
          </n-form-item>
          <n-form-item label="选择备份">
            <n-data-table
              v-if="backupFiles.length > 0"
              :columns="fileColumns"
              :data="backupFiles"
              :bordered="true"
              size="small"
              :max-height="300"
              :row-key="(r: any) => r.name"
              @update:checked-row-keys="(keys: string[]) => selectedBackup = keys[0] || null"
            >
              <template #empty>
                <n-empty description="暂无备份文件" />
              </template>
            </n-data-table>
            <n-empty v-else description="暂无备份文件" />
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <!-- 历史 -->
      <n-tab-pane name="history" tab="历史记录">
        <div style="margin-bottom: 8px">
          <n-button size="small" @click="loadBackupList">刷新</n-button>
        </div>
        <n-data-table
          :columns="fileColumns"
          :data="backupFiles"
          :bordered="true"
          striped
          :max-height="400"
        />
      </n-tab-pane>
    </n-tabs>

    <template #footer>
      <n-space justify="end">
        <n-button @click="close">取消</n-button>
        <n-button v-if="activeTab === 'backup'" type="primary" @click="doBackup" :loading="loading">
          开始备份
        </n-button>
        <n-button v-if="activeTab === 'restore'" type="warning" @click="doRestore" :loading="loading">
          开始恢复
        </n-button>
      </n-space>
    </template>
  </n-modal>

  <!-- 预览抽屉 -->
  <n-drawer v-model:show="showPreview" :width="600" placement="right">
    <n-drawer-content title="备份文件预览" closable :loading="previewLoading">
      <template v-if="previewData">
        <n-descriptions size="small" bordered :column="2">
          <n-descriptions-item label="文件名">{{ previewData.filename }}</n-descriptions-item>
          <n-descriptions-item label="大小">{{ previewData.file_size_display }}</n-descriptions-item>
          <n-descriptions-item label="创建时间">{{ previewData.date }}</n-descriptions-item>
          <n-descriptions-item label="数据库">{{ previewData.database || '未知' }}</n-descriptions-item>
          <n-descriptions-item label="总行数">{{ previewData.total_lines }}</n-descriptions-item>
          <n-descriptions-item label="INSERT 条数">{{ previewData.total_inserts }}</n-descriptions-item>
          <n-descriptions-item label="备份内容" :span="2">
            <n-space>
              <n-tag v-if="previewData.options.includes('structure')" size="small" type="info">表结构</n-tag>
              <n-tag v-if="previewData.options.includes('data')" size="small" type="success">数据</n-tag>
              <n-tag v-if="previewData.options.includes('views')" size="small" type="warning">视图</n-tag>
              <n-tag v-if="previewData.options.includes('functions')" size="small" type="warning">函数/存储过程</n-tag>
              <n-tag v-if="previewData.options.includes('triggers')" size="small" type="warning">触发器</n-tag>
              <n-tag v-if="previewData.options.includes('events')" size="small" type="warning">事件</n-tag>
            </n-space>
          </n-descriptions-item>
        </n-descriptions>

        <n-h5 style="margin: 12px 0 8px">包含的表/视图</n-h5>
        <n-data-table
          v-if="previewData.tables && previewData.tables.length > 0"
          :columns="[
            { title: '名称', key: 'name' },
            { title: '类型', key: 'type', width: 80,
              render: (row: any) => h('n-tag', {
                size: 'small',
                type: row.type === 'view' ? 'warning' : 'info',
              }, row.type === 'view' ? '视图' : '表'),
            },
          ]"
          :data="previewData.tables"
          size="small"
          bordered
          :max-height="200"
        />
        <n-empty v-else description="未检测到表/视图" />

        <n-h5 style="margin: 12px 0 8px">文件头部预览（前 20 行）</n-h5>
        <n-code :code="previewData.content_preview" language="sql" style="max-height: 200px; overflow: auto" />
      </template>
    </n-drawer-content>
  </n-drawer>
</template>