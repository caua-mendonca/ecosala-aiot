<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { dt } from '../utils/format'

const rows = ref<any[]>([])
const filter = ref('')
async function load() { rows.value = await api(`/audit?limit=300${filter.value ? '&action=' + encodeURIComponent(filter.value) : ''}`) }
onMounted(load)
</script>

<template>
  <div class="stack">
    <div class="card row">
      <label class="field">Filtrar por ação
        <select v-model="filter" @change="load"><option value="">todas</option><option value="login">logins</option><option value="comando">comandos</option>
          <option value="job">jobs disparados</option><option value="assistente">perguntas ao assistente</option><option value="simulador">simulador</option>
          <option value="dispositivo">cadastro de dispositivos</option><option value="regra">regras</option></select></label>
      <button class="btn" @click="load">Atualizar</button>
      <span class="spacer" /><small>Tabela audit_log no PostgreSQL</small>
    </div>
    <div class="card table-wrap">
      <table><tr><th>Instante</th><th>Usuário</th><th>Ação</th><th>Alvo</th><th>Detalhes</th></tr>
        <tr v-for="r in rows" :key="r.id"><td>{{ dt(r.ts) }}</td><td>{{ r.username }}</td><td class="mono">{{ r.action }}</td><td class="mono">{{ r.target }}</td>
          <td class="mono truncate" :title="JSON.stringify(r.details)">{{ JSON.stringify(r.details) }}</td></tr></table>
    </div>
  </div>
</template>
