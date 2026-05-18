<template>
  <div class="ai-settings-page">
    <n-page-header @back="goBack">
      <template #title>AI 设置</template>
      <template #extra>
        <n-button type="primary" @click="showAddDialog = true">新增配置</n-button>
      </template>
    </n-page-header>

    <n-data-table
      :columns="columns"
      :data="configs"
      :loading="loading"
      striped
      style="margin-top: 16px"
    />

    <!-- Add/Edit dialog -->
    <n-modal v-model:show="showAddDialog" title="AI 配置" preset="card" style="width: 500px" :mask-closable="false">
      <n-form ref="formRef" :model="formData" label-placement="left" label-width="100">
        <n-form-item label="名称" path="name" :rule="{ required: true, message: '请输入配置名称', trigger: ['blur', 'input'] }">
          <n-input v-model:value="formData.name" placeholder="配置名称" />
        </n-form-item>
        <n-form-item label="API Key">
          <n-input v-model:value="formData.api_key" type="password" show-password-on="click" placeholder="sk-..." />
        </n-form-item>
        <n-form-item label="Base URL">
          <n-input v-model:value="formData.base_url" placeholder="https://api.openai.com/v1" />
        </n-form-item>
        <n-form-item label="模型">
          <div style="display: flex; align-items: center; gap: 6px; width: 100%">
            <n-auto-complete v-model:value="formData.model" :options="modelSuggestions" placeholder="gpt-3.5-turbo" style="flex: 1" />
            <n-button size="tiny" quaternary @click="refreshModels" :loading="refreshingModels" title="刷新模型列表">
              <template #icon>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" :class="{ spinning: refreshingModels }">
                  <polyline points="23 4 23 10 17 10"/>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
              </template>
            </n-button>
          </div>
        </n-form-item>
        <n-form-item label="Temperature">
          <n-slider v-model:value="formData.temperature" :min="0" :max="2" :step="0.1" style="width: 200px" />
          <span style="margin-left: 12px">{{ formData.temperature.toFixed(1) }}</span>
        </n-form-item>
        <n-form-item label="Max Tokens">
          <n-input-number v-model:value="formData.max_tokens" :min="1" :max="128000" :step="100" style="width: 160px" />
        </n-form-item>
        <n-form-item label="系统提示词">
          <n-input v-model:value="formData.system_prompt" type="textarea" :rows="3" placeholder="可选的系统提示词" />
        </n-form-item>
        <n-form-item label="设为默认">
          <n-switch v-model:value="formData.is_default" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="space-between">
          <n-button @click="testConnection" :loading="testing" :disabled="!formData.api_key">测试连接</n-button>
          <n-space>
            <n-button @click="showAddDialog = false">取消</n-button>
            <n-button type="primary" @click="saveConfig">保存</n-button>
          </n-space>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import type { DataTableColumn, FormInst } from 'naive-ui'
import { api } from '../api'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const configs = ref<any[]>([])
const showAddDialog = ref(false)
const testing = ref(false)
const editId = ref<number | null>(null)

const formData = ref({
  name: '',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-3.5-turbo',
  temperature: 0.7,
  max_tokens: 2048,
  system_prompt: '',
  is_default: false,
})

const formRef = ref<FormInst | null>(null)
const modelSuggestions = ref([
  'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
  'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano',
  'deepseek-chat', 'deepseek-reasoner',
  'claude-3-opus-20240229', 'claude-3-sonnet-20240229',
])

const refreshingModels = ref(false)

async function refreshModels() {
  if (!formData.value.base_url || !formData.value.api_key) {
    message.warning('请先填写 Base URL 和 API Key')
    return
  }
  refreshingModels.value = true
  try {
    const res: any = await api.aiListModels(formData.value.api_key, formData.value.base_url)
    if (res.success && Array.isArray(res.data)) {
      modelSuggestions.value = res.data
      if (res.data.length > 0 && !formData.value.model) {
        formData.value.model = res.data[0]
      }
      message.success(`获取到 ${res.data.length} 个模型`)
    } else {
      message.error(res.message || '获取模型列表失败')
    }
  } catch (e: any) {
    message.error('获取模型列表失败: ' + (e.message || ''))
  } finally {
    refreshingModels.value = false
  }
}

