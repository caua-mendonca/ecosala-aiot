<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { setUnauthorizedHandler } from './api'
import { useAuth } from './stores/auth'
import { useLive } from './stores/live'

const auth = useAuth()
const live = useLive()
const route = useRoute()
const router = useRouter()

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/historico', label: 'Histórico' },
  { to: '/gemeo-3d', label: 'Gêmeo 3D' },
  { to: '/insights', label: 'Insights' },
  { to: '/dispositivos', label: 'Dispositivos' },
  { to: '/laboratorio', label: 'Laboratório' },
  { to: '/treinamento', label: 'Treinamento' },
  { to: '/mensageria', label: 'Mensageria' },
  { to: '/assistente', label: 'Assistente' },
  { to: '/auditoria', label: 'Auditoria', role: 'admin' as const },
  { to: '/infra', label: 'Infra' },
]

function logout() {
  live.disconnect()
  auth.logout()
  router.push('/login')
}
setUnauthorizedHandler(logout)

watch(() => auth.isLogged, (ok) => {
  if (ok) void live.connect()
  else live.disconnect()
}, { immediate: true })
</script>

<template>
  <div v-if="route.meta.public" class="public"><RouterView /></div>
  <div v-else class="shell">
    <aside class="side">
      <div class="brand">
        <img src="/favicon.svg" alt="" width="28" height="28" />
        <div><strong>EcoSala</strong><small>AIoT · Smart Campus</small></div>
      </div>
      <nav>
        <template v-for="l in links" :key="l.to">
          <RouterLink v-if="!l.role || auth.can(l.role)" :to="l.to" class="nav-link">{{ l.label }}</RouterLink>
        </template>
      </nav>
      <div class="side-foot">
        <div class="conn" :class="{ ok: live.connected && live.hasData }">
          <span class="dot" />
          {{ !live.connected ? 'WebSocket desconectado' : live.hasData ? 'Tempo real ativo' : 'Sem dados do simulador' }}
        </div>
        <div class="who">{{ auth.username }} <span class="role">{{ auth.roleLabel }}</span></div>
        <button class="btn ghost small" @click="logout">Sair</button>
      </div>
    </aside>
    <main class="content">
      <header class="page-head"><h1>{{ route.meta.title }}</h1></header>
      <RouterView />
    </main>
  </div>
</template>
