<script setup lang="ts">
import { ref, watch, reactive } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../../api'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const message = useMessage()
const dialog = useDialog()

// ── 状态定义 ──
const configs = ref<any[]>([])
const loadingList = ref(false)
const saving = ref(false)
const testing = ref(false)
const loadingModels = ref(false)
const activeConfigId = ref<number | null>(null)
const modelOptions = ref<{ label: string; value: string }[]>([])

// ── 表单定义 ──
const form = reactive({
  id: null as number | null,
  name: '',
  protocol: 'openai',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-3.5-turbo',
  system_prompt: '你是一个专业的数据库智能助手，能够帮我编写、分析和优化 SQL。',
  temperature: 0.7,
  max_tokens: 2048,
  is_default: false
})

// ── 协议选项 ──
const protocolOptions = [
  { label: 'OpenAI 协议', value: 'openai' }
]

// ── 加载配置列表 ──
async function loadConfigs() {
  loadingList.value = true
  try {
    const res = await api.aiListConfigs()
    if (!res.success || !res.data) {
      message.error(res.message || '获取配置列表失败')
      return
    }
    configs.value = res.data
    
    // 如果没有选中的配置，默认选第一个
    if (!activeConfigId.value && res.data.length > 0) {
      selectConfig(res.data[0])
    }
  } catch (e: any) {
    message.error(e.message || '获取配置列表出错')
  } finally {
    loadingList.value = false
  }
}

// ── 选中配置 ──
function selectConfig(cfg: any) {
  activeConfigId.value = cfg.id
  form.id = cfg.id
  form.name = cfg.name
  form.protocol = cfg.protocol || 'openai'
  form.api_key = cfg.api_key || ''
  form.base_url = cfg.base_url || 'https://api.openai.com/v1'
  form.model = cfg.model || 'gpt-3.5-turbo'
  form.system_prompt = cfg.system_prompt || ''
  form.temperature = cfg.temperature ?? 0.7
  form.max_tokens = cfg.max_tokens ?? 2048
  form.is_default = !!cfg.is_default
  modelOptions.value = []
}

// ── 新建配置初始化 ──
function initNewConfig() {
  activeConfigId.value = null
  form.id = null
  form.name = '新建 AI 配置'
  form.protocol = 'openai'
  form.api_key = ''
  form.base_url = 'https://api.openai.com/v1'
  form.model = 'gpt-3.5-turbo'
  form.system_prompt = '你是一个专业的数据库智能助手，能够帮我编写、分析和优化 SQL。'
  form.temperature = 0.7
  form.max_tokens = 2048
  form.is_default = configs.value.length === 0 // 如果是第一个配置，默认设为 True
  modelOptions.value = []
}

// ── 保存配置 ──
async function handleSave() {
  if (!form.name.trim()) {
    message.warning('请输入配置名称')
    return
  }
  if (!form.base_url.trim()) {
    message.warning('请输入 Base URL')
    return
  }
  if (!form.api_key.trim()) {
    message.warning('请输入 API Key')
    return
  }
  if (!form.model.trim()) {
    message.warning('请输入或拉取模型名称')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      protocol: form.protocol,
      api_key: form.api_key.trim(),
      base_url: form.base_url.trim(),
      model: form.model.trim(),
      system_prompt: form.system_prompt.trim(),
      temperature: form.temperature,
      max_tokens: form.max_tokens,
      is_default: form.is_default ? 1 : 0
    }

    if (form.id) {
      // 更新已有的配置
      const res = await api.aiUpdateConfig(form.id, payload)
      if (!res.success) {
        message.error(res.message || '更新配置失败')
        return
      }
      message.success('配置已保存')
    } else {
      // 新增配置
      const res = await api.aiCreateConfig(payload)
      if (!res.success || !res.data) {
        message.error(res.message || '新增配置失败')
        return
      }
      message.success('配置已创建')
      activeConfigId.value = res.data.id
    }
    
    await loadConfigs()
  } catch (e: any) {
    message.error(e.message || '保存配置出错')
  } finally {
    saving.value = false
  }
}

