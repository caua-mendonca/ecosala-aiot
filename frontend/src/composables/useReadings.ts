import { useReadingsStore } from '@/stores/readingsStore'
import { useDevicesStore } from '@/stores/devicesStore'
import { usePolling } from '@/composables/usePolling'

const DASHBOARD_POLL_INTERVAL_MS = 5000

/**
 * Mantem leituras e dispositivos atualizados a cada 5s enquanto o
 * componente chamador estiver montado (ver usePolling).
 */
export function useReadings() {
  const readingsStore = useReadingsStore()
  const devicesStore = useDevicesStore()

  async function refreshAll(): Promise<void> {
    await Promise.all([readingsStore.refresh(), devicesStore.refresh()])
  }

  usePolling(refreshAll, DASHBOARD_POLL_INTERVAL_MS)

  return { readingsStore, devicesStore, refreshAll }
}
