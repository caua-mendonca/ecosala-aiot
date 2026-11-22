import type { ItemStatus } from '../types'

export const STATUS_LABEL: Record<ItemStatus, string> = {
  normal: 'Normal',
  atencao: 'Atenção',
  critico: 'Crítico',
  nodata: 'Sem dados',
}
export const STATUS_COLOR: Record<ItemStatus, string> = {
  normal: '#16a34a',
  atencao: '#d97706',
  critico: '#dc2626',
  nodata: '#94a3b8',
}

export const TYPE_LABEL: Record<string, string> = {
  temperature: 'Temperatura',
  humidity: 'Umidade',
  luminosity: 'Luminosidade',
  co2: 'CO₂',
  presence: 'Presença',
  fan: 'Ventilação',
  light: 'Iluminação',
  alarm: 'Sinalização',
  air_conditioner: 'Ar-condicionado',
}

export const MODE_LABEL: Record<string, string> = {
  rolamento: 'Desgaste de rolamento',
  superaquecimento: 'Superaquecimento',
  entupimento: 'Entupimento (filtro/obstrução)',
  desbalanceamento: 'Desbalanceamento',
  deriva_sensor: 'Deriva de sensor',
  travamento_sensor: 'Travamento de sensor',
}

export function num(v: unknown, digits = 1): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return v.toLocaleString('pt-BR', { maximumFractionDigits: digits, minimumFractionDigits: 0 })
}

export function dt(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function time(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function big(n: number): string {
  return n.toLocaleString('pt-BR')
}

export function rul(h: number | undefined | null, capped?: boolean): string {
  if (h === undefined || h === null) return '—'
  if (capped) return '> 7 dias'
  if (h >= 48) return `${num(h / 24, 1)} dias`
  return `${num(h, 0)} h`
}
