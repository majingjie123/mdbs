<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../api'

const message = useMessage()
const dialog = useDialog()

const props = defineProps<{
  connId: number
  dbName?: string
}>()

// ── 状态 ──
const plans = ref<any[]>([])
const loading = ref(false)
const connections = ref<any[]>([])
const showDialog = ref(false)
const editingPlan = ref<any>(null)
const saving = ref(false)

// 表单
const formData = ref({
  conn_id: props.connId || 0,
  name: '',
  database: props.dbName || '',
  schedule_type: 'daily',
  schedule_value: '02:00',
  options: ['structure', 'data'],
  enabled: true,
})

const scheduleTypeOptions = [
  { label: '每日', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '间隔分钟', value: 'interval' },
  { label: '一次性', value: 'once' },
]

const weekdayOptions = [
  { label: '周一', value: 0 },
  { label: '周二', value: 1 },
  { label: '周三', value: 2 },
  { label: '周四', value: 3 },
  { label: '周五', value: 4 },
  { label: '周六', value: 5 },
  { label: '周日', value: 6 },
]

const backupOptions = [
  { label: '结构', value: 'structure' },
  { label: '数据', value: 'data' },
]

// ── 加载 ──
async function loadPlans() {
  loading.value = true
  try {
    const res: any = await api.listBackupPlans(props.connId)
    if (res.success) {
      plans.value = (res.data || []).map((p: any) => ({
        ...p,
        options: typeof p.options === 'string' ? JSON.parse(p.options) : (p.options || []),
      }))
    }
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadConnections() {
  try {
    const res: any = await api.listConnections()
    if (res.success) connections.value = res.data || []
  } catch {}
}

function openCreateDialog() {
  editingPlan.value = null
  formData.value = {
    conn_id: props.connId || 0,
    name: '',
    database: props.dbName || '',
    schedule_type: 'daily',
    schedule_value: '02:00',
    options: ['structure', 'data'],
    enabled: true,
  }
  if (formData.value.conn_id === 0 && connections.value.length > 0) {
    formData.value.conn_id = connections.value[0].id
  }
  showDialog.value = true
}

function openEditDialog(plan: any) {
  editingPlan.value = plan
  formData.value = {
    conn_id: plan.conn_id,
    name: plan.name,
    database: plan.database,
    schedule_type: plan.schedule_type || 'daily',
    schedule_value: plan.schedule_value || '02:00',
    options: plan.options || ['structure', 'data'],
    enabled: !!plan.enabled,
  }
  showDialog.value = true
}

async function savePlan() {
  if (!formData.value.name || !formData.value.database) {
    message.warning('请填写计划名称和数据库')
    return
  }
  saving.value = true
  try {
    let res: any
    if (editingPlan.value) {
      res = await api.updateBackupPlan(editingPlan.value.id, formData.value)
    } else {
      res = await api.createBackupPlan(formData.value)
    }
    if (res.success) {
      message.success(editingPlan.value ? '计划已更新' : '计划已创建')
      showDialog.value = false
      await loadPlans()
    } else {
      message.error(res.message || '保存失败')
    }
  } catch (e: any) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function confirmDelete(plan: any) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除备份计划 "${plan.name}" 吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res: any = await api.deleteBackupPlan(plan.id)
        if (res.success) {
          message.success('已删除')
          await loadPlans()
        } else {
          message.error(res.message || '删除失败')
        }
      } catch (e: any) {
        message.error('删除失败')
      }
    },
  })
}

async function togglePlan(plan: any) {
  const enable = !plan.enabled
  try {
    const res: any = await api.toggleBackupPlan(plan.id, enable)
    if (res.success) {
      plan.enabled = enable
      message.success(enable ? '已启用' : '已禁用')
    } else {
      message.error(res.message || '操作失败')
    }
  } catch (e: any) {
    message.error('操作失败')
  }
}

async function runNow(plan: any) {
  try {
    const res: any = await api.runBackupPlanNow(plan.id)
    if (res.success) {
      message.success('备份任务已启动，请稍后查看 sync_logs 目录')
    } else {
      message.error(res.message || '启动失败')
    }
  } catch (e: any) {
    message.error('启动失败')
  }
}

function formatSchedule(plan: any): string {
  const type = plan.schedule_type
  const val = plan.schedule_value
  if (type === 'daily') return `每天 ${val}`
  if (type === 'weekly') {
    const parts = (val || '').split(' ')
    const day = parseInt(parts[0])
    const time1 = parts[1] || '00:00'
    const dayName = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][day] || '未知'
    return `每周${dayName} ${time1}`
  }
  if (type === 'interval') return `每 ${val} 分钟`
  if (type === 'once') return `一次性: ${val}`
  return val || '未知'
}

