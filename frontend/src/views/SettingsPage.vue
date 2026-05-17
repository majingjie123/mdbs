<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const activeTab = ref('theme')

// 主题设置
const themeOptions = [
  { label: '暗黑模式', value: 'dark' },
  { label: '护眼绿', value: 'eye' },
  { label: '黑客绿', value: 'hacker' },
  { label: '深海蓝', value: 'deepblue' },
  { label: '优雅紫', value: 'purple' },
  { label: '樱花粉', value: 'pink' },
  { label: '落日橙', value: 'orange' },
]
const currentTheme = ref('dark')
const fontFamily = ref('Cascadia Code, Fira Code, Consolas, monospace')
const fontSize = ref(13)

// AI 设置
const aiEnabled = ref(false)
const aiProvider = ref('openai')
const aiEndpoint = ref('')
const aiApiKey = ref('')
const aiModel = ref('gpt-4o-mini')
const aiMaxTokens = ref(4096)

const providerOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Azure OpenAI', value: 'azure' },
  { label: 'Ollama (本地)', value: 'ollama' },
  { label: '兼容 OpenAI 的 API', value: 'custom' },
]

const modelOptions: Record<string, { label: string; value: string }[]> = {
  openai: [
    { label: 'GPT-4o', value: 'gpt-4o' },
    { label: 'GPT-4o-mini', value: 'gpt-4o-mini' },
    { label: 'GPT-4-turbo', value: 'gpt-4-turbo' },
    { label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo' },
    { label: 'o1-mini', value: 'o1-mini' },
    { label: 'o3-mini', value: 'o3-mini' },
    { label: 'DeepSeek V3', value: 'deepseek-chat' },
    { label: 'DeepSeek R1', value: 'deepseek-reasoner' },
  ],
  azure: [
    { label: 'GPT-4o', value: 'gpt-4o' },
    { label: 'GPT-4-turbo', value: 'gpt-4-turbo' },
  ],
  ollama: [
    { label: 'Llama 3', value: 'llama3' },
    { label: 'Qwen 2.5', value: 'qwen2.5' },
    { label: 'DeepSeek', value: 'deepseek' },
    { label: 'Mistral', value: 'mistral' },
    { label: '自定义', value: 'custom' },
  ],
  custom: [
    { label: '自定义模型', value: 'custom' },
  ],
}

const currentModels = ref(modelOptions[aiProvider.value] || modelOptions.custom)

function onProviderChange(provider: string) {
  currentModels.value = modelOptions[provider] || modelOptions.custom
  aiModel.value = currentModels.value[0]?.value || 'custom'
}

// 保存设置
function saveSettings() {
  const settings = {
    theme: currentTheme.value,
    fontFamily: fontFamily.value,
    fontSize: fontSize.value,
    ai: {
      enabled: aiEnabled.value,
      provider: aiProvider.value,
      endpoint: aiEndpoint.value,
      apiKey: aiApiKey.value,
      model: aiModel.value,
      maxTokens: aiMaxTokens.value,
    }
  }
  localStorage.setItem('mdbs_settings', JSON.stringify(settings))
  message.success('设置已保存')
}

// 加载设置
function loadSettings() {
  const stored = localStorage.getItem('mdbs_settings')
  if (!stored) return
  try {
    const s = JSON.parse(stored)
    if (s.theme) currentTheme.value = s.theme
    if (s.fontFamily) fontFamily.value = s.fontFamily
    if (s.fontSize) fontSize.value = s.fontSize
    if (s.ai) {
      aiEnabled.value = s.ai.enabled ?? false
      aiProvider.value = s.ai.provider || 'openai'
      aiEndpoint.value = s.ai.endpoint || ''
      aiApiKey.value = s.ai.apiKey || ''
      aiModel.value = s.ai.model || 'gpt-4o-mini'
      aiMaxTokens.value = s.ai.maxTokens || 4096
      onProviderChange(aiProvider.value)
    }
  } catch {}
}

// 清除所有数据
function clearAllData() {
  dialog.warning({
    title: '清除所有数据',
    content: '确定要清除所有本地数据包括连接配置、设置、缓存？此操作不可撤销！',
    positiveText: '确认清除',
    negativeText: '取消',
    type: 'error',
    onPositiveClick: async () => {
      localStorage.removeItem('mdbs_settings')
      localStorage.clear()
      message.success('已清除所有本地数据')
    },
  })
}

onMounted(loadSettings)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>设置</h2>
      <n-space>
        <n-button @click="saveSettings" type="primary">保存设置</n-button>
        <n-button @click="router.push('/connections')">返回</n-button>
      </n-space>
    </div>

    <n-tabs v-model:value="activeTab" type="line">
      <!-- 主题设置 -->
      <n-tab-pane name="theme" tab="界面主题">
        <n-form label-placement="left" label-width="120" style="max-width: 500px">
          <n-form-item label="主题风格">
            <n-select v-model:value="currentTheme" :options="themeOptions" />
          </n-form-item>
          <n-form-item label="编辑器字体">
            <n-input v-model:value="fontFamily" placeholder="Cascadia Code, Consolas, monospace" />
          </n-form-item>
          <n-form-item label="字号">
            <n-input-number v-model:value="fontSize" :min="10" :max="24" />
          </n-form-item>
          <n-divider />
          <n-form-item label="主题预览">
            <div class="theme-preview" :class="`theme-${currentTheme}`">
              <div class="preview-toolbar">工具栏</div>
              <div class="preview-body">
                <div class="preview-sidebar">侧栏</div>
                <div class="preview-workspace">工作区</div>
              </div>
              <div class="preview-status">状态栏</div>
            </div>
          </n-form-item>
        </n-form>
      </n-tab-pane>

      <!-- AI 设置 -->
      <n-tab-pane name="ai" tab="AI 助手">
        <n-form label-placement="left" label-width="140" style="max-width: 500px">
          <n-form-item label="启用 AI 助手">
            <n-switch v-model:value="aiEnabled" />
          </n-form-item>

          <template v-if="aiEnabled">
            <n-form-item label="API 提供商">
              <n-select
                v-model:value="aiProvider"
                :options="providerOptions"
                @update:value="onProviderChange"
              />
            </n-form-item>

            <n-form-item v-if="aiProvider === 'custom' || aiProvider === 'ollama'" label="API 地址">
              <n-input v-model:value="aiEndpoint" placeholder="https://api.openai.com/v1" />
            </n-form-item>

            <n-form-item v-if="aiProvider !== 'ollama'" label="API Key">
              <n-input
                v-model:value="aiApiKey"
                type="password"
                show-password-on="click"
                placeholder="sk-..."
              />
            </n-form-item>

            <n-form-item label="模型">
              <n-select v-model:value="aiModel" :options="currentModels" />
            </n-form-item>

            <n-form-item label="最大 Token">
              <n-input-number v-model:value="aiMaxTokens" :min="512" :max="32768" :step="512" />
            </n-form-item>

            <n-alert type="info" closable>
              AI 助手可以帮助您生成 SQL、解释查询结果、优化查询性能等。
              API Key 仅存储在本地，不会上传到服务器。
            </n-alert>
          </template>
        </n-form>
      </n-tab-pane>

      <!-- 关于 -->
      <n-tab-pane name="about" tab="关于">
        <div class="about-section">
          <h3>MDBS - 数据库连接管理工具</h3>
          <p>版本 1.0.0</p>
          <p>基于 Vue 3 + FastAPI 构建</p>
          <n-divider />
          <n-button type="error" @click="clearAllData">清除所有本地数据</n-button>
        </div>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.page {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  color: #e0e0e0;
  font-size: 20px;
}

/* 主题预览 */
.theme-preview {
  width: 320px;
  height: 180px;
  border: 1px solid #555;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-size: 11px;
}

.preview-toolbar {
  height: 24px;
  background: #3c3f41;
  padding: 4px 8px;
  color: #aaa;
}

.preview-body {
  flex: 1;
  display: flex;
}

.preview-sidebar {
  width: 80px;
  background: #252526;
  padding: 8px;
  color: #888;
}

.preview-workspace {
  flex: 1;
  background: #1e1e1e;
  padding: 8px;
  color: #777;
}

.preview-status {
  height: 20px;
  background: #3c3f41;
  padding: 2px 8px;
  color: #999;
}

/* 不同主题变体 */
.theme-eye .preview-toolbar { background: #3a5a3a; }
.theme-eye .preview-sidebar { background: #2a4a2a; }
.theme-eye .preview-workspace { background: #1a3a1a; }
.theme-eye .preview-status { background: #3a5a3a; }
.theme-hacker .preview-toolbar { background: #0a3a0a; }
.theme-hacker .preview-sidebar { background: #0a2a0a; }
.theme-hacker .preview-workspace { background: #0a1a0a; }
.theme-hacker .preview-status { background: #0a3a0a; }
.theme-deepblue .preview-toolbar { background: #1a2a4a; }
.theme-deepblue .preview-sidebar { background: #0a1a3a; }
.theme-deepblue .preview-workspace { background: #050f20; }
.theme-deepblue .preview-status { background: #1a2a4a; }
.theme-purple .preview-toolbar { background: #3a1a4a; }
.theme-purple .preview-sidebar { background: #2a0a3a; }
.theme-purple .preview-workspace { background: #1a0520; }
.theme-purple .preview-status { background: #3a1a4a; }
.theme-pink .preview-toolbar { background: #4a2035; }
.theme-pink .preview-sidebar { background: #3a1525; }
.theme-pink .preview-workspace { background: #2a0a18; }
.theme-pink .preview-status { background: #4a2035; }
.theme-orange .preview-toolbar { background: #4a3520; }
.theme-orange .preview-sidebar { background: #3a2515; }
.theme-orange .preview-workspace { background: #2a1808; }
.theme-orange .preview-status { background: #4a3520; }

.about-section {
  max-width: 400px;
}
.about-section h3 {
  color: #e0e0e0;
  margin-bottom: 8px;
}
.about-section p {
  color: #aaa;
  margin: 4px 0;
}
</style>