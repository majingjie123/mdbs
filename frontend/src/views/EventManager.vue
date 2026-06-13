<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../api'

const message = useMessage()
const dialog = useDialog()

const props = defineProps<{
  connId: number
  eventName?: string
  dbName?: string
  schemaName?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

// ── 状态 ──
const events = ref<any[]>([])
const loading = ref(false)
const selectedEvent = ref<any>(null)
const ddlText = ref('')
const ddlLoading = ref(false)

// ── 新建/编辑对话框 ──
const showCreateDialog = ref(false)
const createLoading = ref(false)
const createSql = ref('-- 示例：CREATE EVENT my_event\n-- ON SCHEDULE EVERY 1 DAY\n-- STARTS CURRENT_TIMESTAMP\n-- DO\n--   DELETE FROM old_logs;\n')

// ── 加载列表 ──
async function loadEvents() {
  loading.value = true
  try {
    const res: any = await api.listEvents(props.connId, props.dbName, props.schemaName)
    if (res.success) {
      events.value = res.data || []
      if (props.eventName) {
        const found = events.value.find((e: any) => e.EVENT_NAME === props.eventName)
        if (found) selectedEvent.value = found
      }
    } else {
      message.error(res.message || '加载事件列表失败')
    }
  } catch (e: any) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// ── 加载 DDL ──
async function loadDDL(eventName: string) {
  ddlLoading.value = true
  ddlText.value = ''
  try {
    const res: any = await api.getEventDDL(props.connId, eventName, props.dbName)
    if (res.success) {
      ddlText.value = res.data || ''
    } else {
      ddlText.value = `-- ${res.message || '无法加载 DDL'}`
    }
  } catch (e: any) {
    ddlText.value = `-- ${e.message || '加载 DDL 失败'}`
  } finally {
    ddlLoading.value = false
  }
}

// ── 切换启用/禁用 ──
async function toggleEvent(event: any) {
  const enable = event.STATUS !== 'ENABLED'
  try {
    const res: any = await api.toggleEvent(props.connId, event.EVENT_NAME, enable, props.dbName)
    if (res.success) {
      message.success(res.message || (enable ? '已启用' : '已禁用'))
      event.STATUS = enable ? 'ENABLED' : 'DISABLED'
    } else {
      message.error(res.message || '切换失败')
    }
  } catch (e: any) {
    message.error(e.message || '切换失败')
  }
}

// ── 删除事件 ──
function confirmDrop(event: any) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除事件 "${event.EVENT_NAME}" 吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res: any = await api.dropEvent(props.connId, event.EVENT_NAME, props.dbName)
        if (res.success) {
          message.success(res.message || '删除成功')
          if (selectedEvent.value?.EVENT_NAME === event.EVENT_NAME) {
            selectedEvent.value = null
            ddlText.value = ''
          }
          await loadEvents()
        } else {
          message.error(res.message || '删除失败')
        }
      } catch (e: any) {
        message.error(e.message || '删除失败')
      }
    },
  })
}

// ── 创建事件 ──
async function doCreateEvent() {
  if (!createSql.value.trim() || createSql.value.startsWith('--')) {
    message.warning('请输入有效的 CREATE EVENT 语句')
    return
  }
  createLoading.value = true
  try {
    const res: any = await api.createEvent(props.connId, {
      event_sql: createSql.value,
      database: props.dbName,
    })
    if (res.success) {
      message.success('事件创建成功')
      showCreateDialog.value = false
      createSql.value = '-- 示例：CREATE EVENT my_event\n-- ON SCHEDULE EVERY 1 DAY\n-- STARTS CURRENT_TIMESTAMP\n-- DO\n--   DELETE FROM old_logs;\n'
      await loadEvents()
    } else {
      message.error(res.message || '创建失败')
    }
  } catch (e: any) {
    message.error(e.message || '创建失败')
  } finally {
    createLoading.value = false
  }
}

// ── 复制 DDL ──
function copyDDL() {
  if (ddlText.value) {
    navigator.clipboard.writeText(ddlText.value).then(() => {
      message.success('DDL 已复制到剪贴板')
    })
  }
}

// ── 选择事件 ──
function onSelectEvent(event: any) {
  selectedEvent.value = event
  loadDDL(event.EVENT_NAME)
}

onMounted(() => {
  loadEvents()
})
</script>

