export interface Envelope {
  id: string
  ts: string
  type: string
  device: string | null
  room: string | null
  payload: Record<string, any>
  rk?: string
}

export interface Device {
  id: string
  name: string
  room: string
  kind: 'sensor' | 'actuator' | 'equipment'
  type: string
  unit: string | null
  normal_min: number | null
  normal_max: number | null
  controllable: boolean
  node: string
  enabled: boolean
}

export interface Prediction {
  health: number
  rul_h: number
  rul_capped: boolean
  trend: number
  status: 'normal' | 'atencao' | 'critico'
  model_version: number
  failed: boolean
}

export interface Alert {
  id: number
  device: string
  room: string
  kind: string
  severity: string
  message: string
  health: number | null
  rul_h: number | null
  state: string
  opened_at: string
  closed_at: string | null
}

export type ItemStatus = 'normal' | 'atencao' | 'critico' | 'nodata'

export interface Job {
  id: string
  kind: 'generate' | 'train'
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  message: string | null
  params: Record<string, any> | null
  result: Record<string, any> | null
  created_by: string | null
  created_at: string
  updated_at: string
}
