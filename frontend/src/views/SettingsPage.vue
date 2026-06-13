<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import { useAppStore } from '../stores/app'
import type { DataTableColumn, FormInst } from 'naive-ui'
import { api } from '../api'
import { DEFAULT_SHORTCUTS, loadShortcuts, saveShortcuts, resetShortcuts } from '../composables/useShortcuts'
import type { ShortcutDef } from '../composables/useShortcuts'

const router = useRouter()
const store = useAppStore()
const message = useMessage()
const dialog = useDialog()

const activeTab = ref('theme')

// AI 配置相关
const aiLoading = ref(false)
const aiConfigs = ref<any[]>([])
const showAiDialog = ref(false)
const aiTesting = ref(false)
const aiEditId = ref<number | null>(null)
const aiFormRef = ref<FormInst | null>(null)
const aiFormData = ref({
  name: '',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-3.5-turbo',
  temperature: 0.7,
  max_tokens: 2048,
  system_prompt: '',
  is_default: false,
})
const aiModelSuggestions = ref([
  'gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini',
  'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano',
  'deepseek-chat', 'deepseek-reasoner',
  'claude-3-opus-20240229', 'claude-3-sonnet-20240229',
])
const refreshingModels = ref(false)

const aiColumns: DataTableColumn[] = [
  { title: '名称', key: 'name', width: 120 },
  { title: '模型', key: 'model', width: 160 },
  { title: 'Base URL', key: 'base_url', ellipsis: { tooltip: true } },
  { title: '默认', key: 'is_default', width: 60,
    render: (row: any) => row.is_default ? h('n-tag', { type: 'success', size: 'small' }, '默认') : '',
  },
  { title: '操作', key: 'actions', width: 160,
    render: (row: any) => h('n-space', { size: 'small' }, {
      default: () => [
        h('n-button', { size: 'tiny', onClick: () => editAiConfig(row) }, '编辑'),
        h('n-button', { size: 'tiny', type: 'error', quaternary: true, onClick: () => deleteAiConfig(row) }, '删除'),
      ],
    }),
  },
]

async function loadAiConfigs() {
  aiLoading.value = true
  try {
    const res: any = await api.aiListConfigs()
    if (res.success) aiConfigs.value = res.data || []
  } catch (e: any) {
    message.error('加载失败: ' + (e.message || ''))
  } finally {
    aiLoading.value = false
  }
}

function editAiConfig(row: any) {
  aiEditId.value = row.id
  aiFormData.value = {
    name: row.name || '',
    api_key: '',
    base_url: row.base_url || 'https://api.openai.com/v1',
    model: row.model || 'gpt-3.5-turbo',
    temperature: row.temperature ?? 0.7,
    max_tokens: row.max_tokens ?? 2048,
    system_prompt: row.system_prompt || '',
    is_default: !!row.is_default,
  }
  showAiDialog.value = true
}

async function saveAiConfig() {
  try {
    await aiFormRef.value?.validate()
  } catch {
    return
  }
  try {
    let res: any
    const data: any = { ...aiFormData.value }
    if (aiEditId.value && !data.api_key) {
      delete data.api_key
    }
    if (aiEditId.value) {
      res = await api.aiUpdateConfig(aiEditId.value, data)
    } else {
      res = await api.aiCreateConfig(data)
    }
    if (res.success) {
      message.success(aiEditId.value ? '配置已更新' : '配置已创建')
      showAiDialog.value = false
      aiEditId.value = null
      resetAiForm()
      await loadAiConfigs()
    } else {
      message.error(res.message || '保存失败')
    }
  } catch (e: any) {
    message.error('保存失败: ' + (e.message || ''))
  }
}

function deleteAiConfig(row: any) {
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
          await loadAiConfigs()
        } else {
          message.error(res.message || '删除失败')
        }
      } catch (e: any) {
        message.error('删除失败')
      }
    },
  })
}

async function testAiConnection() {
  if (!aiFormData.value.api_key) {
    message.warning('请先输入 API Key')
    return
  }
  aiTesting.value = true
  let tempId = 0
  try {
    const createRes: any = await api.aiCreateConfig({
      name: '__temp_test__',
      api_key: aiFormData.value.api_key,
      base_url: aiFormData.value.base_url,
      model: aiFormData.value.model,
      temperature: aiFormData.value.temperature,
      max_tokens: aiFormData.value.max_tokens,
    })
    if (!createRes.success || !createRes.data) {
      message.error('创建临时配置失败')
      return
    }
    tempId = createRes.data.id
    const res: any = await api.aiTestConfig(tempId)
    if (res.success) {
      message.success('连接成功!')
    } else {
      message.error(res.message || '连接失败')
    }
  } catch (e: any) {
    message.error('测试失败: ' + (e.message || ''))
  } finally {
    if (tempId) {
      try { await api.aiDeleteConfig(tempId) } catch {}
    }
    aiTesting.value = false
  }
}

