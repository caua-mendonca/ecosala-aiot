export interface Device {
  device_id: string
  room_id: string
  online: boolean
  last_seen: string | null
}
