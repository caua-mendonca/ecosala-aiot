<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const links = ref<Array<{ name: string; url: string; user: string | null }>>([])
const health = ref<any>(null)
onMounted(async () => {
  links.value = await api('/infra/links')
  health.value = await api('/health')
})
const flow = [
  ['IoT → Web', 'simulador → MQTT (Mosquitto) → gateway → RabbitMQ (ecosala.telemetry) → gravador → InfluxDB · → q.websocket → API → WebSocket → dashboard e 3D'],
  ['Web → IoT', 'botão no dashboard → API REST → RabbitMQ (ecosala.commands / q.commands) → gateway → MQTT → simulador → atuador muda e aparece nas leituras seguintes'],
  ['IA', 'Laboratório (q.jobs.generate) → dados sintéticos → Treino (q.jobs.train) → modelos → inferência consome q.inference → previsões e alertas em ecosala.events → interface'],
]
</script>

<template>
  <div class="stack">
    <div class="card">
      <h2>Interfaces de administração (somente em 127.0.0.1, para exploração em aula)</h2>
      <table><tr><th>Interface</th><th>Endereço</th><th>Usuário</th></tr>
        <tr v-for="l in links" :key="l.name"><td>{{ l.name }}</td><td><a :href="l.url" target="_blank" rel="noopener noreferrer">{{ l.url }}</a></td><td class="mono">{{ l.user ?? '(login da aplicação)' }}</td></tr></table>
      <small>As senhas ficam no arquivo <code>.env</code> (gerado por <code>scripts/gerar_segredos.py</code>, fora do Git).</small>
    </div>
    <div class="card" v-if="health"><h2>Saúde da API</h2>
      <span v-for="(v, k) in health" :key="k" class="pill" :class="v === true || v === 'ok' ? 'normal' : 'critico'" style="margin-right:.4rem">{{ k }}: {{ v }}</span></div>
    <div class="card"><h2>Fluxos obrigatórios</h2>
      <table><tr v-for="[n, f] in flow" :key="n"><td><b>{{ n }}</b></td><td>{{ f }}</td></tr></table>
      <p class="muted">InfluxDB guarda leituras e telemetria. PostgreSQL guarda usuários, dispositivos, configurações, regras, alertas, jobs, versões de modelo e auditoria.</p>
    </div>
  </div>
</template>
