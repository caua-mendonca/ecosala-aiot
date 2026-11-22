<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
import { useAuth } from '../stores/auth'
import { useLive } from '../stores/live'
import type { Job } from '../types'
import { MODE_LABEL, big, dt, num } from '../utils/format'

const live = useLive()
const auth = useAuth()
const form = reactive<any>({})
const meta = ref<any>(null)
const estimate = ref<{ total_readings: number; ok: boolean; error: string | null } | null>(null)
const jobs = ref<Job[]>([])
const msg = ref('')

async function loadJobs() { jobs.value = await api<Job[]>('/jobs?kind=generate') }
onMounted(async () => {
  meta.value = await api('/lab/defaults')
  Object.assign(form, meta.value.defaults)
  await loadJobs()
})
let t: number | undefined
watch(form, () => {
  window.clearTimeout(t)
  t = window.setTimeout(async () => { estimate.value = await api('/lab/estimate', { method: 'POST', json: form }) }, 300)
}, { deep: true })
const off = live.onMessage((e) => { if (e.type === 'job.done' || e.type === 'job.failed') void loadJobs() })
onBeforeUnmount(off)

function progressOf(j: Job) {
  const ev = live.jobs[j.id]
  if (ev && j.status !== 'done' && j.status !== 'failed') return { p: ev.payload.progress ?? j.progress, m: ev.payload.message ?? j.message, s: ev.type === 'job.failed' ? 'failed' : 'running' }
  return { p: j.progress, m: j.message, s: j.status }
}
const running = computed(() => jobs.value.some((j) => ['queued', 'running'].includes(progressOf(j).s)))

function toggle(list: string[], m: string) {
  const i = list.indexOf(m)
  if (i >= 0) list.splice(i, 1)
  else list.push(m)
}
async function submit() {
  msg.value = ''
  try {
    const r = await api<{ job_id: string }>('/lab/generate', { method: 'POST', json: form })
    msg.value = `Job ${r.job_id} enviado para a fila q.jobs.generate. A API respondeu na hora; o worker processa em segundo plano.`
    await loadJobs()
  } catch (e) { msg.value = (e as Error).message }
}
</script>

<template>
  <div class="stack" v-if="meta">
    <div class="card stack">
      <h2>Configurar geração de dados sintéticos</h2>
      <p class="muted">Simula a vida inteira dos ar-condicionados (equipamentos reais levam meses para falhar). Cada leitura representa {{ meta.sample_minutes }} minutos; degradação progressiva com ruído, ciclo dia/noite e estações, falhas mecânicas e de sensor, leituras faltantes e valores absurdos.</p>
      <div class="grid cols-4">
        <label class="field">Equipamentos (1 por sala)<input type="number" min="1" max="2000" v-model.number="form.n_equipment" /></label>
        <label class="field">Sensores de cada tipo por sala<input type="number" min="1" max="20" v-model.number="form.sensors_per_type" /></label>
        <label class="field">Período simulado (dias)<input type="number" min="1" max="1095" v-model.number="form.days" /></label>
        <label class="field">Semente aleatória<input type="number" min="0" v-model.number="form.seed" /></label>
        <label class="field">% de equipamentos que falham<input type="number" min="0" max="100" v-model.number="form.failure_pct" /></label>
        <label class="field">% com falha de sensor<input type="number" min="0" max="100" v-model.number="form.sensor_fault_pct" /></label>
        <label class="field">Nível de ruído (0–5)<input type="number" step="0.1" min="0" max="5" v-model.number="form.noise" /></label>
        <label class="field">% leituras faltantes<input type="number" step="0.1" min="0" max="100" v-model.number="form.missing_pct" /></label>
        <label class="field">% valores absurdos (outliers)<input type="number" step="0.1" min="0" max="100" v-model.number="form.outlier_pct" /></label>
      </div>
      <div class="row"><b>Modos de falha:</b>
        <label v-for="m in meta.mechanical_modes" :key="m" class="row"><input type="checkbox" :checked="form.failure_modes.includes(m)" @change="toggle(form.failure_modes, m)" />{{ MODE_LABEL[m] }}</label>
        <label v-for="m in meta.sensor_modes" :key="m" class="row"><input type="checkbox" :checked="form.sensor_fault_modes.includes(m)" @change="toggle(form.sensor_fault_modes, m)" />{{ MODE_LABEL[m] }}</label>
      </div>
      <div class="row">
        <span v-if="estimate">Volume estimado: <b>{{ big(estimate.total_readings) }}</b> leituras
          <small>(mínimo exigido 1.000.000 · teto {{ big(meta.max_readings) }})</small></span>
        <span v-if="estimate && !estimate.ok" class="error">{{ estimate.error }}</span>
        <span v-else-if="estimate && estimate.total_readings < 1000000" class="error">abaixo de 1 milhão</span>
        <span class="spacer" />
        <button class="btn" :disabled="!auth.can('admin') || (estimate && !estimate.ok) || running" @click="submit">Gerar dados</button>
      </div>
      <small v-if="!auth.can('admin')">Somente o administrador pode gerar dados.</small>
      <p v-if="msg" class="notice info">{{ msg }}</p>
    </div>
    <div class="card table-wrap">
      <h2>Jobs de geração</h2>
      <table>
        <tr><th>Job / dataset</th><th>Progresso</th><th>Resultado</th><th>Criado</th></tr>
        <tr v-for="j in jobs" :key="j.id">
          <td class="mono">{{ j.id }}<br /><small>por {{ j.created_by }}</small></td>
          <td style="min-width:200px"><div class="progress"><div :style="{ width: (progressOf(j).p * 100) + '%' }" /></div>
            <small>{{ progressOf(j).s }} · {{ num(progressOf(j).p * 100, 0) }}% · {{ progressOf(j).m }}</small></td>
          <td><template v-if="j.result">
            <b>{{ big(j.result.total_readings) }}</b> leituras ({{ big(j.result.equipment_rows) }} linhas de equipamento),
            {{ j.result.failing_equipment }} falhas {{ JSON.stringify(j.result.failures_by_mode) }}, {{ j.result.size_mb }} MB,
            amostra no InfluxDB (bucket lab): {{ big(j.result.influx_sample_points ?? 0) }} pontos</template>
            <span v-else-if="j.status === 'failed'" class="error">{{ j.message }}</span></td>
          <td>{{ dt(j.created_at) }}</td>
        </tr>
      </table>
    </div>
  </div>
</template>
