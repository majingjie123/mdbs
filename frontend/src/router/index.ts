import { createRouter, createWebHashHistory } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
  }
}

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/connections',
    },
    {
      path: '/connections',
      name: 'connections',
      component: () => import('../views/ConnectionList.vue'),
    },
    {
      path: '/connections/:id',
      name: 'connection-detail',
      component: () => import('../views/ConnectionDetail.vue'),
      props: (route) => ({
        id: parseInt(route.params.id as string),
        edit: route.query.edit === '1',
      }),
    },
    {
      path: '/workbench/:connId',
      name: 'workbench',
      component: () => import('../views/SQLWorkbench.vue'),
      props: (route) => ({
        connId: parseInt(route.params.connId as string),
        dbName: (route.query.db as string) || '',
        schemaName: (route.query.schema as string) || '',
        initialSql: (route.query.sql as string) || '',
      }),
    },
    {
      path: '/workbench/:connId/:db',
      name: 'workbench-db',
      component: () => import('../views/SQLWorkbench.vue'),
      props: (route) => ({
        connId: parseInt(route.params.connId as string),
        dbName: route.params.db as string,
        schemaName: (route.query.schema as string) || '',
        initialSql: (route.query.sql as string) || '',
      }),
    },
    {
      path: '/tables/:connId/:table',
      name: 'table-browser',
      component: () => import('../views/TableBrowser.vue'),
      props: (route) => ({
        connId: parseInt(route.params.connId as string),
        tableName: route.params.table as string,
        dbName: (route.query.db as string) || '',
      }),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsPage.vue'),
    },
    {
      path: '/ai/chat',
      name: 'ai-chat',
      component: () => import('../views/AIChat.vue'),
      meta: { title: 'AI 助手' },
    },
    {
      path: '/ai/chat/:connId',
      name: 'ai-chat-conn',
      component: () => import('../views/AIChat.vue'),
      props: (route) => ({
        connId: parseInt(route.params.connId as string),
      }),
      meta: { title: 'AI 助手' },
    },
    {
      path: '/ai/chat/:connId/:db',
      name: 'ai-chat-db',
      component: () => import('../views/AIChat.vue'),
      props: (route) => ({
        connId: parseInt(route.params.connId as string),
        db: route.params.db as string,
      }),
      meta: { title: 'AI 助手' },
    },
  ],
})

export default router