<template>
  <div class="event-manager">
    <div class="event-header">
      <h2>📅 事件管理</h2>
      <n-tag v-if="dbName" type="info" size="small">{{ dbName }}</n-tag>
      <n-space size="small">
        <n-button size="tiny" type="primary" @click="showCreateDialog = true">新建事件</n-button>
        <n-button size="tiny" @click="loadEvents">刷新</n-button>
        <n-button size="tiny" @click="$emit('close')" v-if="$emit">关闭</n-button>
      </n-space>
    </div>

    <div class="event-body">
      <!-- 左侧列表 -->
      <div class="event-list-panel">
        <n-spin :show="loading">
          <n-list v-if="events.length > 0" bordered>
            <n-list-item
              v-for="evt in events"
              :key="evt.EVENT_NAME"
              :class="{ active: selectedEvent?.EVENT_NAME === evt.EVENT_NAME }"
              @click="onSelectEvent(evt)"
              style="cursor: pointer;"
            >
              <template #prefix>
                <n-tag
                  :type="evt.STATUS === 'ENABLED' ? 'success' : 'default'"
                  size="tiny"
                  round
                >
                  {{ evt.STATUS === 'ENABLED' ? '启用' : '禁用' }}
                </n-tag>
              </template>
              <n-ellipsis>{{ evt.EVENT_NAME }}</n-ellipsis>
              <template #suffix>
                <n-button-group size="tiny">
                  <n-button
                    size="tiny"
                    :type="evt.STATUS === 'ENABLED' ? 'warning' : 'success'"
                    @click.stop="toggleEvent(evt)"
                  >
                    {{ evt.STATUS === 'ENABLED' ? '禁用' : '启用' }}
                  </n-button>
                  <n-button size="tiny" type="error" @click.stop="confirmDrop(evt)">删除</n-button>
                </n-button-group>
              </template>
              <n-thing>
                <template #description>
                  <n-space size="small">
                    <n-tag size="tiny">{{ evt.EVENT_TYPE }}</n-tag>
                    <n-tag v-if="evt.INTERVAL_FIELD" size="tiny">
                      {{ evt.INTERVAL_VALUE }} {{ evt.INTERVAL_FIELD }}
                    </n-tag>
                    <span v-if="evt.EVENT_COMMENT" style="color: var(--color-text-muted); font-size: 12px;">
                      {{ evt.EVENT_COMMENT }}
                    </span>
                  </n-space>
                </template>
              </n-thing>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无事件" />
        </n-spin>
      </div>

      <!-- 右侧详情 -->
      <div class="event-detail-panel">
        <template v-if="selectedEvent">
          <n-descriptions :title="selectedEvent.EVENT_NAME" bordered size="small" :column="2">
            <n-descriptions-item label="事件类型" :span="2">
              <n-tag :type="selectedEvent.EVENT_TYPE === 'RECURRING' ? 'primary' : 'info'">
                {{ selectedEvent.EVENT_TYPE === 'RECURRING' ? '循环' : '一次性' }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="执行间隔" v-if="selectedEvent.INTERVAL_FIELD">
              {{ selectedEvent.INTERVAL_VALUE }} {{ selectedEvent.INTERVAL_FIELD }}
            </n-descriptions-item>
            <n-descriptions-item label="执行时间" v-if="selectedEvent.EXECUTE_AT && selectedEvent.EXECUTE_AT !== 'None'">
              {{ selectedEvent.EXECUTE_AT }}
            </n-descriptions-item>
            <n-descriptions-item label="开始时间" v-if="selectedEvent.STARTS && selectedEvent.STARTS !== 'None'">
              {{ selectedEvent.STARTS }}
            </n-descriptions-item>
            <n-descriptions-item label="结束时间" v-if="selectedEvent.ENDS && selectedEvent.ENDS !== 'None'">
              {{ selectedEvent.ENDS }}
            </n-descriptions-item>
            <n-descriptions-item label="状态">
              <n-tag :type="selectedEvent.STATUS === 'ENABLED' ? 'success' : 'default'" round>
                {{ selectedEvent.STATUS === 'ENABLED' ? '已启用' : selectedEvent.STATUS === 'DISABLED' ? '已禁用' : selectedEvent.STATUS }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="完成时处理">
              {{ selectedEvent.ON_COMPLETION || 'NOT PRESERVE' }}
            </n-descriptions-item>
            <n-descriptions-item label="定义者">{{ selectedEvent.DEFINER }}</n-descriptions-item>
            <n-descriptions-item label="创建时间">{{ selectedEvent.CREATED }}</n-descriptions-item>
            <n-descriptions-item label="最近修改">{{ selectedEvent.LAST_ALTERED }}</n-descriptions-item>
            <n-descriptions-item label="备注" :span="2" v-if="selectedEvent.EVENT_COMMENT">
              {{ selectedEvent.EVENT_COMMENT }}
            </n-descriptions-item>
          </n-descriptions>

          <n-divider />

          <div class="ddl-section">
            <div class="ddl-header">
              <span style="font-weight: 600;">DDL 定义</span>
              <n-space size="small">
                <n-button size="tiny" @click="loadDDL(selectedEvent.EVENT_NAME)">刷新</n-button>
                <n-button size="tiny" @click="copyDDL">复制</n-button>
              </n-space>
            </div>
            <n-spin :show="ddlLoading">
              <n-pre class="ddl-pre">{{ ddlText || '暂无 DDL 定义' }}</n-pre>
            </n-spin>
          </div>
        </template>
        <n-empty v-else description="请从左侧选择一个事件" style="margin-top: 60px;" />
      </div>
    </div>

    <!-- 新建事件对话框 -->
    <n-modal v-model:show="showCreateDialog" title="新建事件" preset="card" style="width: 720px" :mask-closable="false">
      <n-space vertical>
        <n-alert type="info" closable>
          建议使用合法的 MySQL 事件语法。事件调度器将自动开启。
        </n-alert>
        <n-input
          v-model:value="createSql"
          type="textarea"
          :rows="12"
          placeholder="输入 CREATE EVENT 语句"
          :input-props="{ style: 'font-family: monospace; font-size: 13px;' }"
        />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showCreateDialog = false">取消</n-button>
          <n-button type="primary" @click="doCreateEvent" :loading="createLoading">创建</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.event-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
}

.event-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.event-header h2 {
  margin: 0;
  font-size: 18px;
}

.event-body {
  display: flex;
  flex: 1;
  gap: 12px;
  overflow: hidden;
}

.event-list-panel {
  width: 400px;
  min-width: 300px;
  overflow-y: auto;
  border-right: 1px solid var(--color-border);
  padding-right: 8px;
}

.event-detail-panel {
  flex: 1;
  overflow-y: auto;
}

.event-list-panel .n-list-item.active {
  background-color: var(--color-primary-opacity-1);
  border-radius: 4px;
}

.ddl-section {
  margin-top: 8px;
}

.ddl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.ddl-pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
