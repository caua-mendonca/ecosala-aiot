import { createRouter, createWebHistory } from 'vue-router'
import { useAuth, type Role } from './stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    role?: Role
    public?: boolean
  }
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true, title: 'Login' } },
    { path: '/', component: () => import('./views/DashboardView.vue'), meta: { title: 'Dashboard' } },
    { path: '/historico', component: () => import('./views/HistoryView.vue'), meta: { title: 'Histórico' } },
    { path: '/gemeo-3d', component: () => import('./views/TwinView.vue'), meta: { title: 'Gêmeo digital 3D' } },
    { path: '/insights', component: () => import('./views/InsightsView.vue'), meta: { title: 'Insights de IA' } },
    { path: '/dispositivos', component: () => import('./views/DevicesView.vue'), meta: { title: 'Dispositivos e regras' } },
    { path: '/laboratorio', component: () => import('./views/LabView.vue'), meta: { title: 'Laboratório de Dados' } },
    { path: '/treinamento', component: () => import('./views/TrainingView.vue'), meta: { title: 'Treinamento' } },
    { path: '/mensageria', component: () => import('./views/MessagingView.vue'), meta: { title: 'Mensageria' } },
    { path: '/assistente', component: () => import('./views/AssistantView.vue'), meta: { title: 'Assistente' } },
    { path: '/auditoria', component: () => import('./views/AuditView.vue'), meta: { title: 'Auditoria', role: 'admin' } },
    { path: '/infra', component: () => import('./views/InfraView.vue'), meta: { title: 'Infraestrutura' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.isLogged && auth.token) await auth.restore()
  if (!to.meta.public && !auth.isLogged) return { path: '/login', query: { next: to.fullPath } }
  if (to.meta.role && !auth.can(to.meta.role)) return '/'
  document.title = `${to.meta.title ?? ''} · EcoSala AIoT`
  return true
})
