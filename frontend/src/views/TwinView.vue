<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import DevicePanel from '../components/DevicePanel.vue'
import { Twin, type TwinData } from '../scene/twin'
import { useLive } from '../stores/live'
import { STATUS_COLOR, STATUS_LABEL } from '../utils/format'
import type { ItemStatus } from '../types'

const live = useLive()
const host = ref<HTMLDivElement | null>(null)
const selected = ref<string | null>(null)
let twin: Twin | null = null

// Acesso somente-leitura ao store, consultado dentro do loop de animação
const data: TwinData = {
  hasData: () => live.lastTelemetry > 0 && Date.now() - live.lastTelemetry < live.noDataSeconds * 1000,
  value: (id) => {
    const p = live.latest[id]?.payload
    return p && typeof p.value === 'number' ? p.value : null
  },
  state: (id) => !!live.latest[id]?.payload?.state,
  equipment: (id) => live.latest[id]?.payload ?? null,
  status: (id) => live.statusOf(id, Date.now()),
  deviceIds: () => live.devices.map((d) => d.id),
}

onMounted(() => {
  if (host.value) twin = new Twin(host.value, data, (id) => { selected.value = id })
})
onBeforeUnmount(() => twin?.dispose())

function close() {
  selected.value = null
  twin?.select(null)
}
const legend: ItemStatus[] = ['normal', 'atencao', 'critico', 'nodata']
</script>

<template>
  <div class="twin-page">
    <div ref="host" class="viewport" />
    <div v-if="!live.hasData" class="overlay">
      <b>Sem dados em tempo real</b>
      <span>{{ live.connected ? 'O simulador parou de enviar telemetria. A cena está congelada.' : 'WebSocket desconectado; reconectando…' }}</span>
    </div>
    <div class="legend card">
      <div v-for="s in legend" :key="s" class="row"><span class="dot" :style="{ background: STATUS_COLOR[s] }" />{{ STATUS_LABEL[s] }}</div>
      <small>Clique em um item · arraste para girar · role para zoom</small>
    </div>
    <div v-if="selected" class="side-panel">
      <DevicePanel :device-id="selected" @close="close" />
    </div>
  </div>
</template>

<style scoped>
.twin-page { position: relative; height: calc(100vh - 110px); min-height: 480px; border-radius: 12px; overflow: hidden; border: 1px solid var(--line); }
.viewport { position: absolute; inset: 0; }
.overlay { position: absolute; top: 1rem; left: 50%; transform: translateX(-50%); background: rgba(15, 23, 42, .85); color: #fff; padding: .7rem 1.1rem; border-radius: 10px; display: flex; flex-direction: column; align-items: center; gap: .2rem; pointer-events: none; }
.legend { position: absolute; left: 1rem; bottom: 1rem; display: flex; flex-direction: column; gap: .2rem; padding: .6rem .8rem; background: rgba(255,255,255,.92); }
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.side-panel { position: absolute; top: 1rem; right: 1rem; width: 330px; max-height: calc(100% - 2rem); overflow-y: auto; }
</style>
