<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import LineChart from '../components/LineChart.vue'
import StatusPill from '../components/StatusPill.vue'
import { useAuth } from '../stores/auth'
import { useLive } from '../stores/live'
import type { Alert, Prediction } from '../types'
import { MODE_LABEL, dt, num, rul, time } from '../utils/format'

const live = useLive()
const auth = useAuth()
const model = ref<{ version: number | null; created_at?: string } | null>(null)
const msg = ref('')
const mode = ref<Record<string, string>>({})
const hours = ref<Record<string, number>>({})
const healthHist = ref<Record<string, Array<{ x: string; y: number }>>>({})
const closedAlerts = ref<Alert[]>([])

const equipment = computed(() => live.devices.filter((d) => d.kind === 'equipment'))
function pred(id: string): Prediction | undefined {
  return live.predictions[id]?.payload as Prediction | undefined
}
function trendLabel(t: number | undefined): string {
  if (t === undefined) return '—'
  if (t < -0.3) return '↘ piorando'
  if (t > 0.3) return '↗ melhorando'
  return '→ estável'
}

const off = live.onMessage((e) => {
  if (e.type === 'prediction' && e.device) {
    const arr = [...(healthHist.value[e.device] ?? []), { x: time(e.ts), y: e.payload.health as number }].slice(-80)
    healthHist.value = { ...healthHist.value, [e.device]: arr }
  }
})
onBeforeUnmount(off)

async function load() {
  const r = await api<{ model: any }>('/insights')
  model.value = r.model
  closedAlerts.value = (await api<Alert[]>('/alerts?state=closed&limit=10'))
  await live.loadAlerts()
}
onMounted(load)

async function inject(id: string) {
  await api(`/equipment/${id}/fault`, { method: 'POST', json: { mode: mode.value[id] ?? 'rolamento', hours: hours.value[id] ?? 36 } })
  msg.value = `Falha "${MODE_LABEL[mode.value[id] ?? 'rolamento']}" injetada em ${id}. Acompanhe a saúde caindo e o alerta aparecer (tempo simulado acelerado).`
}
async function repair(id: string) {
  await api(`/equipment/${id}/repair`, { method: 'POST' })
  msg.value = `${id} reparado. O alerta é limpo após 10 previsões normais seguidas (histerese).`
}
</script>

<template>
  <div class="stack">
    <div class="notice info">
      Modelos em uso: <b>{{ model?.version ? 'versão ' + model.version : 'nenhum ainda (treino automático inicial em andamento ou aguarde o Treinamento)' }}</b>.
      Saúde (0–100) e vida útil restante vêm de 2 modelos de regressão aplicados à telemetria ao vivo pelo serviço de inferência.
      Alertas usam histerese: 3 previsões seguidas abaixo do limite para disparar, 10 acima para limpar.
    </div>
    <p v-if="msg" class="notice">{{ msg }}</p>
    <div class="grid cols-3">
      <div v-for="e in equipment" :key="e.id" class="card stack">
        <div class="card-head"><div><h2>{{ e.name }}</h2><small class="mono">{{ e.id }}</small></div>
          <StatusPill :status="live.statusOf(e.id)" /></div>
        <template v-if="pred(e.id)">
          <div class="grid cols-2">
            <div class="kpi"><span class="label">Índice de saúde</span>
              <span class="value">{{ num(pred(e.id)!.health, 0) }}<small>/100</small></span>
              <div class="progress"><div :style="{ width: pred(e.id)!.health + '%', background: pred(e.id)!.health < 45 ? 'var(--crit)' : pred(e.id)!.health < 70 ? 'var(--warn)' : 'var(--ok)' }" /></div></div>
            <div class="kpi"><span class="label">Vida útil restante</span><span class="value">{{ rul(pred(e.id)!.rul_h, pred(e.id)!.rul_capped) }}</span>
              <small>{{ trendLabel(pred(e.id)!.trend) }}</small></div>
          </div>
          <p v-if="!pred(e.id)!.rul_capped && pred(e.id)!.status !== 'normal'"><b>{{ e.id }} deve falhar em cerca de {{ rul(pred(e.id)!.rul_h) }}</b> (tempo simulado).</p>
        </template>
        <small v-else>Sem previsão ainda.</small>
        <div class="chart-box small"><LineChart :series="[{ label: 'saúde', data: healthHist[e.id] ?? [] }]" minimal :y-min="0" :y-max="100" /></div>
        <div v-for="a in live.alertsOpen.filter((x) => x.device === e.id)" :key="a.id" class="notice">
          ⚠ {{ a.message }} <small>desde {{ dt(a.opened_at) }}</small></div>
        <div v-if="auth.can('operator')" class="row">
          <select v-model="mode[e.id]"><option v-for="m in ['rolamento', 'superaquecimento', 'entupimento', 'desbalanceamento']" :key="m" :value="m">{{ MODE_LABEL[m] }}</option></select>
          <label class="row"><small>duração (h simuladas)</small><input type="number" min="4" max="240" style="width:5rem" v-model.number="hours[e.id]" placeholder="36" /></label>
          <button class="btn small danger" @click="inject(e.id)">Injetar falha</button>
          <button class="btn small ghost" @click="repair(e.id)">Reparar</button>
        </div>
      </div>
    </div>
    <div class="card table-wrap">
      <h2>Alertas preditivos</h2>
      <table>
        <tr><th>Equipamento</th><th>Tipo</th><th>Mensagem</th><th>Aberto em</th><th>Estado</th></tr>
        <tr v-for="a in [...live.alertsOpen, ...closedAlerts]" :key="a.id">
          <td class="mono">{{ a.device }}</td><td>{{ a.kind === 'rul' ? 'vida útil' : 'saúde' }}</td><td>{{ a.message }}</td>
          <td>{{ dt(a.opened_at) }}</td><td><StatusPill :status="a.state === 'open' ? 'critico' : 'normal'" :label="a.state === 'open' ? 'aberto' : 'resolvido'" /></td></tr>
      </table>
    </div>
  </div>
</template>
