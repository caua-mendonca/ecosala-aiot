<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import BaseCard from '@/components/common/BaseCard.vue'
import LoadingState from '@/components/common/LoadingState.vue'
import ErrorState from '@/components/common/ErrorState.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ReadingLineChart from '@/components/charts/ReadingLineChart.vue'
import { useDevicesStore } from '@/stores/devicesStore'
import { useComfortStore } from '@/stores/comfortStore'
import { fetchReadingHistory } from '@/services/readingService'
import type { Reading } from '@/domain/Reading'
import { formatNumber } from '@/utils/formatNumber'
import { computeStats } from '@/utils/statistics'

interface PeriodOption {
  label: string
  start: string
  window: string
}

const PERIOD_OPTIONS: PeriodOption[] = [
  { label: '15 minutos', start: '-15m', window: '30s' },
  { label: '1 hora', start: '-1h', window: '1m' },
  { label: '6 horas', start: '-6h', window: '5m' },
  { label: '24 horas', start: '-24h', window: '15m' },
  { label: '7 dias', start: '-7d', window: '1h' },
]

const devicesStore = useDevicesStore()
const comfortStore = useComfortStore()

const selectedDeviceId = ref('')
const selectedPeriodLabel = ref(PERIOD_OPTIONS[1]!.label)
const selectedPeriod = computed(
  () =>
    PERIOD_OPTIONS.find((period) => period.label === selectedPeriodLabel.value) ??
    PERIOD_OPTIONS[1]!,
)

const history = ref<Reading[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

async function loadHistory(): Promise<void> {
  if (!selectedDeviceId.value) {
    return
  }
  isLoading.value = true
  error.value = null
  try {
    history.value = await fetchReadingHistory({
      deviceId: selectedDeviceId.value,
      start: selectedPeriod.value.start,
      stop: 'now()',
      window: selectedPeriod.value.window,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erro ao carregar histórico.'
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([devicesStore.refresh(), comfortStore.load()])
  const firstDevice = devicesStore.devices[0]
  if (firstDevice) {
    selectedDeviceId.value = firstDevice.device_id
  }
})

watch([selectedDeviceId, selectedPeriodLabel], loadHistory)

const temperatureStats = computed(() => computeStats(history.value.map((r) => r.temperature)))
const humidityStats = computed(() => computeStats(history.value.map((r) => r.humidity)))
const luminosityStats = computed(() => computeStats(history.value.map((r) => r.luminosity)))
</script>

<template>
  <section class="history-view">
    <h1>Histórico</h1>

    <div class="history-view__controls">
      <label>
        Dispositivo
        <select v-model="selectedDeviceId">
          <option
            v-for="device in devicesStore.devices"
            :key="device.device_id"
            :value="device.device_id"
          >
            {{ device.room_id }} ({{ device.device_id }})
          </option>
        </select>
      </label>

      <label>
        Período
        <select v-model="selectedPeriodLabel">
          <option v-for="period in PERIOD_OPTIONS" :key="period.label" :value="period.label">
            {{ period.label }}
          </option>
        </select>
      </label>
    </div>

    <LoadingState v-if="isLoading" message="Carregando histórico..." />
    <ErrorState v-else-if="error" :message="error" @retry="loadHistory" />
    <EmptyState
      v-else-if="devicesStore.devices.length === 0"
      message="Nenhum dispositivo conhecido ainda."
    />
    <EmptyState v-else-if="history.length === 0" message="Nenhum dado no período selecionado." />

    <template v-else>
      <BaseCard>
        <h2>Temperatura (°C)</h2>
        <ReadingLineChart
          :readings="history"
          metric="temperature"
          unit="Temperatura (°C)"
          :reference-min="comfortStore.thresholds?.temperature_min_c"
          :reference-max="comfortStore.thresholds?.temperature_max_c"
        />
      </BaseCard>

      <BaseCard>
        <h2>Umidade (%)</h2>
        <ReadingLineChart
          :readings="history"
          metric="humidity"
          unit="Umidade (%)"
          :reference-min="comfortStore.thresholds?.humidity_min_percent"
          :reference-max="comfortStore.thresholds?.humidity_max_percent"
        />
      </BaseCard>

      <BaseCard>
        <h2>Luminosidade (lux)</h2>
        <ReadingLineChart
          :readings="history"
          metric="luminosity"
          unit="Luminosidade (lux)"
          :reference-min="comfortStore.thresholds?.luminosity_min_lux"
        />
      </BaseCard>

      <BaseCard>
        <h2>Resumo do período</h2>
        <table class="history-view__summary">
          <thead>
            <tr>
              <th>Métrica</th>
              <th>Mínimo</th>
              <th>Máximo</th>
              <th>Média</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Temperatura (°C)</td>
              <td>{{ formatNumber(temperatureStats.min) }}</td>
              <td>{{ formatNumber(temperatureStats.max) }}</td>
              <td>{{ formatNumber(temperatureStats.mean) }}</td>
            </tr>
            <tr>
              <td>Umidade (%)</td>
              <td>{{ formatNumber(humidityStats.min) }}</td>
              <td>{{ formatNumber(humidityStats.max) }}</td>
              <td>{{ formatNumber(humidityStats.mean) }}</td>
            </tr>
            <tr>
              <td>Luminosidade (lux)</td>
              <td>{{ formatNumber(luminosityStats.min, 0) }}</td>
              <td>{{ formatNumber(luminosityStats.max, 0) }}</td>
              <td>{{ formatNumber(luminosityStats.mean, 0) }}</td>
            </tr>
          </tbody>
        </table>
      </BaseCard>
    </template>
  </section>
</template>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.history-view__controls {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.history-view__controls label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.history-view__controls select {
  padding: 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: inherit;
  font: inherit;
}

.history-view__summary {
  width: 100%;
  border-collapse: collapse;
}

.history-view__summary th,
.history-view__summary td {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}
</style>
