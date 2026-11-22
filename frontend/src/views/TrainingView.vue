<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import LineChart from '../components/LineChart.vue'
import { useAuth } from '../stores/auth'
import { useLive } from '../stores/live'
import type { Job } from '../types'
import { big, dt, num } from '../utils/format'

const live = useLive()
const auth = useAuth()
const models = ref<any[]>([])
const datasets = ref<any[]>([])
const jobs = ref<Job[]>([])
const datasetId = ref('')
const selected = ref<number | null>(null)
const msg = ref('')

async function load() {
  ;[models.value, datasets.value, jobs.value] = await Promise.all([api<any[]>('/models'), api<any[]>('/lab/datasets'), api<Job[]>('/jobs?kind=train')])
  if (selected.value === null && models.value.length) selected.value = (models.value.find((m) => m.active) ?? models.value[0]).version
}
onMounted(load)
const off = live.onMessage((e) => { if (['job.done', 'job.failed', 'model.updated'].includes(e.type)) void load() })
onBeforeUnmount(off)

const active = computed(() => models.value.find((m) => m.active))
const model = computed(() => models.value.find((m) => m.version === selected.value))
const runningJob = computed(() => jobs.value.find((j) => ['queued', 'running'].includes(j.status) && !(live.jobs[j.id]?.type === 'job.done')))
const runningProgress = computed(() => runningJob.value ? (live.jobs[runningJob.value.id]?.payload ?? runningJob.value) : null)

async function train() {
  msg.value = ''
  try {
    const r = await api<{ job_id: string }>('/training/train', { method: 'POST', json: { dataset_id: datasetId.value || null } })
    msg.value = `Treino ${r.job_id} na fila q.jobs.train. Quando terminar, o modelo novo entra em uso sem reiniciar a inferência.`
    await load()
  } catch (e) { msg.value = (e as Error).message }
}
function scatter(t: any) {
  const pts = (t.scatter ?? []).map(([y, p]: number[]) => ({ x: y, y: p }))
  const max = Math.max(1, ...pts.map((p: any) => Math.max(p.x, p.y)))
  return [{ label: 'previsto × real', data: pts }, { label: 'ideal', data: [{ x: 0, y: 0 }, { x: max, y: max }], dashed: true, color: '#94a3b8' }]
}
function importance(t: any) {
  return [{ label: 'importância (queda do MAE ao embaralhar)', data: (t.feature_importance ?? []).slice(0, 10).map(([k, v]: [string, number]) => ({ x: k, y: v })) }]
}
</script>

<template>
  <div class="stack">
    <div class="card row">
      <div><h2>Versão em uso: {{ active ? 'v' + active.version : 'nenhuma' }}</h2>
        <small v-if="active">treinada em {{ dt(active.created_at) }} · {{ active.result.rows_used_train ? big(active.result.rows_used_train) : '' }} linhas de treino</small></div>
      <span class="spacer" />
      <label class="field">Dataset
        <select v-model="datasetId"><option value="">mais recente</option>
          <option v-for="d in datasets" :key="d.id" :value="d.id">{{ d.id }} ({{ big(d.result?.total_readings ?? 0) }} leituras)</option></select></label>
      <button class="btn" :disabled="!auth.can('admin') || !!runningJob" @click="train">Treinar modelos</button>
    </div>
    <p v-if="msg" class="notice info">{{ msg }}</p>
    <div v-if="runningJob && runningProgress" class="card">
      <b>Treinando ({{ runningJob.id }})</b>
      <div class="progress"><div :style="{ width: (runningProgress.progress ?? 0) * 100 + '%' }" /></div>
      <small>{{ runningProgress.message }}</small>
    </div>

    <div class="card row" v-if="models.length">
      <b>Versões:</b>
      <button v-for="m in models" :key="m.version" class="btn small" :class="{ ghost: m.version !== selected }" @click="selected = m.version">
        v{{ m.version }}{{ m.active ? ' (em uso)' : '' }}{{ m.valid ? '' : ' ✗' }}</button>
    </div>

    <template v-if="model">
      <p v-if="!model.valid" class="notice">Esta versão NÃO venceu a base simples em algum alvo e por isso não foi colocada em uso.</p>
      <p class="muted">Divisão por equipamento (sem misturar máquinas): treino {{ big(model.result.rows.train) }}, validação {{ big(model.result.rows.val) }}, teste {{ big(model.result.rows.test) }} linhas · dataset {{ model.result.dataset }} · {{ model.result.train_seconds }} s de treino.</p>
      <div class="grid cols-2">
        <div v-for="(t, name) in model.result.targets" :key="name" class="card stack">
          <div class="card-head"><h2>{{ t.label }}</h2>
            <span class="pill" :class="t.beats_baseline ? 'normal' : 'critico'">{{ t.beats_baseline ? 'vence a base' : 'não vence a base' }}</span></div>
          <table>
            <tr><th>Conjunto</th><th class="num">MAE</th><th class="num">RMSE</th><th class="num">R²</th></tr>
            <tr v-for="(m, part) in t.metrics" :key="part"><td>Modelo ({{ String(part) === 'val' ? 'validação' : 'teste' }})</td>
              <td class="num">{{ num(m.mae, 2) }}</td><td class="num">{{ num(m.rmse, 2) }}</td><td class="num">{{ num(m.r2, 3) }}</td></tr>
            <tr v-for="(m, part) in t.baseline" :key="'b' + part" class="muted"><td>Base simples: média ({{ String(part) === 'val' ? 'validação' : 'teste' }})</td>
              <td class="num">{{ num(m.mae, 2) }}</td><td class="num">{{ num(m.rmse, 2) }}</td><td class="num">{{ num(m.r2, 3) }}</td></tr>
          </table>
          <h3>Previsto × real (teste)</h3>
          <div class="chart-box medium"><LineChart kind="scatter" :series="scatter(t)" x-label="real" y-label="previsto" /></div>
          <h3>Importância dos atributos</h3>
          <div class="chart-box"><LineChart kind="bar" :series="importance(t)" /></div>
        </div>
      </div>
    </template>
    <div v-else class="card">Nenhum modelo treinado ainda. Gere dados no Laboratório e clique em "Treinar modelos" (na primeira subida o sistema treina uma versão inicial automaticamente).</div>
  </div>
</template>
