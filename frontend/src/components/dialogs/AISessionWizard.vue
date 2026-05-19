<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../../api'
import { useMessage } from 'naive-ui'
import { useAppStore } from '../../stores/app'

const props = withDefaults(defineProps<{
  show?: boolean
  connId?: number
  dbName?: string
}>(), {
  show: false,
  connId: 0,
  dbName: '',
})

const emit = defineEmits<{
  (e: 'update:show', val: boolean): void
  (e: 'done'): void
}>()

const message = useMessage()
const store = useAppStore()

// ── 步骤状态 ──
const step = ref(1) // 1: 选连接, 2: 选数据库, 3: 选表, 4: 确认
const connections = ref<any[]>([])
const databases = ref<string[]>([])
const allTables = ref<string[]>([])
const allViews = ref<string[]>([])
const loading = ref(false)

const selectedConnId = ref(props.connId)
const selectedDb = ref(props.dbName)
const selectedTables = ref<string[]>([])
const selectedViews = ref<string[]>([])

// 表/视图筛选
const tableFilterText = ref('')
const filteredAllTables = computed(() => {
  const q = tableFilterText.value.trim().toLowerCase()
  if (!q) return allTables.value
  return allTables.value.filter(t => t.toLowerCase().includes(q))
})
const filteredAllViews = computed(() => {
  const q = tableFilterText.value.trim().toLowerCase()
  if (!q) return allViews.value
  return allViews.value.filter(v => v.toLowerCase().includes(q))
})

// ── 加载连接列表 ──
async function loadConnections() {
  loading.value = true
  try {
    const res: any = await api.listConnections()
    if (res.success) connections.value = res.data || []
  } catch (e: any) {
    message.error('加载连接失败: ' + (e.message || ''))
  } finally {
    loading.value = false
  }
}

onMounted(() => { if (props.show) loadConnections() })
watch(() => props.show, (v) => { if (v) loadConnections() })

// ── 选择连接 → 加载数据库 ──
async function onConnSelect(id: number) {
  selectedConnId.value = id
  selectedDb.value = ''
  selectedTables.value = []
  selectedViews.value = []
  databases.value = []
  loading.value = true
  try {
    const res: any = await api.listDatabases(id)
    if (res.success) databases.value = res.data || []
    step.value = 2
  } catch (e: any) {
    message.error('加载数据库失败')
  } finally {
    loading.value = false
  }
}

// ── 选择数据库 → 加载表/视图 ──
async function onDbSelect(db: string) {
  selectedDb.value = db
  selectedTables.value = []
  selectedViews.value = []
  loading.value = true
  try {
    const [tRes, vRes] = await Promise.all([
      api.listTables(selectedConnId.value, db),
      api.listViews(selectedConnId.value, db),
    ])
    if (tRes.success) allTables.value = (tRes.data || []).map((t: any) => t.name || t)
    if (vRes.success) allViews.value = vRes.data || []
    step.value = 3
  } catch (e: any) {
    message.error('加载表失败')
  } finally {
    loading.value = false
  }
}

// ── 切换表选择 ──
function toggleTable(t: string) {
  const idx = selectedTables.value.indexOf(t)
  if (idx >= 0) selectedTables.value.splice(idx, 1)
  else selectedTables.value.push(t)
}

function toggleView(v: string) {
  const idx = selectedViews.value.indexOf(v)
  if (idx >= 0) selectedViews.value.splice(idx, 1)
  else selectedViews.value.push(v)
}

function selectAllTables() {
  if (selectedTables.value.length === allTables.value.length) {
    selectedTables.value = []
  } else {
    selectedTables.value = [...allTables.value]
  }
}

// ── 确认 ──
async function doConfirm() {
  if (!selectedConnId.value) return
  if (selectedTables.value.length === 0 && selectedViews.value.length === 0) {
    message.warning('请至少选择一张表或视图')
    return
  }
  loading.value = true
  try {
    // 打开 AI 助手标签，带上下文
    sessionStorage.setItem('ai_session_tables_' + selectedConnId.value, JSON.stringify({
      connId: selectedConnId.value,
      dbName: selectedDb.value,
      tables: selectedTables.value,
      views: selectedViews.value,
    }))
    store.openTab('ai-chat', 'AI 助手', {
      connId: selectedConnId.value,
      dbName: selectedDb.value,
      tableName: selectedTables.value[0] || '',
      _sessionTables: selectedTables.value,
      _sessionViews: selectedViews.value,
    })
    step.value = 1
    emit('update:show', false)
    emit('done')
    message.success(`已加载 ${selectedTables.value.length} 张表、${selectedViews.value.length} 个视图`)
  } finally {
    loading.value = false
  }
}

function close() { emit('update:show', false) }
</script>

