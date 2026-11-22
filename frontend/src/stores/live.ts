// Estado em tempo real: recebido SOMENTE pelo WebSocket da API.
// A cena 3D lê este store dentro do loop de animação (não redesenha a cada mensagem).
import { defineStore } from 'pinia'
import { computed, ref, shallowReactive } from 'vue'
import { api } from '../api'
import type { Alert, Device, Envelope, ItemStatus, Prediction } from '../types'

const HISTORY = 60

export const useLive = defineStore('live', () => {
  const latest = shallowReactive<Record<string, Envelope>>({})
  const receivedAt = shallowReactive<Record<string, number>>({})
  const history = shallowReactive<Record<string, Array<[string, number]>>>({})
  const predictions = shallowReactive<Record<string, Envelope>>({})
  const nodeStatus = shallowReactive<Record<string, string>>({})
  const jobs = shallowReactive<Record<string, Envelope>>({})
  const alertsOpen = ref<Alert[]>([])
  const acks = ref<Envelope[]>([])
  const devices = ref<Device[]>([])
  const connected = ref(false)
  const lastTelemetry = ref(0)
  const now = ref(Date.now())
  const noDataSeconds = ref(10)
  let ws: WebSocket | null = null
  let stopped = true
  let retry = 1000
  let pingTimer: number | undefined
  let clockTimer: number | undefined
  const listeners = new Set<(e: Envelope) => void>()

  const deviceById = computed(() => Object.fromEntries(devices.value.map((d) => [d.id, d])))
  const hasData = computed(() => lastTelemetry.value > 0 && now.value - lastTelemetry.value < noDataSeconds.value * 1000)

  function valueOf(env: Envelope | undefined): number | null {
    if (!env) return null
    const p = env.payload
    if (p.kind === 'sensor') return p.value
    if (p.kind === 'equipment') return p.vibration
    if (p.kind === 'actuator') return p.state ? 1 : 0
    return null
  }

  function ingest(e: Envelope) {
    if (e.type === 'telemetry' && e.device) {
      latest[e.device] = e
      receivedAt[e.device] = Date.now()
      lastTelemetry.value = Date.now()
      const v = valueOf(e)
      if (v !== null) {
        const h = history[e.device] ? [...history[e.device]] : []
        h.push([e.ts, v])
        if (h.length > HISTORY) h.splice(0, h.length - HISTORY)
        history[e.device] = h
      }
    } else if (e.type === 'prediction' && e.device) {
      predictions[e.device] = e
    } else if (e.type === 'status' && e.device) {
      nodeStatus[e.device] = e.payload.state
    } else if (e.type === 'alert') {
      void loadAlerts()
    } else if (e.type.startsWith('job.') && e.payload.job_id) {
      jobs[e.payload.job_id] = e
    } else if (e.type === 'command.ack') {
      acks.value = [e, ...acks.value].slice(0, 10)
    }
    listeners.forEach((fn) => fn(e))
  }

  function applySnapshot(s: any) {
    for (const [k, v] of Object.entries<Envelope>(s.latest ?? {})) latest[k] = v
    for (const [k, v] of Object.entries<Array<[string, number]>>(s.history ?? {})) history[k] = v
    for (const [k, v] of Object.entries<Envelope>(s.predictions ?? {})) predictions[k] = v
    for (const [k, v] of Object.entries<Envelope>(s.status ?? {})) nodeStatus[k] = v.payload.state
    const age = s.last_telemetry_age_s
    if (typeof age === 'number' && age < noDataSeconds.value) {
      lastTelemetry.value = Date.now() - age * 1000
      for (const k of Object.keys(s.latest ?? {})) receivedAt[k] = lastTelemetry.value
    }
  }

  async function loadDevices() {
    devices.value = await api<Device[]>('/devices')
  }
  async function loadAlerts() {
    try {
      alertsOpen.value = await api<Alert[]>('/alerts?state=open')
    } catch {
      /* ignora */
    }
  }

  async function connect() {
    stopped = false
    try {
      const settings = await api<Record<string, any>>('/settings')
      if (typeof settings.no_data_seconds === 'number') noDataSeconds.value = settings.no_data_seconds
    } catch {
      /* usa padrão */
    }
    await Promise.all([loadDevices(), loadAlerts()])
    open()
    clockTimer = window.setInterval(() => (now.value = Date.now()), 1000)
  }

  async function open() {
    if (stopped) return
    try {
      const { ticket } = await api<{ ticket: string }>('/auth/ws-ticket', { method: 'POST' })
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws?ticket=${encodeURIComponent(ticket)}`)
    } catch {
      scheduleReconnect()
      return
    }
    ws.onopen = () => {
      connected.value = true
      retry = 1000
      pingTimer = window.setInterval(() => ws?.readyState === 1 && ws.send('ping'), 20000)
    }
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data)
      if (data.type === 'hello') applySnapshot(data.snapshot)
      else if (data.type !== 'pong') ingest(data as Envelope)
    }
    ws.onclose = () => {
      connected.value = false
      window.clearInterval(pingTimer)
      scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (stopped) return
    window.setTimeout(open, retry)
    retry = Math.min(retry * 2, 15000)
  }

  function disconnect() {
    stopped = true
    window.clearInterval(clockTimer)
    ws?.close()
  }

  function onMessage(fn: (e: Envelope) => void) {
    listeners.add(fn)
    return () => listeners.delete(fn)
  }

  function isFresh(id: string): boolean {
    const t = receivedAt[id]
    return !!t && now.value - t < noDataSeconds.value * 1000
  }

  // Estado de cor: normal, atenção, crítico ou sem dados (faixa normal do sensor + alertas da IA)
  function statusOf(id: string, at: number = now.value): ItemStatus {
    const t = receivedAt[id]
    if (!t || at - t > noDataSeconds.value * 1000) return 'nodata'
    const d = deviceById.value[id]
    const env = latest[id]
    if (!d || !env) return 'nodata'
    if (d.kind === 'equipment') {
      if (env.payload.failed) return 'critico'
      if (alertsOpen.value.some((a) => a.device === id)) return 'critico'
      const p = predictions[id]?.payload as Prediction | undefined
      return p ? p.status : 'normal'
    }
    if (d.kind === 'sensor') return rangeStatus(env.payload.value, d.normal_min, d.normal_max)
    return 'normal'
  }

  return {
    latest, receivedAt, history, predictions, nodeStatus, jobs, alertsOpen, acks, devices, connected,
    lastTelemetry, now, hasData, deviceById, noDataSeconds,
    connect, disconnect, loadDevices, loadAlerts, onMessage, statusOf, isFresh, valueOf,
  }
})

export function rangeStatus(v: number, min: number | null, max: number | null): ItemStatus {
  const span = min !== null && max !== null ? max - min : Math.abs(max ?? min ?? 10)
  const margin = Math.max(span * 0.15, 1)
  if (max !== null && v > max) return v > max + margin ? 'critico' : 'atencao'
  if (min !== null && v < min) return v < min - margin ? 'critico' : 'atencao'
  return 'normal'
}
