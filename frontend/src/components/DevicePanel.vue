<script setup lang="ts">
// Painel de um item (usado na cena 3D): última leitura, mini gráfico,
// saúde prevista pela IA e botões de comando para atuadores controláveis.
import { computed, ref } from 'vue'
import { api } from '../api'
import { useAuth } from '../stores/auth'
import { useLive } from '../stores/live'
import type { Prediction } from '../types'
import { MODE_LABEL, TYPE_LABEL, dt, num, rul } from '../utils/format'
import LineChart from './LineChart.vue'
import StatusPill from './StatusPill.vue'

const props = defineProps<{ deviceId: string }>()
const emit = defineEmits<{ close: [] }>()
const live = useLive()
const auth = useAuth()
const busy = ref(false)
const msg = ref('')
const faultMode = ref('rolamento')

const device = computed(() => live.deviceById[props.deviceId])
const env = computed(() => live.latest[props.deviceId])
const pred = computed(() => live.predictions[props.deviceId]?.payload as Prediction | undefined)
const status = computed(() => live.statusOf(props.deviceId))
const series = computed(() => [{
  label: props.deviceId,
  data: (live.history[props.deviceId] ?? []).map(([ts, v]) => ({ x: ts.slice(11, 19), y: v })),
}])
const isOn = computed(() => {
  const p = env.value?.payload
  if (!p) return false
  return p.kind === 'equipment' ? !!p.enabled : !!p.state
})

async function send(action: 'on' | 'off') {
  busy.value = true
  msg.value = ''
  try {
    await api(`/devices/${props.deviceId}/command`, { method: 'POST', json: { action } })
    msg.value = 'Comando enviado; o estado muda nas próximas leituras.'
  } catch (e) {
    msg.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

async function fault(kind: 'fault' | 'repair') {
  busy.value = true
  try {
    await api(`/equipment/${props.deviceId}/${kind}`, { method: 'POST', json: kind === 'fault' ? { mode: faultMode.value, hours: 36 } : undefined })
    msg.value = kind === 'fault' ? 'Falha injetada no simulador.' : 'Equipamento reparado.'
  } catch (e) {
    msg.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="panel card" v-if="device">
    <div class="card-head">
      <div>
        <h2>{{ device.name }}</h2>
        <small class="mono">{{ device.id }} · {{ TYPE_LABEL[device.type] ?? device.type }} · {{ device.room }}</small>
      </div>
      <button class="btn ghost small" @click="emit('close')">✕</button>
    </div>
    <div class="row"><StatusPill :status="status" /><small>atualizado {{ dt(env?.ts) }}</small></div>

    <div v-if="env" class="readings">
      <template v-if="env.payload.kind === 'sensor'">
        <div class="kpi"><span class="label">Última leitura</span>
          <span class="value">{{ num(env.payload.value, 1) }} <small>{{ device.unit }}</small></span></div>
        <small v-if="device.normal_min !== null || device.normal_max !== null">
          Faixa normal: {{ device.normal_min ?? '—' }} a {{ device.normal_max ?? '—' }} {{ device.unit }}</small>
      </template>
      <template v-else-if="env.payload.kind === 'actuator'">
        <div class="kpi"><span class="label">Estado</span><span class="value">{{ env.payload.state ? 'Ligado' : 'Desligado' }}</span></div>
      </template>
      <template v-else>
        <table>
          <tr><td>Vibração</td><td class="num">{{ num(env.payload.vibration, 2) }} mm/s</td></tr>
          <tr><td>Corrente</td><td class="num">{{ num(env.payload.current, 2) }} A</td></tr>
          <tr><td>Temp. descarga</td><td class="num">{{ num(env.payload.temperature, 1) }} °C</td></tr>
          <tr><td>Compressor</td><td class="num">{{ env.payload.failed ? 'QUEBRADO' : env.payload.running ? 'ligado' : 'desligado' }}</td></tr>
        </table>
      </template>
    </div>
    <div class="chart-box small"><LineChart :series="series" minimal /></div>

    <div v-if="device.kind === 'equipment'" class="ai">
      <h3>IA — manutenção preditiva</h3>
      <div v-if="pred" class="grid cols-2">
        <div class="kpi"><span class="label">Saúde</span><span class="value">{{ num(pred.health, 0) }}/100</span></div>
        <div class="kpi"><span class="label">Vida útil restante</span><span class="value">{{ rul(pred.rul_h, pred.rul_capped) }}</span></div>
      </div>
      <small v-else>Aguardando previsões (modelo em treino ou poucas leituras).</small>
    </div>

    <div v-if="device.controllable && auth.can('operator')" class="row cmd">
      <button class="btn small on" :disabled="busy || isOn" @click="send('on')">Ligar</button>
      <button class="btn small off" :disabled="busy || !isOn" @click="send('off')">Desligar</button>
    </div>
    <div v-if="device.kind === 'equipment' && auth.can('operator')" class="row cmd">
      <select v-model="faultMode">
        <option v-for="m in ['rolamento', 'superaquecimento', 'entupimento', 'desbalanceamento']" :key="m" :value="m">{{ MODE_LABEL[m] }}</option>
      </select>
      <button class="btn small danger" :disabled="busy" @click="fault('fault')">Injetar falha</button>
      <button class="btn small ghost" :disabled="busy" @click="fault('repair')">Reparar</button>
    </div>
    <small v-if="msg">{{ msg }}</small>
  </div>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: .6rem; }
.readings table td { padding: .2rem .3rem; }
.ai { border-top: 1px solid var(--line); padding-top: .5rem; }
.cmd { border-top: 1px solid var(--line); padding-top: .5rem; }
</style>
