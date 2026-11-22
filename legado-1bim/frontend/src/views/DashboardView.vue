<script setup lang="ts">
import { computed } from 'vue'
import BaseCard from '@/components/common/BaseCard.vue'
import LoadingState from '@/components/common/LoadingState.vue'
import ErrorState from '@/components/common/ErrorState.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import MetricCard from '@/components/dashboard/MetricCard.vue'
import StatusBadge from '@/components/dashboard/StatusBadge.vue'
import { useReadings } from '@/composables/useReadings'
import { formatDateTimeFull } from '@/utils/formatDate'
import { formatNumber } from '@/utils/formatNumber'

const { readingsStore, devicesStore, refreshAll } = useReadings()

const isLoading = computed(
  () => (readingsStore.isLoading || devicesStore.isLoading) && readingsStore.readings.length === 0,
)
const error = computed(() => readingsStore.error ?? devicesStore.error)

function isDeviceOnline(deviceId: string): boolean {
  return devicesStore.devices.find((device) => device.device_id === deviceId)?.online ?? false
}
</script>

<template>
  <section class="dashboard-view">
    <h1>Dashboard</h1>

    <LoadingState v-if="isLoading" message="Carregando leituras..." />
    <ErrorState v-else-if="error" :message="error" @retry="refreshAll" />
    <EmptyState
      v-else-if="readingsStore.readings.length === 0"
      message="Nenhuma leitura recebida ainda. Verifique se o backend e o Mosquitto estão rodando."
    />

    <div v-else class="dashboard-view__grid">
      <BaseCard
        v-for="reading in readingsStore.readings"
        :key="reading.device_id"
        class="dashboard-view__card"
      >
        <header class="dashboard-view__card-header">
          <div>
            <h2>{{ reading.room_id }}</h2>
            <span class="dashboard-view__device-id">{{ reading.device_id }}</span>
          </div>
          <StatusBadge :status="reading.comfort_status" />
        </header>

        <div class="dashboard-view__metrics">
          <MetricCard label="Temperatura" :value="formatNumber(reading.temperature)" unit="°C" />
          <MetricCard label="Umidade" :value="formatNumber(reading.humidity)" unit="%" />
          <MetricCard
            label="Luminosidade"
            :value="formatNumber(reading.luminosity, 0)"
            unit="lux"
          />
        </div>

        <footer class="dashboard-view__footer">
          <span
            class="dashboard-view__connection"
            :class="isDeviceOnline(reading.device_id) ? 'is-online' : 'is-offline'"
          >
            {{ isDeviceOnline(reading.device_id) ? 'Online' : 'Offline' }}
          </span>
          <span>Atualizado: {{ formatDateTimeFull(reading.timestamp) }}</span>
        </footer>
      </BaseCard>
    </div>
  </section>
</template>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.dashboard-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}

.dashboard-view__card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
}

.dashboard-view__device-id {
  display: block;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.dashboard-view__metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.dashboard-view__footer {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border);
  padding-top: 0.75rem;
}

.dashboard-view__connection {
  font-weight: 600;
}

.dashboard-view__connection.is-online {
  color: var(--color-status-ok-text);
}

.dashboard-view__connection.is-offline {
  color: var(--color-status-critico-text);
}
</style>
