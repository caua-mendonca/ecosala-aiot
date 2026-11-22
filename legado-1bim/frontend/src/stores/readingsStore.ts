import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Reading } from '@/domain/Reading'
import { fetchLatestReadings } from '@/services/readingService'

export const useReadingsStore = defineStore('readings', () => {
  const readings = ref<Reading[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdatedAt = ref<Date | null>(null)

  async function refresh(roomId?: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      readings.value = await fetchLatestReadings(roomId)
      lastUpdatedAt.value = new Date()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao carregar leituras.'
    } finally {
      isLoading.value = false
    }
  }

  return { readings, isLoading, error, lastUpdatedAt, refresh }
})