// ── 删除配置 ──
function handleDelete(cfg: any, event: Event) {
  event.stopPropagation() // 阻止列表项被点击选中
  
  dialog.warning({
    title: '删除配置',
    content: `确定要删除 AI 配置「${cfg.name}」吗？`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await api.aiDeleteConfig(cfg.id)
        if (!res.success) {
          message.error(res.message || '删除失败')
          return
        }
        message.success('配置已删除')
        
        // 如果删除了当前选中的配置
        if (activeConfigId.value === cfg.id) {
          activeConfigId.value = null
          form.id = null
        }
        
        await loadConfigs()
        if (configs.value.length === 0) {
          initNewConfig()
        }
      } catch (e: any) {
        message.error(e.message || '删除配置出错')
      }
    }
  })
}

// ── 测试连接 ──
async function handleTest() {
  if (!form.id) {
    message.warning('请先保存配置，然后再进行连接测试')
    return
  }

  testing.value = true
  try {
    const res = await api.aiTestConfig(form.id)
    if (!res.success) {
      message.error(res.message || '连接测试失败')
      return
    }
    message.success(res.message || '连接测试成功，配置可用！')
  } catch (e: any) {
    message.error(e.message || '测试连接出错')
  } finally {
    testing.value = false
  }
}

// ── 拉取模型列表 ──
async function fetchModels() {
  if (!form.api_key.trim()) {
    message.warning('请输入 API Key 后再拉取模型')
    return
  }
  if (!form.base_url.trim()) {
    message.warning('请输入 Base URL 后再拉取模型')
    return
  }

  loadingModels.value = true
  try {
    const res = await api.aiListModels(form.api_key.trim(), form.base_url.trim())
    if (!res.success || !res.data) {
      message.error(res.message || '获取模型列表失败')
      return
    }
    modelOptions.value = res.data.map((m: string) => ({ label: m, value: m }))
    message.success(`拉取成功，共获取 ${res.data.length} 个可用模型`)
  } catch (e: any) {
    message.error(e.message || '拉取模型列表出错')
  } finally {
    loadingModels.value = false
  }
}

// ── 监视弹窗状态 ──
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadConfigs()
  }
})
</script>

