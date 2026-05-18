<script setup lang="ts">
import { ref, onMounted, onUnmounted, markRaw, defineAsyncComponent } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore, type TabItem } from '../stores/app'
import { useMessage } from 'naive-ui'

const store = useAppStore()
const router = useRouter()
const message = useMessage()

// ── 组件映射 ──
const componentMap: Record<string, any> = {
  'sql-workbench': markRaw(defineAsyncComponent(() => import('../views/SQLWorkbench.vue'))),
  'table-browser': markRaw(defineAsyncComponent(() => import('../views/TableBrowser.vue'))),
  'ai-chat': markRaw(defineAsyncComponent(() => import('../views/AIChat.vue'))),
  'connection-list': markRaw(defineAsyncComponent(() => import('../views/ConnectionList.vue'))),
  'connection-detail': markRaw(defineAsyncComponent(() => import('../views/ConnectionDetail.vue'))),
  'ai-settings': markRaw(defineAsyncComponent(() => import('../views/AISettingsPage.vue'))),
}

// ── 右键菜单 ──
const tabCtxMenu = ref({ visible: false, x: 0, y: 0, tabId: '' })

function onTabContextMenu(e: MouseEvent, tab: TabItem) {
  e.preventDefault()
  tabCtxMenu.value = { visible: true, x: e.clientX, y: e.clientY, tabId: tab.id }
}

function closeTabCtxMenu() {
  tabCtxMenu.value.visible = false
}

function handleCtxAction(action: string) {
  const id = tabCtxMenu.value.tabId
  if (!id) return
  switch (action) {
    case 'close': store.closeTab(id); break
    case 'close-others': store.closeOtherTabs(id); break
    case 'close-all': store.closeAllTabs(); break
  }
  tabCtxMenu.value.visible = false
}

// 点击文档关闭右键菜单
function onDocClick() { closeTabCtxMenu() }
onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

// ── 鼠标中键关闭 ──
function onTabMouseDown(e: MouseEvent, tab: TabItem) {
  if (e.button === 1 && tab.closable) {
    e.preventDefault()
    store.closeTab(tab.id)
  }
}
</script>

<template>
  <div class="tab-workspace">
    <!-- 标签栏 -->
    <div class="tab-bar" v-if="store.tabs.length > 0">
      <div
        v-for="tab in store.tabs"
        :key="tab.id"
        class="tab-item"
        :class="{ active: tab.id === store.activeTabId }"
        @click="store.activateTab(tab.id)"
        @contextmenu="onTabContextMenu($event, tab)"
        @mousedown="onTabMouseDown($event, tab)"
        draggable="false"
      >
        <span class="tab-title">{{ tab.title }}</span>
        <span
          v-if="tab.closable"
          class="tab-close"
          @click.stop="store.closeTab(tab.id)"
          title="关闭"
        >✕</span>
      </div>
    </div>

    <!-- 标签内容 -->
    <div class="tab-content">
      <template v-if="store.activeTab">
        <component
          :is="componentMap[store.activeTab.type]"
          v-bind="store.activeTab.props"
          :key="store.activeTab.id"
        />
      </template>
      <div v-else class="tab-empty">
        <div class="empty-content">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          <p>选择数据库连接或双击表名开始工作</p>
          <n-button size="small" @click="store.openTab('connection-list', '连接管理', {}, false)">打开连接列表</n-button>
        </div>
      </div>
    </div>

    <!-- 标签右键菜单 -->
    <teleport to="body">
      <div
        v-if="tabCtxMenu.visible"
        class="tab-context-menu"
        :style="{ left: tabCtxMenu.x + 'px', top: tabCtxMenu.y + 'px' }"
        @click.stop
      >
        <div class="ctx-item" @click="handleCtxAction('close')">关闭</div>
        <div class="ctx-item" @click="handleCtxAction('close-others')">关闭其他</div>
        <div class="ctx-item" @click="handleCtxAction('close-all')">全部关闭</div>
      </div>
    </teleport>
  </div>
</template>

<style scoped>
.tab-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.tab-bar {
  display: flex;
  align-items: center;
  background: #252526;
  border-bottom: 1px solid #3c3c3c;
  min-height: 32px;
  overflow-x: auto;
  overflow-y: hidden;
  user-select: none;
  flex-shrink: 0;
}

.tab-bar::-webkit-scrollbar {
  height: 3px;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: #999999;
  cursor: pointer;
  border-right: 1px solid #3c3c3c;
  white-space: nowrap;
  min-width: 0;
  position: relative;
  transition: background 0.1s, color 0.1s;
}

.tab-item:hover {
  background: #2d2d2d;
  color: #cccccc;
}

.tab-item.active {
  background: #1e1e1e;
  color: #ffffff;
  border-bottom: 2px solid #0078d4;
}

.tab-title {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 3px;
  font-size: 10px;
  color: #666;
  flex-shrink: 0;
}

.tab-close:hover {
  background: #3c3c3c;
  color: #ffffff;
}

.tab-content {
  flex: 1;
  overflow: hidden;
  background: #1e1e1e;
}

.tab-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
  color: #666;
}

.empty-content p {
  margin: 16px 0;
  font-size: 14px;
}

/* 标签右键菜单 */
.tab-context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 140px;
  background: #3c3f41;
  border: 1px solid #555;
  border-radius: 4px;
  padding: 4px 0;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.tab-context-menu .ctx-item {
  padding: 6px 16px;
  cursor: pointer;
  color: #ccc;
  font-size: 12px;
}

.tab-context-menu .ctx-item:hover {
  background: #4c4f51;
  color: #fff;
}
</style>
