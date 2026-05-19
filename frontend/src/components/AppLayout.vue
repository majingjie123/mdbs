<script setup lang="ts">
import { ref, provide, defineAsyncComponent } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import { useAppStore } from '../stores/app'
import Sidebar from './Sidebar.vue'
import TabWorkspace from './TabWorkspace.vue'
import ExportDialog from './dialogs/ExportDialog.vue'
import ImportDialog from './dialogs/ImportDialog.vue'
import BackupDialog from './dialogs/BackupDialog.vue'
import SyncDialog from './dialogs/SyncDialog.vue'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const store = useAppStore()

// 动态加载 AIChat 组件
const AIChat = defineAsyncComponent(() => import('../views/AIChat.vue'))

// 菜单状态
const fileMenuVisible = ref(false)
const toolsMenuVisible = ref(false)
const editMenuVisible = ref(false)
const viewMenuVisible = ref(false)
const helpMenuVisible = ref(false)

// 对话框可见性
const showExport = ref(false)
const showImport = ref(false)
const showBackup = ref(false)
const showSync = ref(false)

// AI 助手右侧面板
const aiPanelExpanded = ref(false)

// 状态栏
const statusText = ref('就绪')
const statusConn = ref('')

provide('statusText', statusText)
provide('statusConn', statusConn)

// 切换 AI 面板
function toggleAIPanel() {
  aiPanelExpanded.value = !aiPanelExpanded.value
}

// ── 分割面板 ──
const splitPos = ref(260)
const isDragging = ref(false)
const containerRef = ref<HTMLElement | null>(null)

function onSplitMouseDown(e: MouseEvent) {
  e.preventDefault()
  isDragging.value = true
  document.addEventListener('mousemove', onSplitMouseMove)
  document.addEventListener('mouseup', onSplitMouseUp)
}

function onSplitMouseMove(e: MouseEvent) {
  if (!isDragging.value || !containerRef.value) return
  const rect = containerRef.value.getBoundingClientRect()
  let x = e.clientX - rect.left
  x = Math.max(180, Math.min(x, rect.width - 200))
  splitPos.value = x
}

function onSplitMouseUp() {
  isDragging.value = false
  document.removeEventListener('mousemove', onSplitMouseMove)
  document.removeEventListener('mouseup', onSplitMouseUp)
}

// ── 菜单 ──
function toggleFileMenu(e: MouseEvent) {
  e.stopPropagation()
  fileMenuVisible.value = !fileMenuVisible.value
  toolsMenuVisible.value = false
  editMenuVisible.value = false
  viewMenuVisible.value = false
  helpMenuVisible.value = false
}

function toggleToolsMenu(e: MouseEvent) {
  e.stopPropagation()
  toolsMenuVisible.value = !toolsMenuVisible.value
  fileMenuVisible.value = false
  editMenuVisible.value = false
  viewMenuVisible.value = false
  helpMenuVisible.value = false
}

function toggleEditMenu(e: MouseEvent) {
  e.stopPropagation()
  editMenuVisible.value = !editMenuVisible.value
  fileMenuVisible.value = false
  toolsMenuVisible.value = false
  viewMenuVisible.value = false
  helpMenuVisible.value = false
}

function toggleViewMenu(e: MouseEvent) {
  e.stopPropagation()
  viewMenuVisible.value = !viewMenuVisible.value
  fileMenuVisible.value = false
  toolsMenuVisible.value = false
  editMenuVisible.value = false
  helpMenuVisible.value = false
}

function toggleHelpMenu(e: MouseEvent) {
  e.stopPropagation()
  helpMenuVisible.value = !helpMenuVisible.value
  fileMenuVisible.value = false
  toolsMenuVisible.value = false
  editMenuVisible.value = false
  viewMenuVisible.value = false
}

function closeMenus() {
  fileMenuVisible.value = false
  toolsMenuVisible.value = false
  editMenuVisible.value = false
  viewMenuVisible.value = false
  helpMenuVisible.value = false
}

// 文件菜单操作
function goNewConnection() {
  closeMenus()
  store.openTab('connection-detail', '新建连接', { id: 0, edit: 1 }, true)
}

function goImport() { closeMenus(); showImport.value = true }
function goExport() { closeMenus(); showExport.value = true }
function goBackupRestore() { closeMenus(); showBackup.value = true }
function goSync() { closeMenus(); showSync.value = true }
function goSyncHistory() { closeMenus(); showSync.value = true }
function goSettings() { closeMenus(); store.openTab('settings', '设置', {}, true) }
function goAISettings() { closeMenus(); store.openTab('ai-settings', 'AI 设置', {}, true) }
function goAIChat() {
  closeMenus()
  store.openTab('ai-chat', 'AI 助手', {
    connId: store.selectedNode.connId,
    dbName: store.selectedNode.dbName,
    schemaName: store.selectedNode.schemaName,
    tableName: store.selectedNode.tableName,
    nodeType: store.selectedNode.nodeType,
    connName: store.selectedNode.connName,
  })
}
function confirmExit() { closeMenus(); window.close() }

