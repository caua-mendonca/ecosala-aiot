export type ComfortStatus = 'OK' | 'ATENCAO' | 'CRITICO'

/**
 * Espelha ReadingSummarySchema da API (backend/app/presentation/api/v1/schemas.py).
 * Os nomes de campo seguem snake_case de proposito, identicos ao JSON da API.
 */
export interface Reading {
  device_id: string
  room_id: string
  timestamp: string
  temperature: number
  humidity: number
  luminosity: number
  comfort_status: ComfortStatus
}
