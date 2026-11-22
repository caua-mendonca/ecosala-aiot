<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import LineChart from '../components/LineChart.vue'
import { useAuth } from '../stores/auth'
import { time } from '../utils/format'

// O navegador nunca fala com o RabbitMQ: o backend consulta a API de gerenciamento.
const auth = useAuth()
const data = ref<any>(null)
const dlq = ref<any[]>([])
const error = ref('')
const msg = ref('')
const depth = ref<Record<string, Array<{ x: string; y: number }>>>({})

async function load() {
  try {
    data.value = await api('/messaging/overview')
    error.value = ''
    const now = time(new Date().toISOString())
    const next = { ...depth.value }
    for (const q of data.value.queues) next[q.name] = [...(next[q.name] ?? []), { x: now, y: q.messages }].slice(-60)
    depth.value = next
  } catch (e) { error.value = (e as Error).message }
}
async function loadDlq() {
  if (!auth.can('operator')) return
  try { dlq.value = await api('/messaging/dlq') } catch (e) { error.value = (e as Error).message }
}
let timer: number | undefined
onMounted(() => { void load(); void loadDlq(); timer = window.setInterval(load, 2000) })
onBeforeUnmount(() => window.clearInterval(timer))

async function consumer(q: string, action: 'pause' | 'resume') {
  await api(`/messaging/consumers/${q}/${action}`, { method: 'POST' })
  msg.value = action === 'pause' ? `Consumidor de ${q} parado: veja a fila crescer.` : `Consumidor de ${q} retomado: a fila esvazia.`
  await load()
}
async function testDlq() {
  const r = await api<{ status: string }>('/messaging/test-dlq', { method: 'POST' })
  msg.value = r.status
  window.setTimeout(loadDlq, 800)
}
const series = () => ['q.influx', 'q.inference', 'q.websocket', 'q.rules', 'q.persist']
  .filter((q) => depth.value[q]).map((q) => ({ label: q, data: depth.value[q] }))
</script>

<template>
  <div class="stack">
    <p v-if="error" class="notice">{{ error }}</p>
    <p v-if="msg" class="notice info">{{ msg }}</p>
    <div class="notice info">Demonstração do consumidor parado: rode <code>docker compose stop influx-writer</code> (a fila <b>q.influx</b> cresce) e depois <code>docker compose start influx-writer</code> (ela esvazia). Ou pause um consumidor da própria API abaixo.</div>
    <div class="card" v-if="data">
      <div class="card-head"><h2>Filas (atualiza a cada 2 s)</h2><small>exchanges: {{ data.exchanges.map((x: any) => `${x.name} (${x.type})`).join(' · ') }}</small></div>
      <div class="table-wrap"><table>
        <tr><th>Fila</th><th class="num">Mensagens</th><th class="num">Prontas</th><th class="num">Sem ack</th><th class="num">Publicação/s</th><th class="num">Entrega/s</th><th class="num">Consumidores</th><th>DLX</th><th /></tr>
        <tr v-for="q in data.queues" :key="q.name">
          <td class="mono">{{ q.name }}</td>
          <td class="num" :class="{ error: q.messages > 500 }"><b>{{ q.messages }}</b></td>
          <td class="num">{{ q.ready }}</td><td class="num">{{ q.unacked }}</td>
          <td class="num">{{ q.publish_rate }}</td><td class="num">{{ q.deliver_rate }}</td>
          <td class="num" :class="{ error: q.consumers === 0 && q.name !== 'q.dlq' }">{{ q.consumers }}</td>
          <td class="mono">{{ q.dead_letter ?? '—' }}</td>
          <td><template v-if="data.api_consumers[q.name] && auth.can('operator')">
            <button v-if="!data.api_consumers[q.name].paused" class="btn small ghost" @click="consumer(q.name, 'pause')">Parar consumidor</button>
            <button v-else class="btn small" @click="consumer(q.name, 'resume')">Retomar</button></template></td>
        </tr>
      </table></div>
    </div>
    <div class="card"><h2>Profundidade das filas</h2><div class="chart-box medium"><LineChart :series="series()" /></div></div>
    <div class="grid cols-2" v-if="data">
      <div class="card table-wrap">
        <h2>Consumidores conectados</h2>
        <table><tr><th>Fila</th><th>Conexão</th><th>Usuário</th><th class="num">Prefetch</th></tr>
          <tr v-for="c in data.consumers" :key="c.tag"><td class="mono">{{ c.queue }}</td><td>{{ c.connection }}</td><td>{{ c.user }}</td><td class="num">{{ c.prefetch }}</td></tr></table>
      </div>
      <div class="card table-wrap">
        <div class="card-head"><h2>Fila de mensagens mortas (DLQ)</h2>
          <div class="row" v-if="auth.can('operator')"><button class="btn small ghost" @click="loadDlq">Atualizar</button><button class="btn small danger" @click="testDlq">Enviar mensagem inválida</button></div></div>
        <table><tr><th>Routing key</th><th>Motivo</th><th>Fila de origem</th><th>Conteúdo preservado</th></tr>
          <tr v-for="(m, i) in dlq" :key="i"><td class="mono">{{ m.routing_key }}</td><td>{{ m.reason }}</td><td class="mono">{{ m.queue }}</td><td class="mono truncate">{{ m.payload }}</td></tr></table>
        <small v-if="!dlq.length">DLQ vazia.</small>
      </div>
    </div>
    <div class="card table-wrap" v-if="data">
      <h2>Últimas mensagens (formato único JSON)</h2>
      <table><tr><th>Routing key</th><th>Tipo</th><th>Dispositivo</th><th>Instante</th><th>Conteúdo</th></tr>
        <tr v-for="m in data.recent" :key="m.id"><td class="mono">{{ m.routing_key }}</td><td>{{ m.type }}</td><td class="mono">{{ m.device }}</td><td>{{ m.ts ? time(m.ts) : '' }}</td><td class="mono truncate">{{ m.payload }}</td></tr></table>
    </div>
  </div>
</template>
