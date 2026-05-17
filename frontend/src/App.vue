<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { darkTheme } from 'naive-ui'
import { NConfigProvider, NMessageProvider, NDialogProvider, NLoadingBarProvider } from 'naive-ui'
import AppLayout from './components/AppLayout.vue'

const theme = ref(darkTheme)
const themeId = ref('dark')

onMounted(() => {
  const stored = localStorage.getItem('mdbs_settings')
  if (stored) {
    try {
      const s = JSON.parse(stored)
      if (s.theme) {
        themeId.value = s.theme
        // 基础主题统一使用 darkTheme，通过 CSS 类名区分风格
        theme.value = darkTheme
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
  <NConfigProvider :theme="theme" :data-theme="themeId">
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
</style>
