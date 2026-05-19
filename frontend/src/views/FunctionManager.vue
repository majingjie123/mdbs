<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useMessage } from 'naive-ui'

const props = withDefaults(defineProps<{
  connId?: number
  funcName?: string
  funcType?: string
  dbName?: string
  schemaName?: string
}>(), {
  connId: 0,
  funcName: '',
  funcType: 'FUNCTION',
  dbName: '',
  schemaName: '',
})

const message = useMessage()

const loading = ref(false)
const ddl = ref('')
const error = ref('')
const metadata = ref<any>(null)
const activeTab = ref('ddl')

// ── 加载函数 DDL ──
async function loadFuncDDL() {
  if (!props.connId || !props.funcName) return
  loading.value = true
  error.value = ''
  try {
    const [ddlRes, metaRes] = await Promise.all([
      api.getFunctionDDL(props.connId, props.funcName, props.funcType, props.dbName || undefined, props.schemaName || undefined),
      api.getFunctionMetadata(props.connId, props.funcName, props.dbName || undefined, props.schemaName || undefined),
    ])
    if (ddlRes.success) {
      ddl.value = ddlRes.data || ''
    } else {
      error.value = ddlRes.message || '获取失败'
    }
    if (metaRes.success) {
      metadata.value = metaRes.data
    }
  } catch (e: any) {
    error.value = e.message || '网络错误'
  } finally {
    loading.value = false
  }
}

onMounted(loadFuncDDL)

// ── 工具栏 ──
function copyDDL() {
  navigator.clipboard.writeText(ddl.value)
  message.success('DDL 已复制')
}

function copyName() {
  navigator.clipboard.writeText(props.funcName)
  message.success(`已复制: ${props.funcName}`)
}

// 基本信息
const routineInfo = computed(() => {
  if (!metadata.value?.info) return []
  const info = metadata.value.info
  return [
    { label: '名称', value: info.ROUTINE_NAME },
    { label: '类型', value: info.ROUTINE_TYPE },
    { label: '语言', value: info.ROUTINE_BODY || '-' },
    { label: '确定性', value: info.IS_DETERMINISTIC || '-' },
    { label: 'SQL 模式', value: info.SQL_MODE || '-' },
    { label: '定义者', value: info.DEFINER || '-' },
    { label: '字符集', value: info.CHARACTER_SET_CLIENT || '-' },
    { label: '创建时间', value: info.CREATED || '-' },
    { label: '修改时间', value: info.LAST_ALTERED || '-' },
  ]
})

const paramColumns = computed(() => [
  { title: '序号', key: 'ORDINAL_POSITION', width: 60 },
  { title: '参数名', key: 'PARAMETER_NAME', width: 150 },
  { title: '模式', key: 'PARAMETER_MODE', width: 80 },
  { title: '数据类型', key: 'DTD_IDENTIFIER', width: 200 },
])
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="page-title">
        <h2>{{ funcType === 'PROCEDURE' ? '⚙️' : 'ƒ' }} {{ funcName }}</h2>
        <n-tag v-if="dbName" type="info" size="small">{{ dbName }}</n-tag>
        <n-tag :type="funcType === 'PROCEDURE' ? 'warning' : 'success'" size="small">{{ funcType }}</n-tag>
      </div>
      <n-space size="small">
        <n-button size="tiny" @click="copyName">复制名称</n-button>
        <n-button size="tiny" @click="copyDDL">复制 DDL</n-button>
      </n-space>
    </div>

    <n-alert v-if="error" type="error" closable class="error-alert">{{ error }}</n-alert>

    <n-tabs v-model:value="activeTab" type="line" class="content-tabs">
      <!-- DDL 标签页 -->
      <n-tab-pane name="ddl" tab="DDL 定义">
        <n-card size="small" class="ddl-card">
          <n-spin :show="loading">
            <n-code v-if="ddl" :code="ddl" language="sql" />
            <n-empty v-else-if="!loading" description="无 DDL 数据" />
          </n-spin>
        </n-card>
      </n-tab-pane>

      <!-- 基本信息标签页 -->
      <n-tab-pane name="info" tab="基本信息">
        <n-spin :show="loading">
          <template v-if="routineInfo.length > 0">
            <div v-for="(item, idx) in routineInfo" :key="idx" class="info-row">
              <span class="info-label">{{ item.label }}</span>
              <span class="info-value">{{ item.value }}</span>
            </div>
          </template>
          <n-empty v-else description="暂无元数据信息" />
        </n-spin>
      </n-tab-pane>

      <!-- 参数标签页 -->
      <n-tab-pane name="params" tab="参数">
        <n-spin :show="loading">
          <template v-if="metadata?.params?.length">
            <n-data-table
              :columns="paramColumns"
              :data="metadata.params"
              :bordered="true"
              size="small"
              striped
            />
          </template>
          <n-empty v-else description="无参数" />
        </n-spin>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.page { padding: 20px; height: 100%; display: flex; flex-direction: column; overflow: auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.page-title { display: flex; align-items: center; gap: 12px; }
.page-title h2 { color: #e0e0e0; font-size: 20px; margin: 0; }
.error-alert { margin-bottom: 12px; }
.content-tabs { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.ddl-card { flex: 1; overflow: auto; min-height: 0; }
.info-row { display: flex; padding: 8px 0; border-bottom: 1px solid #333; font-size: 13px; }
.info-label { min-width: 100px; color: #888; }
.info-value { color: #e0e0e0; }
</style>
