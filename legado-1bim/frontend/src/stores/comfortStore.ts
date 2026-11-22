import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { ComfortThresholds } from '@/domain/ComfortThresholds'
import { fetchComfortThresholds } from '@/services/comfortService'

export const useComfortStore = defineStore('comfort', () => {
  const thresholds = ref<ComfortThresholds | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    if (thresholds.value) {
      return
    }
    isLoading.value = true
    error.value = null
    try {
      thresholds.value = await fetchComfortThresholds()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao carregar faixas de conforto.'
    } finally {
      isLoading.value = false
    }
  }

  return { thresholds, isLoading, error, load }
})
