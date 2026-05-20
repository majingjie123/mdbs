<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import { NConfigProvider, NMessageProvider, NDialogProvider, NLoadingBarProvider } from 'naive-ui'
import AppLayout from './components/AppLayout.vue'
import { useAppStore } from './stores/app'

const store = useAppStore()

// 根据 themeId 动态生成 NaiveUI 主题覆盖
const themeOverrides = computed<GlobalThemeOverrides | null>(() => {
  switch (store.themeId) {
    case 'eye':
      return {
        common: {
          primaryColor: '#66bb6a',
          primaryColorHover: '#81c784',
          primaryColorPressed: '#4caf50',
          primaryColorSuppl: '#66bb6a',
          borderColor: '#2e7d32',
          dividerColor: '#2e7d32',
        },
      }
    case 'hacker':
      return {
        common: {
          primaryColor: '#00ff41',
          primaryColorHover: '#33ff66',
          primaryColorPressed: '#00cc33',
          primaryColorSuppl: '#00ff41',
          borderColor: '#0a3a0a',
          dividerColor: '#0a3a0a',
        },
      }
    case 'deepblue':
      return {
        common: {
          primaryColor: '#4a8bc2',
          primaryColorHover: '#64b5f6',
          primaryColorPressed: '#3a7bb2',
          primaryColorSuppl: '#4a8bc2',
          borderColor: '#1a2a4a',
          dividerColor: '#1a2a4a',
        },
      }
    case 'purple':
      return {
        common: {
          primaryColor: '#ab47bc',
          primaryColorHover: '#ce93d8',
          primaryColorPressed: '#9c27b0',
          primaryColorSuppl: '#ab47bc',
          borderColor: '#3a1a4a',
          dividerColor: '#3a1a4a',
        },
      }
    case 'pink':
      return {
        common: {
          primaryColor: '#e91e63',
          primaryColorHover: '#f48fb1',
          primaryColorPressed: '#d81b60',
          primaryColorSuppl: '#e91e63',
          borderColor: '#4a2035',
          dividerColor: '#4a2035',
        },
      }
    case 'orange':
      return {
        common: {
          primaryColor: '#f57c00',
          primaryColorHover: '#ffb74d',
          primaryColorPressed: '#e65100',
          primaryColorSuppl: '#f57c00',
          borderColor: '#4a3520',
          dividerColor: '#4a3520',
        },
      }
    default:
      return null
  }
})

onMounted(() => {
  const stored = localStorage.getItem('mdbs_settings')
  if (stored) {
    try {
      const s = JSON.parse(stored)
      if (s.theme) {
        store.themeId = s.theme
        document.documentElement.setAttribute('data-theme', s.theme)
      }
      if (s.fontFamily || s.fontSize) {
        const root = document.documentElement
        if (s.fontFamily) root.style.setProperty('--editor-font', s.fontFamily)
        if (s.fontSize) root.style.setProperty('--editor-font-size', s.fontSize + 'px')
      }
    } catch {}
  }
})
</script>

<template>
  <NConfigProvider :theme="darkTheme" :theme-overrides="themeOverrides">
    <NLoadingBarProvider>
      <NMessageProvider>
        <NDialogProvider>
          <AppLayout />
        </NDialogProvider>
      </NMessageProvider>
    </NLoadingBarProvider>
  </NConfigProvider>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  overflow: hidden;
}

/* ── 全局 CSS 变量 (暗黑/默认) ── */
:root, [data-theme="dark"] {
  --bg-app: #1e1e1e;
  --bg-toolbar: #3c3f41;
  --bg-hover: #4c4f51;
  --bg-dropdown: #3c3f41;
  --bg-sidebar: #252526;
  --bg-status: #3c3f41;
  --bg-ai-strip: #252526;
  --bg-ai-header: #252526;
  --bg-ai-panel: #1e1e1e;
  --bg-card: #2d2d2d;
  --color-text: #e0e0e0;
  --color-text-secondary: #cccccc;
  --color-text-muted: #999999;
  --color-text-menu: #bbbbbb;
  --color-text-code: #d4d4d4;
  --color-accent: #0078d4;
  --color-accent-alt: #4fc3f7;
  --color-accent-user: #2080f0;
  --color-border: #3c3c3c;
  --color-border-light: #555555;
  --color-conn-online: #6a9955;
  --color-icon: #bbbbbb;
}

/* ── 护眼绿 ── */
[data-theme="eye"] {
  --bg-app: #1a2e1a;
  --bg-toolbar: #2d4a2d;
  --bg-hover: #3a5a3a;
  --bg-dropdown: #2d4a2d;
  --bg-sidebar: #1f3a1f;
  --bg-status: #2d4a2d;
  --bg-ai-strip: #1f3a1f;
  --bg-ai-header: #1f3a1f;
  --bg-ai-panel: #1a2e1a;
  --bg-card: #1f3a1f;
  --color-text: #c8e6c9;
  --color-text-secondary: #a5d6a7;
  --color-text-muted: #81c784;
  --color-text-menu: #a5d6a7;
  --color-text-code: #d4d4d4;
  --color-accent: #66bb6a;
  --color-accent-alt: #81c784;
  --color-accent-user: #4caf50;
  --color-border: #2e7d32;
  --color-border-light: #388e3c;
  --color-conn-online: #aed581;
  --color-icon: #a5d6a7;
}

