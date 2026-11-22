import { httpClient } from '@/core/httpClient'
import { toApiError } from '@/core/errors'
import type { Device } from '@/domain/Device'

export async function fetchDevices(): Promise<Device[]> {
  try {
    const response = await httpClient.get<Device[]>('/devices')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
