<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import LineChart from '../components/LineChart.vue'
import { useLive } from '../stores/live'
import { dt, num } from '../utils/format'

const live = useLive()
const device = ref('temp-101')
const range = ref('1h')
const field = ref('value')
const data = ref<{ points: Array<{ ts: string; value: number | null }>; stats: any } | null>(null)
const error = ref('')
const loading = ref(false)

const dev = computed(() => live.deviceById[device.value])
const fields = computed(() => {
  const k = dev.value?.kind
  if (k === 'equipment') return [['vibration', 'Vibração (mm/s)'], ['current', 'Corrente (A)'], ['temperature', 'Temperatura de descarga (°C)'],
    ['health', 'Saúde prevista pela IA'], ['rul_h', 'Vida útil prevista (h)']]
  if (k === 'actuator') return [['state', 'Estado (0/1)']]
  return [['value', 'Valor']]
})
const measurement = computed(() => {
  if (dev.value?.kind === 'actuator') return 'actuator'
  if (dev.value?.kind === 'equipment') return ['health', 'rul_h'].includes(field.value) ? 'prediction' : 'equipment'
  return 'sensor'
})
watch(device, () => { field.value = fields.value[0][0] })

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api(`/readings/history?device=${device.value}&field=${field.value}&measurement=${measurement.value}&range=${range.value}`)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
watch([device, field, range], load)
onMounted(load)

const series = computed(() => [{
  label: device.value,
  data: (data.value?.points ?? []).map((p) => ({ x: dt(p.ts).slice(0, 14), y: p.value })),
}])
</script>

<template>
  <div class="stack">
    <div class="card row">
      <label class="field">Dispositivo
        <select v-model="device"><option v-for="d in live.devices" :key="d.id" :value="d.id">{{ d.name }} ({{ d.id }})</option></select></label>
      <label class="field">Medida
        <select v-model="field"><option v-for="[k, l] in fields" :key="k" :value="k">{{ l }}</option></select></label>
      <label class="field">Período
        <select v-model="range"><option v-for="r in ['15m', '1h', '6h', '24h', '7d']" :key="r">{{ r }}</option></select></label>
      <button class="btn" :disabled="loading" @click="load">Atualizar</button>
      <span class="spacer" /><small>Consulta ao InfluxDB (média por janela)</small>
    </div>
    <p v-if="error" class="notice">{{ error }}</p>
    <div class="grid cols-4" v-if="data">
      <div class="card kpi"><span class="label">Pontos</span><span class="value">{{ data.stats.count }}</span></div>
      <div class="card kpi"><span class="label">Mínimo</span><span class="value">{{ num(data.stats.min, 2) }}</span></div>
      <div class="card kpi"><span class="label">Média</span><span class="value">{{ num(data.stats.mean, 2) }}</span></div>
      <div class="card kpi"><span class="label">Máximo</span><span class="value">{{ num(data.stats.max, 2) }}</span></div>
    </div>
    <div class="card"><div class="chart-box"><LineChart :series="series" /></div></div>
    <div class="card table-wrap" v-if="data?.points.length">
      <h2>Leituras (mais recentes primeiro)</h2>
      <table><tr><th>Instante</th><th class="num">Valor</th></tr>
        <tr v-for="p in [...data.points].reverse().slice(0, 60)" :key="p.ts"><td>{{ dt(p.ts) }}</td><td class="num">{{ num(p.value, 3) }}</td></tr>
      </table>
    </div>
  </div>
</template>
