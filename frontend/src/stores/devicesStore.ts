import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Device } from '@/domain/Device'
import { fetchDevices } from '@/services/deviceService'

export const useDevicesStore = defineStore('devices', () => {
  const devices = ref<Device[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  async function refresh(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      devices.value = await fetchDevices()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erro ao carregar dispositivos.'
    } finally {
      isLoading.value = false
    }
  }

  return { devices, isLoading, error, refresh }
})
