<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { api } from '../api'

const props = defineProps<{
  connId: number
  dbName?: string
  schemaName?: string
}>()

const message = useMessage()
const dialog = useDialog()
const sequences = ref<any[]>([])
const loading = ref(false)
const ddlVisible = ref(false)
const ddlContent = ref('')
const ddlTitle = ref('')
const showCreate = ref(false)
const createForm = ref({ sequence_name: '', start_value: 1, increment: 1, min_value: 1, max_value: 9223372036854775807, cache_value: 1, cycle: false })
const creating = ref(false)

async function load() {
  if (!props.connId) return
  loading.value = true
  try {
    const res: any = await api.listSequences(props.connId, props.dbName, props.schemaName)
    if (res.success) sequences.value = res.data || []
    else message.warning(res.message)
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function viewDDL(seq: any) {
  ddlTitle.value = seq.sequence_name
  ddlContent.value = '加载中...'
  ddlVisible.value = true
  try {
    const res: any = await api.getSequenceDDL(props.connId, seq.sequence_name, props.dbName, props.schemaName)
    if (res.success) ddlContent.value = res.data || '-- 无 DDL'
    else ddlContent.value = '-- ' + res.message
  } catch (e: any) {
    ddlContent.value = '-- ' + e.message
  }
}

function confirmDrop(seq: any) {
  dialog.warning({
    title: '删除序列',
    content: `确定要删除序列 "${seq.sequence_name}" 吗？`,
    positiveText: '确定删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res: any = await api.dropSequence(props.connId, seq.sequence_name, props.dbName, props.schemaName)
        if (res.success) {
          message.success(res.message)
          await load()
        } else {
          message.warning(res.message)
        }
      } catch (e: any) {
        message.error(e.message)
      }
    },
  })
}

async function doCreate() {
  if (!createForm.value.sequence_name.trim()) {
    message.warning('请输入序列名称')
    return
  }
  creating.value = true
  try {
    const res: any = await api.createSequence(props.connId, createForm.value, props.dbName, props.schemaName)
    if (res.success) {
      message.success(res.message)
      showCreate.value = false
      createForm.value = { sequence_name: '', start_value: 1, increment: 1, min_value: 1, max_value: 9223372036854775807, cache_value: 1, cycle: false }
      await load()
    } else {
      message.warning(res.message)
    }
  } catch (e: any) {
    message.error(e.message)
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="seq-manager">
    <div class="header">
      <h2>🔢 序列管理</h2>
      <n-space>
        <n-button size="small" @click="load" :loading="loading" secondary>刷新</n-button>
        <n-button size="small" type="primary" @click="showCreate = true">新建序列</n-button>
      </n-space>
    </div>

    <n-alert type="info" closable style="margin-bottom:12px">
      <template #header>PostgreSQL 序列管理</template>
      序列用于生成自增数字，通常作为表的主键。
    </n-alert>

    <n-data-table
      :columns="[
        { title: '名称', key: 'sequence_name', ellipsis: true },
        { title: '架构', key: 'schema_name', width: 80 },
        { title: '所有者', key: 'owner', width: 80 },
        { title: '起始值', key: 'start_value', width: 70 },
        { title: '递增量', key: 'increment', width: 70 },
        { title: '最小值', key: 'min_value', width: 70 },
        { title: '最大值', key: 'max_value', width: 100 },
        { title: '缓存', key: 'cache_value', width: 60 },
        { title: '循环', key: 'cycle', width: 60, render: (row: any) => row.cycle ? '是' : '否' },
        { title: '操作', key: 'actions', width: 130, render: (row: any) => h('div', { style: 'display:flex;gap:4px' }, [
          h('n-button', { size: 'tiny', quaternary: true, onClick: () => viewDDL(row) }, 'DDL'),
          h('n-button', { size: 'tiny', quaternary: true, type: 'error', onClick: () => confirmDrop(row) }, '删除'),
        ]) },
      ]"
      :data="sequences"
      :loading="loading"
      size="small"
      striped
      :max-height="400"
    >
      <template #empty>
        <n-empty description="暂无序列" />
      </template>
    </n-data-table>

    <!-- DDL 抽屉 -->
    <n-drawer v-model:show="ddlVisible" :width="500" placement="right">
      <n-drawer-content :title="ddlTitle" closable>
        <n-code :code="ddlContent" language="sql" />
      </n-drawer-content>
    </n-drawer>

    <!-- 新建序列对话框 -->
    <n-modal v-model:show="showCreate" preset="card" title="新建序列" style="width:500px" :mask-closable="false">
      <n-space vertical>
        <n-form-item label="序列名称">
          <n-input v-model:value="createForm.sequence_name" placeholder="例如: user_id_seq" />
        </n-form-item>
        <n-grid :cols="2" :x-gap="12">
          <n-gi>
            <n-form-item label="起始值">
              <n-input-number v-model:value="createForm.start_value" :min="1" style="width:100%" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="递增量">
              <n-input-number v-model:value="createForm.increment" :min="1" style="width:100%" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-grid :cols="2" :x-gap="12">
          <n-gi>
            <n-form-item label="最小值">
              <n-input-number v-model:value="createForm.min_value" :min="1" style="width:100%" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="最大值">
              <n-input-number v-model:value="createForm.max_value" :min="1" style="width:100%" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-form-item label="缓存值">
          <n-input-number v-model:value="createForm.cache_value" :min="1" style="width:100%" />
        </n-form-item>
        <n-form-item label="循环">
          <n-switch v-model:value="createForm.cycle" />
        </n-form-item>
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" @click="doCreate" :loading="creating">创建</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.seq-manager {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.header h2 {
  margin: 0;
  font-size: 18px;
}
</style>
