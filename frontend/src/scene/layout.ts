// Posições 3D dos itens: ficam SÓ no frontend, indexadas pelo mesmo id do cadastro.
export type Vec3 = [number, number, number]

export const ROOM_W = 8
export const ROOM_D = 7
export const WALL_H = 3
export const BACK_Z = -ROOM_D / 2          // face interna da parede do fundo
export const CONDENSER_Z = -5.6

export const ROOMS: Record<string, number> = { 'sala-101': -10, 'sala-102': 0, 'lab-201': 10 }
export const STATION: Vec3 = [17, 0, 3]

export function roomNumber(room: string): string {
  return room.split('-').pop() ?? room
}

// posição de cada item em função da sala (x do centro da sala)
export function itemPosition(id: string): Vec3 | null {
  if (id === 'temp-ext') return [STATION[0], 2.3, STATION[2]]
  if (id === 'lum-ext') return [STATION[0], 3.05, STATION[2]]
  const [prefix, n] = id.split('-')
  const room = Object.keys(ROOMS).find((r) => roomNumber(r) === n)
  if (!room) return null
  const cx = ROOMS[room]
  const wall = BACK_Z + 0.08
  switch (prefix) {
    case 'temp': return [cx - 3.1, 1.7, wall]
    case 'umid': return [cx - 2.5, 1.7, wall]
    case 'lum': return [cx - 1.9, 1.7, wall]
    case 'co2': return [cx - 1.3, 1.7, wall]
    case 'pres': return [cx - ROOM_W / 2 + 0.08, 2.5, 1.5]
    case 'vent': return [cx - 1.6, WALL_H - 0.25, 0.6]
    case 'luz': return [cx + 1.6, WALL_H - 0.04, 0.9]
    case 'alarme': return [cx + ROOM_W / 2 - 0.12, 2.4, -1.6]
    case 'ac': return [cx + 1.5, 2.3, BACK_Z + 0.15]           // unidade interna (evaporadora)
    default: return null
  }
}

export function condenserPosition(room: string): Vec3 {
  return [ROOMS[room] + 1.5, 0.5, CONDENSER_Z]
}

export function deskSlots(room: string): Vec3[] {
  const cx = ROOMS[room]
  const out: Vec3[] = []
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 5; c++) out.push([cx - 2.8 + c * 1.4, 0, -1.2 + r * 1.2])
  }
  return out
}