onMounted(() => {
  loadPlans()
  loadConnections()
})
</script>

<template>
  <div class="backup-plan-manager">
    <div class="header">
      <h2>⏰ 备份计划管理</h2>
      <n-space size="small">
        <n-button size="tiny" type="primary" @click="openCreateDialog">新建计划</n-button>
        <n-button size="tiny" @click="loadPlans">刷新</n-button>
      </n-space>
    </div>

    <n-spin :show="loading">
      <n-list v-if="plans.length > 0" bordered>
        <n-list-item v-for="plan in plans" :key="plan.id">
          <template #prefix>
            <n-tag
              :type="plan.enabled ? 'success' : 'default'"
              size="tiny"
              round
            >
              {{ plan.enabled ? '启用' : '禁用' }}
            </n-tag>
          </template>
          <n-thing :title="plan.name">
            <template #description>
              <n-space size="small" style="margin-top: 4px;">
                <n-tag size="tiny" type="info">{{ plan.database }}</n-tag>
                <n-tag size="tiny">{{ formatSchedule(plan) }}</n-tag>
                <span v-if="plan.last_run" style="font-size: 11px; color: var(--color-text-muted);">
                  上次: {{ plan.last_run }}
                </span>
                <span v-if="plan.next_run" style="font-size: 11px; color: var(--color-text-muted);">
                  下次: {{ plan.next_run }}
                </span>
              </n-space>
            </template>
          </n-thing>
          <template #suffix>
            <n-button-group size="tiny">
              <n-button
                size="tiny"
                :type="plan.enabled ? 'warning' : 'success'"
                @click="togglePlan(plan)"
              >
                {{ plan.enabled ? '禁用' : '启用' }}
              </n-button>
              <n-button size="tiny" @click="runNow(plan)">立即执行</n-button>
              <n-button size="tiny" @click="openEditDialog(plan)">编辑</n-button>
              <n-button size="tiny" type="error" @click="confirmDelete(plan)">删除</n-button>
            </n-button-group>
          </template>
        </n-list-item>
      </n-list>
      <n-empty v-else description="暂无备份计划" />
    </n-spin>

    <!-- 新建/编辑对话框 -->
    <n-modal v-model:show="showDialog" :title="editingPlan ? '编辑备份计划' : '新建备份计划'" preset="card" style="width: 520px;" :mask-closable="false">
      <n-form :model="formData" label-placement="left" label-width="100">
        <n-form-item label="连接" v-if="!props.connId">
          <n-select
            v-model:value="formData.conn_id"
            :options="connections.map((c: any) => ({ label: c.name, value: c.id }))"
            placeholder="选择数据库连接"
          />
        </n-form-item>
        <n-form-item label="计划名称" :rule="{ required: true, message: '请输入名称', trigger: 'blur' }">
          <n-input v-model:value="formData.name" placeholder="例如：每日凌晨备份" />
        </n-form-item>
        <n-form-item label="数据库">
          <n-input v-model:value="formData.database" placeholder="目标数据库" :disabled="!!props.dbName" />
        </n-form-item>
        <n-form-item label="计划类型">
          <n-select v-model:value="formData.schedule_type" :options="scheduleTypeOptions" />
        </n-form-item>
        <n-form-item label="时间/值">
          <template v-if="formData.schedule_type === 'daily'">
            <n-time-picker v-model:value="formData.schedule_value" format="HH:mm" placeholder="选择时间" />
          </template>
          <template v-else-if="formData.schedule_type === 'weekly'">
            <div style="display: flex; gap: 8px; align-items: center;">
              <n-select v-model:value="formData.schedule_value" :options="weekdayOptions" style="width: 100px;" />
              <n-time-picker v-model:value="formData.schedule_value" format="HH:mm" placeholder="时间" />
            </div>
          </template>
          <template v-else-if="formData.schedule_type === 'interval'">
            <n-input-number v-model:value="formData.schedule_value" :min="1" :max="10080" style="width: 160px;">
              <template #suffix>分钟</template>
            </n-input-number>
          </template>
          <template v-else>
            <n-date-picker v-model:value="formData.schedule_value" type="datetime" placeholder="选择执行时间" />
          </template>
        </n-form-item>
        <n-form-item label="备份内容">
          <n-checkbox-group v-model:value="formData.options">
            <n-checkbox value="structure">结构</n-checkbox>
            <n-checkbox value="data">数据</n-checkbox>
          </n-checkbox-group>
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="formData.enabled" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showDialog = false">取消</n-button>
          <n-button type="primary" @click="savePlan" :loading="saving">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.backup-plan-manager {
  padding: 16px;
  max-width: 800px;
}

.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.header h2 {
  margin: 0;
  font-size: 18px;
}
</style>