<template>
  <n-modal :show="show" :on-update:show="(v: boolean) => emit('update:show', v)" :mask-closable="false" style="width:640px">
    <n-card title="🤖 AI 助手 - 初始化会话" :bordered="true" role="dialog" size="small">
      <template #header-extra>
        <n-button size="tiny" quaternary @click="close">✕</n-button>
      </template>

      <!-- 步骤指示器 -->
      <n-steps :current="step" size="small" style="margin-bottom:20px">
        <n-step title="选择连接" />
        <n-step title="选择数据库" />
        <n-step title="选择表/视图" />
        <n-step title="确认" />
      </n-steps>

      <!-- 步骤 1: 选连接 -->
      <div v-if="step === 1">
        <p style="color:#999;margin-bottom:12px">选择要分析的数据库连接：</p>
        <n-spin :show="loading">
          <n-list class="select-list">
            <n-list-item v-for="conn in connections" :key="conn.id" class="select-item" @click="onConnSelect(conn.id)">
              <div class="item-label">{{ conn.name }}</div>
              <div class="item-desc">{{ conn.db_type }} · {{ conn.host }}:{{ conn.port }}</div>
            </n-list-item>
            <n-empty v-if="!connections.length && !loading" description="暂无连接" />
          </n-list>
        </n-spin>
      </div>

      <!-- 步骤 2: 选数据库 -->
      <div v-if="step === 2">
        <p style="color:#999;margin-bottom:12px">选择数据库：</p>
        <n-spin :show="loading">
          <n-list class="select-list">
            <n-list-item v-for="db in databases" :key="db" class="select-item" @click="onDbSelect(db)">
              <div class="item-label">{{ db }}</div>
            </n-list-item>
            <n-empty v-if="!databases.length && !loading" description="无数据库" />
          </n-list>
        </n-spin>
      </div>

      <!-- 步骤 3: 选表/视图 -->
      <div v-if="step === 3">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <p style="color:#999;margin:0">选择要作为上下文的表和视图（勾选后 AI 可了解其结构）：</p>
          <n-space size="small">
            <n-badge :value="selectedTables.length + selectedViews.length" :max="99">
              <n-button size="tiny" type="primary" @click="step = 4">确认选择 ({{ selectedTables.length + selectedViews.length }})</n-button>
            </n-badge>
          </n-space>
        </div>

        <div style="margin-bottom:8px">
          <n-input v-model:value="tableFilterText" placeholder="搜索表名或视图名…" clearable size="small" />
        </div>
        <n-spin :show="loading">
          <div class="selection-area">
            <!-- 表列表 -->
            <n-collapse>
              <n-collapse-item title="📋 表" :key="'tables'">
                <template #header-extra>
                  <n-checkbox :checked="selectedTables.length === allTables.length && allTables.length > 0" @click.stop="selectAllTables" />
                </template>
                <div class="table-grid">
                  <div v-for="t in filteredAllTables" :key="t" class="table-chip" :class="{ selected: selectedTables.includes(t) }" @click="toggleTable(t)">
                    <n-checkbox :checked="selectedTables.includes(t)" @click.stop="toggleTable(t)" />
                    <span>{{ t }}</span>
                  </div>
                  <n-empty v-if="!filteredAllTables.length" description="无表" />
                </div>
              </n-collapse-item>
              <n-collapse-item title="👁️ 视图" :key="'views'">
                <div class="table-grid">
                  <div v-for="v in filteredAllViews" :key="v" class="table-chip" :class="{ selected: selectedViews.includes(v) }" @click="toggleView(v)">
                    <n-checkbox :checked="selectedViews.includes(v)" @click.stop="toggleView(v)" />
                    <span>{{ v }}</span>
                  </div>
                  <n-empty v-if="!filteredAllViews.length" description="无视图" />
                </div>
              </n-collapse-item>
            </n-collapse>
          </div>
        </n-spin>
      </div>

      <!-- 步骤 4: 确认 -->
      <div v-if="step === 4">
        <p style="color:#999;margin-bottom:12px">确认会话配置：</p>
        <n-description bordered size="small">
          <n-description-item label="连接">{{ connections.find(c => c.id === selectedConnId)?.name || selectedConnId }}</n-description-item>
          <n-description-item label="数据库">{{ selectedDb }}</n-description-item>
          <n-description-item label="已选表">{{ selectedTables.length ? selectedTables.join(', ') : '无' }}</n-description-item>
          <n-description-item label="已选视图">{{ selectedViews.length ? selectedViews.join(', ') : '无' }}</n-description-item>
        </n-description>

        <div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end">
          <n-button size="small" @click="step = 3">返回修改</n-button>
          <n-button size="small" type="primary" :loading="loading" @click="doConfirm">✅ 开始对话</n-button>
        </div>
      </div>

    </n-card>
  </n-modal>
</template>

<style scoped>
.select-list { max-height: 300px; overflow-y: auto; }
.select-item { cursor: pointer; }
.select-item:hover { background: #2a2a2a; }
.item-label { color: #e0e0e0; font-size: 14px; }
.item-desc { color: #888; font-size: 12px; margin-top: 2px; }

.selection-area { max-height: 350px; overflow-y: auto; }
.table-grid { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px 0; }
.table-chip {
  display: flex; align-items: center; gap: 4px;
  padding: 4px 8px; border-radius: 4px;
  background: #2a2a2a; cursor: pointer; font-size: 12px;
  border: 1px solid transparent;
}
.table-chip:hover { background: #333; border-color: #555; }
.table-chip.selected { background: #1a3a1a; border-color: #4caf50; }
</style>
