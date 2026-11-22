import { httpClient } from '@/core/httpClient'
import { toApiError } from '@/core/errors'
import type { ComfortThresholds } from '@/domain/ComfortThresholds'

export async function fetchComfortThresholds(): Promise<ComfortThresholds> {
  try {
    const response = await httpClient.get<ComfortThresholds>('/comfort/thresholds')
    return response.data
  } catch (error) {
    throw toApiError(error)
  }
}
