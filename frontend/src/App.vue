<script setup lang="ts">
import { RouterView } from 'vue-router'
import { darkTheme } from 'naive-ui'
import { NConfigProvider, NMessageProvider, NDialogProvider, NLoadingBarProvider } from 'naive-ui'
import Sidebar from './components/Sidebar.vue'
</script>

<template>
  <NConfigProvider :theme="darkTheme">
    <NLoadingBarProvider>
      <NMessageProvider>
        <NDialogProvider>
          <div class="app-layout">
            <Sidebar />
            <main class="app-main">
              <RouterView />
            </main>
          </div>
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

.app-layout {
  display: flex;
  height: 100vh;
  background: #1e1e1e;
}

.app-main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
