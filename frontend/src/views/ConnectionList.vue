<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import type { ConnInfo } from '../api'
import type { DataTableColumn } from 'naive-ui'

const router = useRouter()
const store = useAppStore()

const data = ref<(ConnInfo & { _loading?: boolean })[]>([])
const loading = ref(false)

const columns: DataTableColumn[] = [
  { title: '名称', key: 'name', width: 160 },
  { title: '类型', key: 'db_type', width: 100 },
  { title: '主机', key: 'host', width: 140 },
  { title: '端口', key: 'port', width: 80 },
  { title: '用户', key: 'user', width: 100 },
  { title: '默认库', key: 'database', width: 120 },
  { title: 'SSH', key: 'ssh_enabled', width: 70, render: (r: any) => (r.ssh_enabled ? '是' : '否') },
]

async function load() {
  loading.value = true
  try {
    await store.loadConnections()
    data.value = store.connections as any
  } finally {
    loading.value = false
  }
}

function goDetail(row: any) {
  router.push(`/connections/${row.id}`)
}

function goWorkbench(row: any) {
  router.push(`/workbench/${row.id}`)
}

async function remove(id: number) {
  await api.deleteConnection(id)
  await load()
}

function edit(row: any) {
  router.push(`/connections/${row.id}?edit=1`)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>连接管理</h2>
      <n-button type="primary" @click="router.push('/connections/0?edit=1')">
        新建连接
      </n-button>
    </div>

    <n-data-table
      :columns="columns"
      :data="data"
      :loading="loading"
      :row-key="(r: any) => r.id"
      :bordered="true"
      striped
      @update:row-key=""
      style="flex: 1"
    >
      <template #empty>
        <n-empty description="暂无连接，点击右上角新建" />
      </template>
    </n-data-table>

    <div v-if="data.length" class="actions-row">
      <template v-for="row in data" :key="row.id">
        <n-space class="row-actions" :style="{ marginTop: '8px' }">
          <n-button size="small" @click="goWorkbench(row)">SQL 工作台</n-button>
          <n-button size="small" @click="goDetail(row)">详情</n-button>
          <n-button size="small" @click="edit(row)">编辑</n-button>
          <n-popconfirm @positive-click="remove(row.id)">
            <template #trigger>
              <n-button size="small" type="error">删除</n-button>
            </template>
            确定删除连接 "{{ row.name }}"？
          </n-popconfirm>
        </n-space>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;
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
  font-weight: 600;
}

.actions-row {
  margin-top: 12px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.row-actions {
  padding: 4px 0;
}
</style>
