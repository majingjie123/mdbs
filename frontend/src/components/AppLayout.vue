<script setup lang="ts">
import { ref, provide } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import Sidebar from './Sidebar.vue'

const router = useRouter()
const message = useMessage()

// 菜单状态
const fileMenuVisible = ref(false)
const toolsMenuVisible = ref(false)

// 状态栏
const statusText = ref('就绪')
const statusConn = ref('')

// 提供状态给子组件
provide('statusText', statusText)
provide('statusConn', statusConn)

function toggleFileMenu(e: MouseEvent) {
  e.stopPropagation()
  fileMenuVisible.value = !fileMenuVisible.value
  toolsMenuVisible.value = false
}

function toggleToolsMenu(e: MouseEvent) {
  e.stopPropagation()
  toolsMenuVisible.value = !toolsMenuVisible.value
  fileMenuVisible.value = false
}

function closeMenus() {
  fileMenuVisible.value = false
  toolsMenuVisible.value = false
}

// 菜单操作
function goNewConnection() {
  closeMenus()
  router.push('/connections/0?edit=1')
}

function goImport() { closeMenus(); message.info('导入功能开发中') }
function goExportStructure() { closeMenus(); message.info('导出表结构功能开发中') }
function goExportER() { closeMenus(); message.info('导出 ER 图功能开发中') }
function goExportExcel() { closeMenus(); message.info('导出 Excel 功能开发中') }
function goExportNavicat() { closeMenus(); message.info('导出 Navicat 功能开发中') }
function goBackupRestore() { closeMenus(); message.info('备份/恢复功能开发中') }
function goAISettings() { closeMenus(); message.info('AI 设置功能开发中') }
function goSync() { closeMenus(); message.info('数据库同步功能开发中') }
function goStructureSync() { closeMenus(); message.info('同步表结构功能开发中') }
function goSyncHistory() { closeMenus(); message.info('同步历史功能开发中') }
function goSettings() { closeMenus(); router.push('/settings') }
function confirmExit() { closeMenus(); window.close() }
</script>

<template>
  <div class="app-layout" @click="closeMenus">
    <!-- 顶部菜单栏 -->
    <header class="menu-bar">
      <div class="menu-left">
        <div class="menu-item" @click="toggleFileMenu">
          <span class="menu-label">文件</span>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M0 0l5 6 5-6z"/></svg>
          <!-- 文件下拉菜单 -->
          <div v-if="fileMenuVisible" class="dropdown-menu" @click.stop>
            <div class="dropdown-item" @click="goNewConnection">新增连接</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="goImport">导入数据...</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="goExportStructure">导出表结构...</div>
            <div class="dropdown-item" @click="goExportER">导出 ER 图...</div>
            <div class="dropdown-item" @click="goExportExcel">导出连接 (Excel)</div>
            <div class="dropdown-item" @click="goExportNavicat">导出为 Navicat (.ncx)</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="goBackupRestore">备份 / 恢复...</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="goAISettings">AI 设置</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="confirmExit">退出</div>
          </div>
        </div>
        <div class="menu-item" @click="toggleToolsMenu">
          <span class="menu-label">工具</span>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M0 0l5 6 5-6z"/></svg>
          <!-- 工具下拉菜单 -->
          <div v-if="toolsMenuVisible" class="dropdown-menu" @click.stop>
            <div class="dropdown-item" @click="goSync">数据库同步</div>
            <div class="dropdown-item" @click="goStructureSync">同步表结构</div>
            <div class="dropdown-item" @click="goSyncHistory">同步历史记录</div>
          </div>
        </div>
      </div>
      <div class="menu-right">
        <div class="menu-icon-btn" @click.stop="goSettings" title="设置">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 10a2 2 0 100-4 2 2 0 000 4zm6.32-3.38l-1.1-.48a6.18 6.18 0 00-.38-.9l.5-1.08a.5.5 0 00-.12-.56l-1.2-1.2a.5.5 0 00-.56-.12l-1.08.5a6.18 6.18 0 00-.9-.38l-.48-1.1a.5.5 0 00-.47-.34H8.38a.5.5 0 00-.47.34l-.48 1.1a6.18 6.18 0 00-.9.38l-1.08-.5a.5.5 0 00-.56.12L3.7 4.6a.5.5 0 00-.12.56l.5 1.08a6.18 6.18 0 00-.38.9l-1.1.48a.5.5 0 00-.34.47v1.72a.5.5 0 00.34.47l1.1.48c.1.32.22.62.38.9l-.5 1.08a.5.5 0 00.12.56l1.2 1.2a.5.5 0 00.56.12l1.08-.5c.28.16.58.28.9.38l.48 1.1a.5.5 0 00.47.34h1.72a.5.5 0 00.47-.34l.48-1.1c.32-.1.62-.22.9-.38l1.08.5a.5.5 0 00.56-.12l1.2-1.2a.5.5 0 00.12-.56l-.5-1.08c.16-.28.28-.58.38-.9l1.1-.48a.5.5 0 00.34-.47V7.1a.5.5 0 00-.34-.48z"/>
          </svg>
        </div>
      </div>
    </header>

    <!-- 1px 分隔线 -->
    <div class="menu-sep"></div>

    <!-- 主区域 -->
    <div class="main-area">
      <Sidebar />
      <main class="workspace">
        <RouterView />
      </main>
    </div>

    <!-- 底部状态栏 -->
    <footer class="status-bar">
      <span class="status-text">{{ statusText }}</span>
      <span v-if="statusConn" class="status-conn">{{ statusConn }}</span>
    </footer>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #1e1e1e;
  color: #e0e0e0;
  font-size: 13px;
}

/* 菜单栏 */
.menu-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 30px;
  min-height: 30px;
  background: #3c3f41;
  padding: 0 8px;
  user-select: none;
}

.menu-left {
  display: flex;
  align-items: center;
  gap: 2px;
}

.menu-item {
  position: relative;
  padding: 4px 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 3px;
  color: #bbbbbb;
  font-size: 12px;
}

.menu-item:hover {
  background: #4c4f51;
  color: #ffffff;
}

.menu-right {
  display: flex;
  align-items: center;
}

.menu-icon-btn {
  padding: 4px 6px;
  cursor: pointer;
  border-radius: 3px;
  color: #bbbbbb;
  display: flex;
  align-items: center;
}

.menu-icon-btn:hover {
  background: #4c4f51;
  color: #ffffff;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 200px;
  background: #3c3f41;
  border: 1px solid #555555;
  border-radius: 4px;
  padding: 4px 0;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.dropdown-item {
  padding: 6px 16px;
  cursor: pointer;
  color: #cccccc;
  font-size: 12px;
  white-space: nowrap;
}

.dropdown-item:hover {
  background: #4c4f51;
  color: #ffffff;
}

.dropdown-separator {
  height: 1px;
  background: #555555;
  margin: 4px 8px;
}

.menu-sep {
  height: 1px;
  background: #3c3c3c;
}

.main-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.workspace {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 24px;
  min-height: 24px;
  background: #3c3f41;
  padding: 0 12px;
  font-size: 12px;
  color: #999999;
  border-top: 1px solid #3c3c3c;
}

.status-conn {
  color: #6a9955;
}
</style>
