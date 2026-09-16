export type ComfortStatus = 'OK' | 'ATENCAO' | 'CRITICO'

export interface Reading {
  device_id: string
  room_id: string
  timestamp: string
  temperature: number
  humidity: number
  luminosity: number
  comfort_status: ComfortStatus
}
