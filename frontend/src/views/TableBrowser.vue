<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import type { ColumnDetail } from '../api'

const route = useRoute()
const connId = parseInt(route.params.connId as string)
const tableName = route.params.table as string
const dbName = (route.query.db as string) || ''

const columns = ref<ColumnDetail[]>([])
const ddl = ref('')
const indexes = ref<any[]>([])
const loading = ref(false)
const activeTab = ref('columns')

onMounted(async () => {
  loading.value = true
  try {
    const [colRes, ddlRes, idxRes] = await Promise.all([
      api.getTableColumns(connId, tableName, dbName),
      api.getTableDDL(connId, tableName, dbName),
      api.getTableIndexes(connId, tableName, dbName),
    ])
    if (colRes.success && colRes.data) columns.value = colRes.data
    if (ddlRes.success && ddlRes.data) ddl.value = ddlRes.data
    if (idxRes.success && idxRes.data) indexes.value = idxRes.data
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>{{ tableName }}</h2>
      <n-tag v-if="dbName" type="info" size="small">{{ dbName }}</n-tag>
    </div>

    <n-tabs v-model:value="activeTab" type="line">
      <n-tab-pane name="columns" tab="字段">
        <n-data-table
          :columns="[
            { title: '字段名', key: 'Field', width: 160 },
            { title: '类型', key: 'Type', width: 180 },
            { title: '排序规则', key: 'Collation', width: 140 },
            { title: '允许NULL', key: 'Null', width: 90 },
            { title: '键', key: 'Key', width: 70 },
            { title: '默认值', key: 'Default', width: 120 },
            { title: '自增', key: 'Extra', width: 100 },
            { title: '注释', key: 'Comment' },
          ]"
          :data="columns"
          :loading="loading"
          :bordered="true"
          striped
        />
      </n-tab-pane>

      <n-tab-pane name="indexes" tab="索引">
        <n-data-table
          :columns="[
            { title: '索引名', key: 'Key_name', width: 160 },
            { title: '字段', key: 'Column_name', width: 160 },
            { title: '唯一', key: 'Non_unique', width: 70, render: (r: any) => (r.Non_unique === 0 ? '是' : '否') },
            { title: '类型', key: 'Index_type', width: 100 },
            { title: '主键', key: 'Is_Primary', width: 70, render: (r: any) => (r.Is_Primary ? '是' : '-') },
          ]"
          :data="indexes"
          :loading="loading"
          :bordered="true"
          striped
        />
      </n-tab-pane>

      <n-tab-pane name="ddl" tab="DDL">
        <n-code :code="ddl" language="sql" />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.page {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.page-header h2 {
  color: #e0e0e0;
  font-size: 20px;
}
</style>