/* ── 黑客绿 ── */
[data-theme="hacker"] {
  --bg-app: #0a1a0a;
  --bg-toolbar: #0f2a0f;
  --bg-hover: #1a3a1a;
  --bg-dropdown: #0f2a0f;
  --bg-sidebar: #0c1f0c;
  --bg-status: #0f2a0f;
  --bg-ai-strip: #0c1f0c;
  --bg-ai-header: #0c1f0c;
  --bg-ai-panel: #0a1a0a;
  --bg-card: #0f2a0f;
  --color-text: #00ff41;
  --color-text-secondary: #00cc33;
  --color-text-muted: #009a26;
  --color-text-menu: #00cc33;
  --color-text-code: #00ff41;
  --color-accent: #00ff41;
  --color-accent-alt: #33ff66;
  --color-accent-user: #00cc33;
  --color-border: #0a3a0a;
  --color-border-light: #0d4a0d;
  --color-conn-online: #00ff41;
  --color-icon: #00cc33;
}

/* ── 深海蓝 ── */
[data-theme="deepblue"] {
  --bg-app: #0a0f1e;
  --bg-toolbar: #141a33;
  --bg-hover: #1a254a;
  --bg-dropdown: #141a33;
  --bg-sidebar: #0e1428;
  --bg-status: #141a33;
  --bg-ai-strip: #0e1428;
  --bg-ai-header: #0e1428;
  --bg-ai-panel: #0a0f1e;
  --bg-card: #141a33;
  --color-text: #b0c4de;
  --color-text-secondary: #87a9d9;
  --color-text-muted: #5a7fb4;
  --color-text-menu: #87a9d9;
  --color-text-code: #d4d4d4;
  --color-accent: #4a8bc2;
  --color-accent-alt: #64b5f6;
  --color-accent-user: #4a8bc2;
  --color-border: #1a2a4a;
  --color-border-light: #243b5e;
  --color-conn-online: #64b5f6;
  --color-icon: #87a9d9;
}

/* ── 优雅紫 ── */
[data-theme="purple"] {
  --bg-app: #1a0f1e;
  --bg-toolbar: #2d1a33;
  --bg-hover: #3a254a;
  --bg-dropdown: #2d1a33;
  --bg-sidebar: #221428;
  --bg-status: #2d1a33;
  --bg-ai-strip: #221428;
  --bg-ai-header: #221428;
  --bg-ai-panel: #1a0f1e;
  --bg-card: #2d1a33;
  --color-text: #d1b3d9;
  --color-text-secondary: #bb86d9;
  --color-text-muted: #9c5cb8;
  --color-text-menu: #bb86d9;
  --color-text-code: #d4d4d4;
  --color-accent: #ab47bc;
  --color-accent-alt: #ce93d8;
  --color-accent-user: #ce93d8;
  --color-border: #3a1a4a;
  --color-border-light: #4a2060;
  --color-conn-online: #ce93d8;
  --color-icon: #bb86d9;
}

/* ── 樱花粉 ── */
[data-theme="pink"] {
  --bg-app: #1e0a12;
  --bg-toolbar: #331520;
  --bg-hover: #4a2035;
  --bg-dropdown: #331520;
  --bg-sidebar: #280e1a;
  --bg-status: #331520;
  --bg-ai-strip: #280e1a;
  --bg-ai-header: #280e1a;
  --bg-ai-panel: #1e0a12;
  --bg-card: #331520;
  --color-text: #f2c4d0;
  --color-text-secondary: #e391a8;
  --color-text-muted: #d16b87;
  --color-text-menu: #e391a8;
  --color-text-code: #d4d4d4;
  --color-accent: #e91e63;
  --color-accent-alt: #f48fb1;
  --color-accent-user: #e91e63;
  --color-border: #4a2035;
  --color-border-light: #5a2a40;
  --color-conn-online: #f48fb1;
  --color-icon: #e391a8;
}

/* ── 落日橙 ── */
[data-theme="orange"] {
  --bg-app: #1e140a;
  --bg-toolbar: #332515;
  --bg-hover: #4a3520;
  --bg-dropdown: #332515;
  --bg-sidebar: #281e0e;
  --bg-status: #332515;
  --bg-ai-strip: #281e0e;
  --bg-ai-header: #281e0e;
  --bg-ai-panel: #1e140a;
  --bg-card: #332515;
  --color-text: #e8d5b0;
  --color-text-secondary: #d9b87a;
  --color-text-muted: #c49a4a;
  --color-text-menu: #d9b87a;
  --color-text-code: #d4d4d4;
  --color-accent: #f57c00;
  --color-accent-alt: #ffb74d;
  --color-accent-user: #ffb74d;
  --color-border: #4a3520;
  --color-border-light: #5a4028;
  --color-conn-online: #ffb74d;
  --color-icon: #d9b87a;
}
</style>
