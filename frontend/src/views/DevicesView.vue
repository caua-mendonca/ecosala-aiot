<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import StatusPill from '../components/StatusPill.vue'
import { useAuth } from '../stores/auth'
import { useLive } from '../stores/live'
import type { Device } from '../types'
import { TYPE_LABEL } from '../utils/format'

const live = useLive()
const auth = useAuth()
const rules = ref<any[]>([])
const error = ref('')
const editing = ref<string | null>(null)
const draft = reactive<Partial<Device>>({})
const blank = { id: '', name: '', room: 'sala-101', kind: 'sensor', type: 'temperature', unit: '°C', normal_min: null, normal_max: null, controllable: false, node: 'esp32-sala-101', enabled: true }
const newDev = reactive<any>({ ...blank })

async function loadRules() { rules.value = await api('/rules') }
onMounted(loadRules)

async function run(fn: () => Promise<unknown>) {
  error.value = ''
  try { await fn(); await live.loadDevices(); await loadRules() } catch (e) { error.value = (e as Error).message }
}
function edit(d: Device) { editing.value = d.id; Object.assign(draft, d) }
function save(id: string) {
  run(() => api(`/devices/${id}`, { method: 'PUT', json: { name: draft.name, unit: draft.unit, normal_min: draft.normal_min, normal_max: draft.normal_max, controllable: draft.controllable, enabled: draft.enabled } }))
  editing.value = null
}
function remove(id: string) { if (confirm(`Remover ${id}?`)) run(() => api(`/devices/${id}`, { method: 'DELETE' })) }
function create() { run(async () => { await api('/devices', { method: 'POST', json: newDev }); Object.assign(newDev, blank) }) }
function toggleRule(r: any) { run(() => api(`/rules/${r.id}`, { method: 'PUT', json: { ...r, enabled: !r.enabled } })) }
function saveRule(r: any) { run(() => api(`/rules/${r.id}`, { method: 'PUT', json: r })) }
</script>

<template>
  <div class="stack">
    <p v-if="error" class="notice">{{ error }}</p>
    <div class="card table-wrap">
      <div class="card-head"><h2>Dispositivos IoT cadastrados (PostgreSQL)</h2><small>{{ live.devices.length }} itens</small></div>
      <table>
        <tr><th>Id</th><th>Nome</th><th>Sala</th><th>Tipo</th><th>Faixa normal</th><th>Controlável</th><th>Ativo</th><th>Estado</th><th></th></tr>
        <tr v-for="d in live.devices" :key="d.id">
          <td class="mono">{{ d.id }}</td>
          <template v-if="editing === d.id">
            <td><input v-model="draft.name" /></td><td>{{ d.room }}</td><td>{{ TYPE_LABEL[d.type] ?? d.type }}</td>
            <td><input type="number" step="any" v-model.number="draft.normal_min" style="width:5rem" /> a <input type="number" step="any" v-model.number="draft.normal_max" style="width:5rem" /></td>
            <td><input type="checkbox" v-model="draft.controllable" /></td><td><input type="checkbox" v-model="draft.enabled" /></td><td />
            <td><button class="btn small" @click="save(d.id)">Salvar</button> <button class="btn small ghost" @click="editing = null">Cancelar</button></td>
          </template>
          <template v-else>
            <td>{{ d.name }}</td><td>{{ d.room }}</td><td>{{ d.kind }} · {{ TYPE_LABEL[d.type] ?? d.type }}</td>
            <td>{{ d.normal_min ?? '—' }} a {{ d.normal_max ?? '—' }} {{ d.unit ?? '' }}</td>
            <td>{{ d.controllable ? 'sim' : 'não' }}</td><td>{{ d.enabled ? 'sim' : 'não' }}</td>
            <td><StatusPill :status="live.statusOf(d.id)" /></td>
            <td><template v-if="auth.can('admin')"><button class="btn small ghost" @click="edit(d)">Editar</button> <button class="btn small danger" @click="remove(d.id)">Remover</button></template></td>
          </template>
        </tr>
      </table>
    </div>
    <div v-if="auth.can('admin')" class="card">
      <h2>Cadastrar dispositivo</h2>
      <div class="row">
        <label class="field">Id<input v-model="newDev.id" placeholder="ex.: temp-103" /></label>
        <label class="field">Nome<input v-model="newDev.name" /></label>
        <label class="field">Sala<input v-model="newDev.room" /></label>
        <label class="field">Nó (ESP32)<input v-model="newDev.node" /></label>
        <label class="field">Categoria<select v-model="newDev.kind"><option>sensor</option><option>actuator</option><option>equipment</option></select></label>
        <label class="field">Tipo<input v-model="newDev.type" /></label>
        <label class="field">Unidade<input v-model="newDev.unit" style="width:5rem" /></label>
        <label class="field">Mín.<input type="number" step="any" v-model.number="newDev.normal_min" style="width:5rem" /></label>
        <label class="field">Máx.<input type="number" step="any" v-model.number="newDev.normal_max" style="width:5rem" /></label>
        <label class="field">Controlável<input type="checkbox" v-model="newDev.controllable" /></label>
        <button class="btn" @click="create">Cadastrar</button>
      </div>
    </div>
    <div class="card table-wrap">
      <h2>Regras de negócio (atuador automático)</h2>
      <table>
        <tr><th>Regra</th><th>Origem</th><th>Condição</th><th>Histerese</th><th>Atuador</th><th>Ativa</th><th></th></tr>
        <tr v-for="r in rules" :key="r.id">
          <td>{{ r.name }}</td><td class="mono">{{ r.source_device }}</td>
          <td><template v-if="r.operator === 'alert'">alerta crítico da IA</template>
            <template v-else>{{ r.operator }} <input v-if="auth.can('admin')" type="number" step="any" v-model.number="r.threshold" style="width:5rem" /><span v-else>{{ r.threshold }}</span></template></td>
          <td><input v-if="auth.can('admin') && r.operator !== 'alert'" type="number" step="any" v-model.number="r.hysteresis" style="width:4.5rem" /><span v-else>{{ r.hysteresis }}</span></td>
          <td class="mono">{{ r.actuator_device }}</td>
          <td>{{ r.enabled ? 'sim' : 'não' }}</td>
          <td><template v-if="auth.can('admin')"><button class="btn small ghost" @click="toggleRule(r)">{{ r.enabled ? 'Desativar' : 'Ativar' }}</button>
            <button v-if="r.operator !== 'alert'" class="btn small" @click="saveRule(r)">Salvar</button></template></td>
        </tr>
      </table>
    </div>
  </div>
</template>
