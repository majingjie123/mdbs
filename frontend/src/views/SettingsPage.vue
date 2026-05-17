<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'

const router = useRouter()
const message = useMessage()

const themeOptions = [
  { label: '默认', value: 'default' },
  { label: '暗黑模式', value: 'dark' },
  { label: '黑客绿', value: 'hacker' },
  { label: '护眼绿', value: 'eye' },
  { label: '清新蓝', value: 'blue' },
  { label: '深海蓝', value: 'deepblue' },
  { label: '优雅紫', value: 'purple' },
  { label: '落日橙', value: 'orange' },
  { label: '樱花粉', value: 'pink' },
]
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>设置</h2>
      <n-button @click="router.push('/connections')">返回</n-button>
    </div>
    <div class="placeholder">
      <n-empty description="设置页面开发中" />
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
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
.placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