<template>
  <n-modal
    :show="visible"
    @update:show="(v: boolean) => emit('update:visible', v)"
    preset="card"
    title="AI 配置管理"
    style="width: 780px"
    :mask-closable="false"
    :bordered="true"
    :segmented="{ content: true }"
  >
    <div class="ai-config-container">
      <!-- 左栏：配置列表 -->
      <div class="sidebar-panel">
        <div class="sidebar-header">
          <n-button type="primary" dashed block @click="initNewConfig">
            + 新建 AI 配置
          </n-button>
        </div>
        <n-spin :show="loadingList">
          <div class="config-list-wrap">
            <div
              v-for="cfg in configs"
              :key="cfg.id"
              class="config-item"
              :class="{ active: cfg.id === activeConfigId }"
              @click="selectConfig(cfg)"
            >
              <div class="config-item-meta">
                <span class="config-name">{{ cfg.name }}</span>
                <span class="config-model">{{ cfg.model }}</span>
              </div>
              <div class="config-item-actions">
                <n-tag v-if="cfg.is_default" type="success" size="tiny" round class="tag-default">
                  默认
                </n-tag>
                <button class="btn-delete" @click="handleDelete(cfg, $event)" title="删除此配置">
                  &times;
                </button>
              </div>
            </div>
            <div v-if="!loadingList && configs.length === 0" class="empty-list">
              暂无配置，请点击上方按钮新建
            </div>
          </div>
        </n-spin>
      </div>

      <!-- 右栏：配置表单 -->
      <div class="form-panel">
        <n-scrollbar style="max-height: 480px">
          <n-form label-placement="left" label-width="100" size="small" class="config-form">
            <n-form-item label="配置名称" required>
              <n-input v-model:value="form.name" placeholder="请输入配置名称，如 DeepSeek、OpenAI" />
            </n-form-item>

            <n-form-item label="接口协议" required>
              <n-select v-model:value="form.protocol" :options="protocolOptions" />
            </n-form-item>

            <n-form-item label="Base URL" required>
              <n-input v-model:value="form.base_url" placeholder="如 https://api.openai.com/v1" />
            </n-form-item>

            <n-form-item label="API Key" required>
              <n-input
                v-model:value="form.api_key"
                type="password"
                show-password-on="click"
                placeholder="请输入 API Key (已加密存储)"
              />
            </n-form-item>

            <n-form-item label="模型名称" required>
              <div class="model-select-group">
                <n-select
                  v-model:value="form.model"
                  filterable
                  tag
                  :options="modelOptions"
                  placeholder="请输入或从右侧拉取模型"
                  style="flex: 1"
                />
                <n-button :loading="loadingModels" @click="fetchModels" secondary type="info">
                  拉取模型
                </n-button>
              </div>
            </n-form-item>

            <n-form-item label="设为默认">
              <n-switch v-model:value="form.is_default" />
              <span class="switch-hint">开启后，系统在 AI 对话和智能生成时将默认使用该配置</span>
            </n-form-item>

            <n-form-item label="温度 (Temp)">
              <div class="slider-group">
                <n-slider v-model:value="form.temperature" :min="0.1" :max="2.0" :step="0.1" style="flex: 1" />
                <n-input-number v-model:value="form.temperature" :min="0.1" :max="2.0" :step="0.1" style="width: 80px" />
              </div>
            </n-form-item>

            <n-form-item label="最大 Tokens">
              <n-input-number v-model:value="form.max_tokens" :min="256" :max="16384" :step="256" />
            </n-form-item>

            <n-form-item label="系统提示词">
              <n-input
                v-model:value="form.system_prompt"
                type="textarea"
                :rows="4"
                placeholder="用于设定 AI 扮演的角色和回复规则"
              />
            </n-form-item>
          </n-form>
        </n-scrollbar>

        <div class="form-actions">
          <n-button :loading="testing" type="info" secondary @click="handleTest" :disabled="!form.id">
            测试连接
          </n-button>
          <n-space>
            <n-button @click="emit('update:visible', false)">关闭</n-button>
            <n-button :loading="saving" type="primary" @click="handleSave">保存配置</n-button>
          </n-space>
        </div>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.ai-config-container {
  display: flex;
  height: 520px;
  gap: 16px;
  overflow: hidden;
}

/* 左侧列表 */
.sidebar-panel {
  width: 240px;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  padding-right: 16px;
}

.sidebar-header {
  margin-bottom: 12px;
}

.config-list-wrap {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 460px;
}

.config-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.02);
  transition: all 0.2s ease;
  position: relative;
}

.config-item:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: var(--color-border-light);
}

.config-item.active {
  background: rgba(0, 120, 212, 0.15);
  border-color: var(--color-accent);
}

.config-item-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.config-name {
  font-weight: 600;
  color: var(--color-text);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-model {
  font-size: 11px;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-item-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.btn-delete {
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  display: none;
}

.config-item:hover .btn-delete {
  display: block;
}

.btn-delete:hover {
  color: #ff3333;
}

.empty-list {
  text-align: center;
  color: var(--color-text-muted);
  padding: 40px 10px;
  font-size: 12px;
}

/* 右侧表单 */
.form-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding-left: 4px;
}

.config-form {
  margin-bottom: 16px;
}

.model-select-group {
  display: flex;
  gap: 8px;
  width: 100%;
}

.switch-hint {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-left: 12px;
  line-height: 20px;
}

.slider-group {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--color-border);
  padding-top: 12px;
  margin-top: auto;
}
</style>
