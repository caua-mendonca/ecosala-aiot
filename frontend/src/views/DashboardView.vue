<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { api } from '../api'
import LineChart from '../components/LineChart.vue'
import StatusPill from '../components/StatusPill.vue'
import { useAuth } from '../stores/auth'
import { useLive } from '../stores/live'
import type { Device, Prediction } from '../types'
import { TYPE_LABEL, num, rul, time } from '../utils/format'

const live = useLive()
const auth = useAuth()
const busy = ref<string | null>(null)
const feedback = ref('')

const rooms = computed(() => {
  const map: Record<string, Device[]> = {}
  for (const d of live.devices) (map[d.room] ??= []).push(d)
  return Object.entries(map).sort(([a], [b]) => (a === 'externo' ? 1 : b === 'externo' ? -1 : a.localeCompare(b)))
})

const counts = computed(() => {
  const all = live.devices.length
  const online = live.devices.filter((d) => live.isFresh(d.id)).length
  const equipment = live.devices.filter((d) => d.kind === 'equipment')
  const healths = equipment.map((e) => (live.predictions[e.id]?.payload as Prediction | undefined)?.health)
    .filter((h): h is number => typeof h === 'number')
  return { all, online, alerts: live.alertsOpen.length, worst: healths.length ? Math.min(...healths) : null }
})

// gráfico ao vivo: atualiza a cada 2 s (não a cada mensagem)
const tick = ref(0)
const timer = window.setInterval(() => tick.value++, 2000)
onBeforeUnmount(() => window.clearInterval(timer))
function seriesFor(type: string) {
  void tick.value
  return live.devices.filter((d) => d.kind === 'sensor' && d.type === type && d.room !== 'externo').map((d) => ({
    label: d.room,
    data: (live.history[d.id] ?? []).map(([ts, v]) => ({ x: time(ts), y: v })),
  }))
}
const tempSeries = computed(() => seriesFor('temperature'))
const co2Series = computed(() => seriesFor('co2'))
const vibSeries = computed(() => {
  void tick.value
  return live.devices.filter((d) => d.kind === 'equipment').map((d) => ({
    label: d.id, data: (live.history[d.id] ?? []).map(([ts, v]) => ({ x: time(ts), y: v })),
  }))
})

function value(d: Device): string {
  const p = live.latest[d.id]?.payload
  if (!p) return '—'
  if (p.kind === 'sensor') return `${num(p.value, d.type === 'presence' ? 0 : 1)} ${d.unit ?? ''}`
  if (p.kind === 'actuator') return p.state ? 'Ligado' : 'Desligado'
  if (p.kind === 'equipment') return p.failed ? 'QUEBRADO' : p.running ? 'Funcionando' : 'Desligado'
  return '—'
}
function isOn(d: Device): boolean {
  const p = live.latest[d.id]?.payload
  return d.kind === 'equipment' ? !!p?.enabled : !!p?.state
}

async function command(d: Device, action: 'on' | 'off') {
  busy.value = d.id
  feedback.value = ''
  try {
    await api(`/devices/${d.id}/command`, { method: 'POST', json: { action } })
    feedback.value = `Comando "${action === 'on' ? 'ligar' : 'desligar'}" enviado para ${d.name} (API → RabbitMQ → gateway → MQTT → simulador).`
  } catch (e) {
    feedback.value = (e as Error).message
  } finally {
    busy.value = null
  }
}
async function simulator(action: 'pause' | 'resume') {
  await api(`/simulator/${action}`, { method: 'POST' })
  feedback.value = action === 'pause' ? 'Simulador pausado: a interface vai indicar "sem dados".' : 'Simulador retomado.'
}
</script>

<template>
  <div class="stack">
    <div class="grid cols-4">
      <div class="card kpi"><span class="label">Dispositivos online</span><span class="value">{{ counts.online }}/{{ counts.all }}</span></div>
      <div class="card kpi"><span class="label">Alertas preditivos abertos</span><span class="value" :class="{ error: counts.alerts }">{{ counts.alerts }}</span></div>
      <div class="card kpi"><span class="label">Pior saúde (IA)</span><span class="value">{{ counts.worst === null ? '—' : num(counts.worst, 0) + '/100' }}</span></div>
      <div class="card kpi"><span class="label">Tempo real</span>
        <span class="value"><StatusPill :status="live.hasData ? 'normal' : 'nodata'" :label="live.hasData ? 'recebendo' : 'sem dados'" /></span>
        <div v-if="auth.can('operator')" class="row"><button class="btn small ghost" @click="simulator('pause')">Pausar simulador</button>
          <button class="btn small ghost" @click="simulator('resume')">Retomar</button></div>
      </div>
    </div>
    <p v-if="feedback" class="notice info">{{ feedback }}</p>
    <div v-if="live.acks.length" class="notice info">Último retorno do dispositivo: <b>{{ live.acks[0].payload.detail }}</b> ({{ time(live.acks[0].ts) }})</div>

    <div class="grid cols-3">
      <div class="card"><h2>Temperatura das salas (°C)</h2><div class="chart-box medium"><LineChart :series="tempSeries" /></div></div>
      <div class="card"><h2>CO₂ das salas (ppm)</h2><div class="chart-box medium"><LineChart :series="co2Series" /></div></div>
      <div class="card"><h2>Vibração dos ar-condicionados (mm/s)</h2><div class="chart-box medium"><LineChart :series="vibSeries" /></div></div>
    </div>

    <div class="grid cols-2">
      <div v-for="[room, devs] in rooms" :key="room" class="card">
        <div class="card-head"><h2>{{ room === 'externo' ? 'Estação externa' : room }}</h2>
          <small>{{ live.nodeStatus['esp32-' + room] === 'offline' ? 'nó offline' : '' }}</small></div>
        <table>
          <tr v-for="d in devs" :key="d.id">
            <td>{{ TYPE_LABEL[d.type] ?? d.type }}<br /><small class="mono">{{ d.id }}</small></td>
            <td class="num"><b>{{ value(d) }}</b>
              <div v-if="d.kind === 'equipment' && live.predictions[d.id]"><small>saúde {{ num(live.predictions[d.id].payload.health, 0) }} · vida útil {{ rul(live.predictions[d.id].payload.rul_h, live.predictions[d.id].payload.rul_capped) }}</small></div>
            </td>
            <td><StatusPill :status="live.statusOf(d.id)" /></td>
            <td class="num">
              <template v-if="d.controllable && auth.can('operator')">
                <button class="btn small" :class="isOn(d) ? 'off' : 'on'" :disabled="busy === d.id"
                        @click="command(d, isOn(d) ? 'off' : 'on')">{{ isOn(d) ? 'Desligar' : 'Ligar' }}</button>
              </template>
            </td>
          </tr>
        </table>
      </div>
    </div>
  </div>
</template>
