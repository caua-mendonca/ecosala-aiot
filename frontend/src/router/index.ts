import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardView,
    },
    {
      path: '/historico',
      name: 'history',
      component: () => import('@/views/HistoryView.vue'),
    },
    {
      path: '/sobre',
      name: 'about',
      component: () => import('@/views/AboutView.vue'),
    },
  ],
})

export default router
