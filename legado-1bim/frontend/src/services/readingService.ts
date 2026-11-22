import { httpClient } from '@/core/httpClient'
import { toApiError } from '@/core/errors'
import type { Reading } from '@/domain/Reading'

export async function fetchLatestReadings(roomId?: string): Promise<Reading[]> {
  try {
    const response = await httpClient.get<Reading[]>('/readings/latest', {
      params: roomId ? { room_id: roomId } : undefined,
    })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}

export interface ReadingHistoryParams {
  deviceId: string
  start: string
  stop: string
  window: string
}

export async function fetchReadingHistory(params: ReadingHistoryParams): Promise<Reading[]> {
  try {
    const response = await httpClient.get<Reading[]>('/readings/history', {
      params: {
        device_id: params.deviceId,
        start: params.start,
        stop: params.stop,
        window: params.window,
      },
    })
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