async function refreshAiModels() {
  if (!aiFormData.value.base_url || !aiFormData.value.api_key) {
    message.warning('请先填写 Base URL 和 API Key')
    return
  }
  refreshingModels.value = true
  try {
    const res: any = await api.aiListModels(aiFormData.value.api_key, aiFormData.value.base_url)
    if (res.success && Array.isArray(res.data)) {
      aiModelSuggestions.value = res.data
      if (res.data.length > 0 && !aiFormData.value.model) {
        aiFormData.value.model = res.data[0]
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

function resetAiForm() {
  aiFormData.value = {
    name: '',
    api_key: '',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-3.5-turbo',
    temperature: 0.7,
    max_tokens: 2048,
    system_prompt: '',
    is_default: false,
  }
  aiEditId.value = null
}

function openAddAiDialog() {
  resetAiForm()
  showAiDialog.value = true
}

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

// ── 快捷键设置 ──
const shortcutDefs = ref<ShortcutDef[]>(DEFAULT_SHORTCUTS)
const userShortcuts = ref<Record<string, string>>(loadShortcuts())
const editingShortcutId = ref<string | null>(null)
const editingShortcutValue = ref('')
const shortcutRecordTimer = ref<any>(null)

function getShortcutKey(id: string): string {
  return userShortcuts.value[id] || shortcutDefs.value.find(s => s.id === id)?.defaultKey || ''
}

function startEditShortcut(id: string) {
  editingShortcutId.value = id
  editingShortcutValue.value = getShortcutKey(id)
}

function recordKeydown(e: KeyboardEvent) {
  e.preventDefault()
  e.stopPropagation()
  if (e.key === 'Escape') {
    editingShortcutId.value = null
    return
  }
  if (e.key === 'Enter' && editingShortcutValue.value) {
    // 保存当前值
    if (editingShortcutId.value) {
      userShortcuts.value[editingShortcutId.value] = editingShortcutValue.value
      saveShortcuts(userShortcuts.value)
      message.success(`快捷键 "${shortcutDefs.value.find(s => s.id === editingShortcutId.value)?.label}" 已更新`)
    }
    editingShortcutId.value = null
    return
  }
  const parts: string[] = []
  if (e.ctrlKey || e.metaKey) parts.push('Mod')
  if (e.altKey) parts.push('Alt')
  if (e.shiftKey) parts.push('Shift')
  if (e.key && !['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) {
    const k = e.key.length === 1 ? e.key.toUpperCase() : e.key
    parts.push(k)
  }
  if (parts.length > 0) {
    editingShortcutValue.value = parts.join('-')
  }
}

function saveAllShortcuts() {
  saveShortcuts(userShortcuts.value)
  message.success('快捷键设置已保存')
}

function doResetShortcuts() {
  dialog.warning({
    title: '重置快捷键',
    content: '确定要重置所有快捷键为默认值吗？',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: () => {
      resetShortcuts()
      userShortcuts.value = {}
      message.success('已重置为默认快捷键')
    },
  })
}

// 保存设置
function saveSettings() {
  const settings = {
    theme: currentTheme.value,
    fontFamily: fontFamily.value,
    fontSize: fontSize.value,
  }
  localStorage.setItem('mdbs_settings', JSON.stringify(settings))
  // 立即生效 — 设置 data-theme 属性 & 更新 store
  document.documentElement.setAttribute('data-theme', currentTheme.value)
  store.themeId = currentTheme.value
  const root = document.documentElement
  root.style.setProperty('--editor-font', fontFamily.value)
  root.style.setProperty('--editor-font-size', fontSize.value + 'px')
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

// 返回：标签页模式下关闭自身，否则路由回退
function goBack() {
  if (store.activeTabId) {
    store.closeTab(store.activeTabId)
  } else {
    router.push('/connections')
  }
}

onMounted(() => {
  loadSettings()
  loadAiConfigs()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>设置</h2>
      <n-space>
        <n-button @click="saveSettings" type="primary">保存设置</n-button>
        <n-button @click="goBack">返回</n-button>
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
      <n-tab-pane name="ai" tab="AI 设置">
        <div style="padding: 16px 0">
          <n-space justify="space-between" style="margin-bottom: 16px">
            <p style="color: var(--color-text-secondary); margin: 0;">配置 AI 助手使用的 API Key、模型、接口地址等</p>
            <n-button type="primary" @click="openAddAiDialog">新增配置</n-button>
          </n-space>
          <n-data-table
            :columns="aiColumns"
            :data="aiConfigs"
            :loading="aiLoading"
            striped
          />
        </div>

        <!-- AI 配置对话框 -->
        <n-modal v-model:show="showAiDialog" :title="aiEditId ? '编辑 AI 配置' : '新增 AI 配置'" preset="card" style="width: 500px" :mask-closable="false">
          <n-form ref="aiFormRef" :model="aiFormData" label-placement="left" label-width="100">
            <n-form-item label="名称" path="name" :rule="{ required: true, message: '请输入配置名称', trigger: ['blur', 'input'] }">
              <n-input v-model:value="aiFormData.name" placeholder="配置名称" />
            </n-form-item>
            <n-form-item label="API Key">
              <n-input v-model:value="aiFormData.api_key" type="password" show-password-on="click" placeholder="sk-..." />
            </n-form-item>
            <n-form-item label="Base URL">
              <n-input v-model:value="aiFormData.base_url" placeholder="https://api.openai.com/v1" />
            </n-form-item>
            <n-form-item label="模型">
              <div style="display: flex; align-items: center; gap: 6px; width: 100%">
                <n-auto-complete v-model:value="aiFormData.model" :options="aiModelSuggestions" placeholder="gpt-3.5-turbo" style="flex: 1" />
                <n-button size="tiny" quaternary @click="refreshAiModels" :loading="refreshingModels" title="刷新模型列表">
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
              <n-slider v-model:value="aiFormData.temperature" :min="0" :max="2" :step="0.1" style="width: 200px" />
              <span style="margin-left: 12px">{{ aiFormData.temperature.toFixed(1) }}</span>
            </n-form-item>
            <n-form-item label="Max Tokens">
              <n-input-number v-model:value="aiFormData.max_tokens" :min="1" :max="128000" :step="100" style="width: 160px" />
            </n-form-item>
            <n-form-item label="系统提示词">
              <n-input v-model:value="aiFormData.system_prompt" type="textarea" :rows="3" placeholder="可选的系统提示词" />
            </n-form-item>
            <n-form-item label="设为默认">
              <n-switch v-model:value="aiFormData.is_default" />
            </n-form-item>
          </n-form>
          <template #footer>
            <n-space justify="space-between">
              <n-button @click="testAiConnection" :loading="aiTesting" :disabled="!aiFormData.api_key">测试连接</n-button>
              <n-space>
                <n-button @click="showAiDialog = false">取消</n-button>
                <n-button type="primary" @click="saveAiConfig">保存</n-button>
              </n-space>
            </n-space>
          </template>
        </n-modal>
      </n-tab-pane>

      <!-- 快捷键设置 -->
      <n-tab-pane name="shortcuts" tab="快捷键">
        <div style="padding: 16px 0; max-width: 600px;">
          <n-space justify="space-between" style="margin-bottom: 16px;">
            <p style="margin: 0; color: var(--color-text-secondary);">点击快捷键组合进行编辑，按 Esc 取消，按 Enter 保存</p>
            <n-space>
              <n-button size="tiny" @click="doResetShortcuts">重置为默认</n-button>
              <n-button size="tiny" type="primary" @click="saveAllShortcuts">保存快捷键</n-button>
            </n-space>
          </n-space>
          <n-list bordered>
            <n-list-item v-for="def in shortcutDefs" :key="def.id">
              <n-thing>
                <template #header>{{ def.label }}</template>
                <template #description>{{ def.description }}</template>
              </n-thing>
              <template #suffix>
                <div v-if="editingShortcutId === def.id" style="display: flex; align-items: center; gap: 4px;">
                  <input
                    :value="editingShortcutValue"
                    @keydown="recordKeydown"
                    placeholder="按下快捷键..."
                    style="width: 160px; padding: 4px 8px; border: 1px solid var(--color-accent); border-radius: 3px; background: var(--bg-input); color: inherit; font-family: monospace; font-size: 12px; text-align: center;"
                    autofocus
                  />
                </div>
                <n-tag
                  v-else
                  style="cursor: pointer; font-family: monospace;"
                  @click="startEditShortcut(def.id)"
                >
                  {{ getShortcutKey(def.id) }}
                </n-tag>
              </template>
            </n-list-item>
          </n-list>
        </div>
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
  background: var(--bg-toolbar);
  padding: 4px 8px;
  color: var(--color-text-muted);
}

.preview-body {
  flex: 1;
  display: flex;
}

.preview-sidebar {
  width: 80px;
  background: var(--bg-sidebar);
  padding: 8px;
  color: var(--color-text-muted);
}

.preview-workspace {
  flex: 1;
  background: var(--bg-app);
  padding: 8px;
  color: #777;
}

.preview-status {
  height: 20px;
  background: var(--bg-status);
  padding: 2px 8px;
  color: var(--color-text-muted);
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

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>