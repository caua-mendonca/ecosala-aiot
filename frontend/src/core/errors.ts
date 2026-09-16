import axios from 'axios'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly cause?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function extractDetailMessage(data: unknown): string | undefined {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
  }
  return undefined
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error
  }

  if (axios.isAxiosError(error)) {
    const message = extractDetailMessage(error.response?.data) ?? error.message
    return new ApiError(message, error)
  }

  return new ApiError('Erro inesperado ao comunicar com a API.', error)
}