// 编辑菜单
function goUndo() { closeMenus(); message.info('撤销 (Ctrl+Z)') }
function goRedo() { closeMenus(); message.info('重做 (Ctrl+Shift+Z)') }
function goFind() { closeMenus(); message.info('查找 (Ctrl+F)') }
function goSelectAll() { closeMenus(); message.info('全选 (Ctrl+A)') }

// 视图菜单
function toggleSidebar() {
  closeMenus()
  // 通过查询选择器中 sidebar 的 collapsed 状态切换
  document.querySelector('.sidebar')?.classList.toggle('collapsed')
}
function goFullscreen() {
  closeMenus()
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {})
  } else {
    document.exitFullscreen().catch(() => {})
  }
}

// 帮助菜单
function goAbout() {
  closeMenus()
  dialog.info({
    title: '关于 MDBS',
    content: 'MDBS v1.0\n智能数据库连接管理工具\n\n基于 FastAPI + Vue3',
  })
}
function goShortcuts() {
  closeMenus()
  dialog.info({
    title: '快捷键参考',
    content: [
      'F5 / Ctrl+Enter   执行 SQL',
      'Ctrl+S            保存草稿',
      'Ctrl+F            查找',
      'Ctrl+Shift+F      格式化 SQL',
      'Ctrl+Shift+S      全部保存',
    ].join('\n'),
  })
}
</script>

<template>
  <div class="app-layout" @click="closeMenus">
    <!-- 顶部菜单栏 -->
    <header class="menu-bar">
      <div class="menu-left">
        <div class="menu-item" @click="toggleFileMenu">
          <span class="menu-label">文件</span>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M0 0l5 6 5-6z"/></svg>
          <div v-if="fileMenuVisible" class="dropdown-menu" @click.stop>
            <div class="dropdown-item" @click="goNewConnection">新增连接</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="goImport">导入数据...</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="goExport">导出...</div>
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
          <div v-if="toolsMenuVisible" class="dropdown-menu" @click.stop>
            <div class="dropdown-item" @click="goSync">数据库同步</div>
            <div class="dropdown-item" @click="goSync">同步表结构</div>
            <div class="dropdown-item" @click="goSyncHistory">同步历史记录</div>
          </div>
        </div>
        <div class="menu-item" @click="toggleEditMenu">
          <span class="menu-label">编辑</span>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M0 0l5 6 5-6z"/></svg>
          <div v-if="editMenuVisible" class="dropdown-menu" @click.stop>
            <div class="dropdown-item" @click="goUndo">撤销</div>
            <div class="dropdown-item" @click="goRedo">重做</div>
            <div class="dropdown-separator"></div>
            <div class="dropdown-item" @click="goFind">查找...</div>
            <div class="dropdown-item" @click="goSelectAll">全选</div>
          </div>
        </div>
        <div class="menu-item" @click="toggleViewMenu">
          <span class="menu-label">视图</span>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M0 0l5 6 5-6z"/></svg>
          <div v-if="viewMenuVisible" class="dropdown-menu" @click.stop>
            <div class="dropdown-item" @click="toggleSidebar">切换侧栏</div>
            <div class="dropdown-item" @click="goFullscreen">全屏</div>
          </div>
        </div>
        <div class="menu-item" @click="toggleHelpMenu">
          <span class="menu-label">帮助</span>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor"><path d="M0 0l5 6 5-6z"/></svg>
          <div v-if="helpMenuVisible" class="dropdown-menu" @click.stop>
            <div class="dropdown-item" @click="goAbout">关于 MDBS</div>
            <div class="dropdown-item" @click="goShortcuts">快捷键参考</div>
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

    <!-- 分隔线 -->
    <div class="menu-sep"></div>

    <!-- 主区域（可拖拽分割） -->
    <div ref="containerRef" class="main-area" :class="{ dragging: isDragging }">
      <div class="sidebar-wrapper" :style="{ width: splitPos + 'px' }">
        <Sidebar />
      </div>
      <!-- 拖拽手柄 -->
      <div class="split-handle" @mousedown="onSplitMouseDown"></div>
      <!-- 工作区 -->
      <div class="workspace-wrapper">
        <TabWorkspace />
      </div>
      <!-- AI 切换竖条 -->
      <div class="ai-toggle-strip" :class="{ active: aiPanelExpanded }" @click="toggleAIPanel" title="AI 助手">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 1a7 7 0 100 14A7 7 0 008 1zM6.5 5.5a1.5 1.5 0 113 0 1.5 1.5 0 01-3 0zM9.5 8a.5.5 0 01.5.5v3a.5.5 0 01-1 0v-3a.5.5 0 01.5-.5zM8 11c-1.657 0-3 1.343-3 3h6c0-1.657-1.343-3-3-3z"/>
        </svg>
      </div>
      <!-- 右侧 AI 面板 -->
      <div class="ai-panel" :class="{ expanded: aiPanelExpanded }">
        <div class="ai-panel-header">
          <span>AI 助手</span>
          <button class="ai-panel-close" @click="aiPanelExpanded = false">×</button>
        </div>
        <div class="ai-panel-content">
          <AIChat
            :conn-id="store.selectedNode.connId"
            :db-name="store.selectedNode.dbName"
            :schema-name="store.selectedNode.schemaName"
            :table-name="store.selectedNode.tableName"
            :node-type="store.selectedNode.nodeType"
            :conn-name="store.selectedNode.connName"
          />
        </div>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <footer class="status-bar">
      <span class="status-text">{{ statusText }}</span>
      <span v-if="statusConn" class="status-conn">{{ statusConn }}</span>
    </footer>

    <!-- 全局对话框 -->
    <ExportDialog v-model:visible="showExport" />
    <ImportDialog v-model:visible="showImport" />
    <BackupDialog v-model:visible="showBackup" />
    <SyncDialog v-model:visible="showSync" />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-app);
  color: var(--color-text);
  font-size: 13px;
  overflow: hidden;
}

