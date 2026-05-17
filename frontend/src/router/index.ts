import { createRouter, createWebHashHistory } from 'vue-router'

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
      props: true,
    },
    {
      path: '/workbench/:connId',
      name: 'workbench',
      component: () => import('../views/SQLWorkbench.vue'),
      props: true,
    },
    {
      path: '/workbench/:connId/:db',
      name: 'workbench-db',
      component: () => import('../views/SQLWorkbench.vue'),
      props: true,
    },
    {
      path: '/tables/:connId/:table',
      name: 'table-browser',
      component: () => import('../views/TableBrowser.vue'),
      props: true,
    },
  ],
})

export default router
