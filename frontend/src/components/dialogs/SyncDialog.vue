<script setup lang="ts">
import { ref, h } from 'vue'
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

const activeTab = ref('database')

// 目标连接
const targetConnId = ref<number | null>(null)
const targetDb = ref('')

const connOptions = ref([
  { label: '请先添加目标连接', value: null },
])

// 同步选项
const syncStructure = ref(true)
const syncData = ref(false)
const syncViews = ref(false)
const syncFunctions = ref(false)
const dropTarget = ref(false)

// 同步历史
const syncHistory = ref([
  { date: '2026-05-16 14:30', source: 'local', target: 'prod', status: '成功', tables: '15' },
])

function doSync() {
  message.success('同步功能开发中，将在后续版本实现')
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
    title="数据库同步"
    style="width: 650px"
    :bordered="true"
    :segmented="{ content: true }"
  >
    <n-tabs v-model:value="activeTab" type="line">
      <n-tab-pane name="database" tab="数据库同步">
        <n-form label-placement="left" label-width="120">
          <n-form-item label="源数据库">
            <n-input :value="dbName || '当前连接'" disabled />
          </n-form-item>
          <n-form-item label="目标连接">
            <n-select
              v-model:value="targetConnId"
              :options="connOptions"
              placeholder="选择目标连接"
            />
          </n-form-item>
          <n-form-item label="目标数据库">
            <n-input v-model:value="targetDb" placeholder="目标数据库名称" />
          </n-form-item>
          <n-divider />
          <n-form-item label="同步选项">
            <n-space vertical>
              <n-checkbox v-model:checked="syncStructure">表结构</n-checkbox>
              <n-checkbox v-model:checked="syncData">数据</n-checkbox>
              <n-checkbox v-model:checked="syncViews">视图</n-checkbox>
              <n-checkbox v-model:checked="syncFunctions">函数/存储过程</n-checkbox>
              <n-checkbox v-model:checked="dropTarget">同步前清空目标</n-checkbox>
            </n-space>
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <n-tab-pane name="structure" tab="同步表结构">
        <n-alert type="info" closable>
          比较源和目标数据库的表结构差异，生成 ALTER 语句。
        </n-alert>
        <div style="margin-top: 16px">
          <n-space>
            <n-button>比较结构</n-button>
            <n-button type="primary" disabled>应用更改</n-button>
          </n-space>
        </div>
      </n-tab-pane>

      <n-tab-pane name="history" tab="同步历史">
        <n-data-table
          :columns="[
            { title: '时间', key: 'date', width: 150 },
            { title: '源', key: 'source', width: 100 },
            { title: '目标', key: 'target', width: 100 },
            { title: '状态', key: 'status', width: 80,
              render: (r: any) => h('n-tag', { type: r.status === '成功' ? 'success' : 'error', size: 'small' }, r.status)
            },
            { title: '表数', key: 'tables', width: 60 },
          ]"
          :data="syncHistory"
          :bordered="true"
          striped
        />
      </n-tab-pane>
    </n-tabs>

    <template #footer>
      <n-space justify="end">
        <n-button @click="close">取消</n-button>
        <n-button type="primary" @click="doSync">开始同步</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