/* ── 菜单栏 ── */
.menu-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 30px;
  min-height: 30px;
  background: var(--bg-toolbar);
  padding: 0 8px;
  user-select: none;
  flex-shrink: 0;
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
  color: var(--color-text-menu);
  font-size: 12px;
}

.menu-item:hover {
  background: var(--bg-hover);
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
  color: var(--color-icon);
  display: flex;
  align-items: center;
}

.menu-icon-btn:hover {
  background: var(--bg-hover);
  color: #ffffff;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 200px;
  background: var(--bg-dropdown);
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  padding: 4px 0;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.dropdown-item {
  padding: 6px 16px;
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: 12px;
  white-space: nowrap;
}

.dropdown-item:hover {
  background: var(--bg-hover);
  color: #ffffff;
}

.dropdown-separator {
  height: 1px;
  background: var(--color-border-light);
  margin: 4px 8px;
}

.menu-sep {
  height: 1px;
  background: var(--color-border);
  flex-shrink: 0;
}

/* ── 主区域 ── */
.main-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.main-area.dragging {
  cursor: col-resize;
}

.sidebar-wrapper {
  flex-shrink: 0;
  overflow: hidden;
}

.split-handle {
  width: 4px;
  cursor: col-resize;
  background: transparent;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  transition: background 0.15s;
}

.split-handle:hover,
.main-area.dragging .split-handle {
  background: var(--color-accent);
}

.workspace-wrapper {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── 状态栏 ── */
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 24px;
  min-height: 24px;
  background: var(--bg-status);
  padding: 0 12px;
  font-size: 12px;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border);
  flex-shrink: 0;
}

.status-conn {
  color: var(--color-conn-online);
}

/* ── AI 切换竖条 ── */
.ai-toggle-strip {
  width: 0;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-text-muted);
  background: var(--bg-ai-strip);
  border-left: 1px solid var(--color-border);
  transition: width 0.2s ease, color 0.15s, background 0.15s;
  writing-mode: vertical-lr;
  user-select: none;
  overflow: hidden;
}

.ai-toggle-strip:hover {
  width: 22px;
  color: var(--color-accent-alt);
  background: var(--bg-hover);
}

.ai-toggle-strip.active {
  width: 22px;
  color: var(--color-accent-alt);
  background: var(--bg-ai-panel);
  border-left-color: var(--color-accent-alt);
}

/* ── AI 面板 ── */
.ai-panel {
  width: 0;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--bg-ai-panel);
  border-left: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
}

.ai-panel.expanded {
  width: 400px;
  min-width: 300px;
  max-width: 600px;
}

.ai-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-ai-header);
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.ai-panel-close {
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 16px;
  padding: 2px 6px;
  border-radius: 3px;
  line-height: 1;
}

.ai-panel-close:hover {
  background: var(--bg-hover);
  color: #fff;
}

.ai-panel-content {
  flex: 1;
  overflow: hidden;
}

/* 菜单图标激活状态 */
.menu-icon-btn.active {
  background: var(--bg-hover);
  color: var(--color-accent);
}
</style>