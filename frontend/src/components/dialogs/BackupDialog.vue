<script setup lang="ts">
import { ref } from 'vue'
import { useMessage } from 'naive-ui'

const props = defineProps<{
  visible: boolean
  connId?: number
  dbName?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const message = useMessage()

const activeTab = ref('backup')
const backupDb = ref('')
const backupTables = ref<string[]>([])
const backupOptions = ref<string[]>(['structure', 'data'])
const backupPath = ref('')

const allOptions = [
  { label: '表结构', value: 'structure' },
  { label: '数据', value: 'data' },
  { label: '视图', value: 'views' },
  { label: '函数/存储过程', value: 'functions' },
  { label: '触发器', value: 'triggers' },
  { label: '事件', value: 'events' },
]

// 备份历史（简化）
const history = ref([
  { date: '2026-05-17 10:00', file: 'backup_20260517.sql', size: '2.3 MB' },
])

function doBackup() {
  message.success('备份功能开发中，将在后续版本实现')
  emit('update:visible', false)
}

function doRestore() {
  message.success('恢复功能开发中，将在后续版本实现')
  emit('update:visible', false)
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
    title="备份 / 恢复"
    style="width: 600px"
    :bordered="true"
    :segmented="{ content: true }"
  >
    <n-tabs v-model:value="activeTab" type="line">
      <n-tab-pane name="backup" tab="备份">
        <n-form label-placement="left" label-width="100">
          <n-form-item label="数据库">
            <n-input v-model:value="backupDb" :placeholder="dbName || '全部数据库'" />
          </n-form-item>
          <n-form-item label="备份内容">
            <n-checkbox-group v-model:value="backupOptions">
              <n-space>
                <n-checkbox v-for="opt in allOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
              </n-space>
            </n-checkbox-group>
          </n-form-item>
          <n-form-item label="保存路径">
            <n-input v-model:value="backupPath" placeholder="默认: 项目目录/backup/" />
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <n-tab-pane name="restore" tab="恢复">
        <n-form label-placement="left" label-width="100">
          <n-form-item label="选择文件">
            <n-upload :disabled="true">
              <n-button>选择备份文件</n-button>
            </n-upload>
          </n-form-item>
          <n-form-item label="目标数据库">
            <n-input :placeholder="dbName || 'original'" />
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <n-tab-pane name="history" tab="历史">
        <n-data-table
          :columns="[
            { title: '时间', key: 'date', width: 160 },
            { title: '文件', key: 'file', width: 200 },
            { title: '大小', key: 'size', width: 100 },
          ]"
          :data="history"
          :bordered="true"
          striped
        />
      </n-tab-pane>
    </n-tabs>

    <template #footer>
      <n-space justify="end">
        <n-button @click="close">取消</n-button>
        <n-button v-if="activeTab === 'backup'" type="primary" @click="doBackup">开始备份</n-button>
        <n-button v-if="activeTab === 'restore'" type="warning" @click="doRestore">开始恢复</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