const columns: DataTableColumn[] = [
  { title: '名称', key: 'name', width: 120 },
  { title: '模型', key: 'model', width: 160 },
  { title: 'Base URL', key: 'base_url', ellipsis: { tooltip: true } },
  { title: '默认', key: 'is_default', width: 60,
    render: (row: any) => row.is_default ? h('n-tag', { type: 'success', size: 'small' }, '默认') : '',
  },
  { title: '操作', key: 'actions', width: 160,
    render: (row: any) => h('n-space', { size: 'small' }, {
      default: () => [
        h('n-button', { size: 'tiny', onClick: () => editConfig(row) }, '编辑'),
        h('n-button', { size: 'tiny', type: 'error', quaternary: true, onClick: () => deleteConfig(row) }, '删除'),
      ],
    }),
  },
]

async function loadConfigs() {
  loading.value = true
  try {
    const res: any = await api.aiListConfigs()
    if (res.success) configs.value = res.data || []
  } catch (e: any) {
    message.error('加载失败: ' + (e.message || ''))
  } finally {
    loading.value = false
  }
}

function editConfig(row: any) {
  editId.value = row.id
  formData.value = {
    name: row.name || '',
    api_key: '',
    base_url: row.base_url || 'https://api.openai.com/v1',
    model: row.model || 'gpt-3.5-turbo',
    temperature: row.temperature ?? 0.7,
    max_tokens: row.max_tokens ?? 2048,
    system_prompt: row.system_prompt || '',
    is_default: !!row.is_default,
  }
  showAddDialog.value = true
}

async function saveConfig() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  try {
    let res: any
    if (editId.value) {
      res = await api.aiUpdateConfig(editId.value, formData.value)
    } else {
      res = await api.aiCreateConfig(formData.value)
    }
    if (res.success) {
      message.success(editId.value ? '配置已更新' : '配置已创建')
      showAddDialog.value = false
      editId.value = null
      resetForm()
      await loadConfigs()
    } else {
      message.error(res.message || '保存失败')
    }
  } catch (e: any) {
    message.error('保存失败: ' + (e.message || ''))
  }
}

function deleteConfig(row: any) {
  dialog.warning({
    title: '删除配置',
    content: `确定删除配置 "${row.name}" 吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res: any = await api.aiDeleteConfig(row.id)
        if (res.success) {
          message.success('已删除')
          await loadConfigs()
        } else {
          message.error(res.message || '删除失败')
        }
      } catch (e: any) {
        message.error('删除失败')
      }
    },
  })
}

async function testConnection() {
  if (!formData.value.api_key) {
    message.warning('请先输入 API Key')
    return
  }
  testing.value = true
  try {
    // Create temp config for testing
    const createRes: any = await api.aiCreateConfig({
      name: '__temp_test__',
      api_key: formData.value.api_key,
      base_url: formData.value.base_url,
      model: formData.value.model,
      temperature: formData.value.temperature,
      max_tokens: formData.value.max_tokens,
    })
    if (!createRes.success || !createRes.data) {
      message.error('创建临时配置失败')
      return
    }
    const tempId = createRes.data.id
    const res: any = await api.aiTestConfig(tempId)
    if (res.success) {
      message.success('连接成功!')
    } else {
      message.error(res.message || '连接失败')
    }
    // Clean up temp config
    await api.aiDeleteConfig(tempId)
  } catch (e: any) {
    message.error('测试失败: ' + (e.message || ''))
  } finally {
    testing.value = false
  }
}

function resetForm() {
  formData.value = {
    name: '',
    api_key: '',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-3.5-turbo',
    temperature: 0.7,
    max_tokens: 2048,
    system_prompt: '',
    is_default: false,
  }
  editId.value = null
}

function goBack() {
  router.back()
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.ai-settings-page {
  padding: 16px;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
