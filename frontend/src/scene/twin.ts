// Gêmeo digital 3D do campus (Three.js, cena procedural de poucos polígonos).
// Regras atendidas:
//  - a cena só muda com dados do WebSocket (lidos do store dentro do loop de animação);
//  - sem dados recentes: animações param e todos os itens ficam cinza ("sem dados");
//  - cada item tem cor de estado (normal/atenção/crítico/sem dados) e é clicável;
//  - atuadores animados; o condensador treme proporcionalmente à vibração;
//  - ambiente reage a dados reais: dia/noite (luminosidade externa), névoa de CO₂,
//    ocupação (presença), luz interna (lâmpada/luminosidade);
//  - tubulações saem e chegam exatamente nos pontos de conexão dos equipamentos;
//  - repetições (carteiras, pessoas, árvores) usam InstancedMesh.
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { ItemStatus } from '../types'
import {
  BACK_Z, CONDENSER_Z, ROOMS, ROOM_D, ROOM_W, STATION, WALL_H, condenserPosition, deskSlots, itemPosition, roomNumber,
} from './layout'

export interface TwinData {
  hasData(): boolean
  value(id: string): number | null
  state(id: string): boolean
  equipment(id: string): Record<string, any> | null
  status(id: string): ItemStatus
  deviceIds(): string[]
}

const STATUS_HEX: Record<ItemStatus, number> = { normal: 0x22c55e, atencao: 0xf59e0b, critico: 0xef4444, nodata: 0x94a3b8 }

interface Item {
  id: string
  root: THREE.Object3D
  status: THREE.Mesh[]          // malhas que recebem a cor de estado
  lastStatus?: ItemStatus
  animate?: (dt: number, t: number, live: boolean) => void
}

export class Twin {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private camera: THREE.PerspectiveCamera
  private controls: OrbitControls
  private clock = new THREE.Clock()
  private items = new Map<string, Item[]>()
  private pickables: THREE.Object3D[] = []
  private raf = 0
  private ro: ResizeObserver
  private hemi: THREE.HemisphereLight
  private sun: THREE.DirectionalLight
  private sunMesh: THREE.Mesh
  private stars: THREE.Points
  private dayColor = new THREE.Color(0xbfe3ff)
  private nightColor = new THREE.Color(0x0b1026)
  private bg = new THREE.Color(0xbfe3ff)
  private fog = new THREE.Fog(0xbfe3ff, 60, 160)
  private roomFx: Record<string, { haze: THREE.Mesh; people: THREE.InstancedMesh; floor: THREE.MeshStandardMaterial }> = {}
  private dummy = new THREE.Object3D()
  private downAt: [number, number] | null = null
  private highlight: THREE.Mesh

  constructor(private container: HTMLElement, private data: TwinData, private onPick: (id: string | null) => void) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.shadowMap.enabled = true
    container.appendChild(this.renderer.domElement)
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 400)
    this.camera.position.set(4, 19, 26)
    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.target.set(2, 1, -1)
    this.controls.enableDamping = true
    this.controls.maxPolarAngle = Math.PI * 0.48
    this.controls.minDistance = 6
    this.controls.maxDistance = 80

    this.scene.background = this.bg
    this.scene.fog = this.fog
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x445544, 0.8)
    this.scene.add(this.hemi)
    this.sun = new THREE.DirectionalLight(0xfff2d6, 1.5)
    this.sun.position.set(20, 30, 15)
    this.sun.castShadow = true
    this.sun.shadow.mapSize.set(1024, 1024)
    Object.assign(this.sun.shadow.camera, { left: -30, right: 30, top: 30, bottom: -30, far: 120 })
    this.sun.shadow.camera.updateProjectionMatrix()
    this.scene.add(this.sun)
    this.sunMesh = new THREE.Mesh(new THREE.SphereGeometry(2, 16, 12), new THREE.MeshBasicMaterial({ color: 0xffe08a }))
    this.scene.add(this.sunMesh)
    this.stars = this.makeStars()
    this.scene.add(this.stars)

    this.buildGround()
    for (const room of Object.keys(ROOMS)) this.buildRoom(room)
    this.buildStation()
    this.highlight = new THREE.Mesh(new THREE.RingGeometry(0.45, 0.55, 32),
      new THREE.MeshBasicMaterial({ color: 0x0ea5e9, side: THREE.DoubleSide, transparent: true, opacity: 0.9 }))
    this.highlight.visible = false
    this.scene.add(this.highlight)

    this.ro = new ResizeObserver(() => this.resize())
    this.ro.observe(container)
    this.resize()
    const el = this.renderer.domElement
    el.addEventListener('pointerdown', this.onDown)
    el.addEventListener('pointerup', this.onUp)
    this.loop()
  }

  // ------------------------------------------------------------------ construção
  private mat(color: number, extra: THREE.MeshStandardMaterialParameters = {}) {
    return new THREE.MeshStandardMaterial({ color, roughness: 0.8, metalness: 0.05, ...extra })
  }

  private box(w: number, h: number, d: number, color: number, pos: [number, number, number], extra = {}) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), this.mat(color, extra))
    m.position.set(...pos)
    m.castShadow = true
    m.receiveShadow = true
    return m
  }

  private register(id: string, root: THREE.Object3D, status: THREE.Mesh[], animate?: Item['animate']) {
    root.userData.deviceId = id
    root.traverse((o) => { o.userData.deviceId = id })
    this.scene.add(root)
    this.pickables.push(root)
    const list = this.items.get(id) ?? []
    list.push({ id, root, status, animate })
    this.items.set(id, list)
  }

  private label(text: string, pos: [number, number, number], size = 1.6) {
    const c = document.createElement('canvas')
    c.width = 256
    c.height = 64
    const g = c.getContext('2d')!
    g.fillStyle = 'rgba(15,31,28,0.75)'
    g.fillRect(0, 0, 256, 64)
    g.fillStyle = '#fff'
    g.font = 'bold 30px sans-serif'
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.fillText(text, 128, 33)
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthTest: false }))
    s.scale.set(size * 4, size, 1)
    s.position.set(...pos)
    this.scene.add(s)
  }

  private makeStars() {
    const n = 400
    const pos = new Float32Array(n * 3)
    for (let i = 0; i < n; i++) {
      const th = Math.random() * Math.PI * 2
      const ph = Math.random() * Math.PI * 0.45
      pos.set([Math.cos(th) * Math.sin(ph) * 150, Math.cos(ph) * 150 + 10, Math.sin(th) * Math.sin(ph) * 150], i * 3)
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    return new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.7, transparent: true, opacity: 0 }))
  }

  private buildGround() {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(140, 140), this.mat(0x6aa36b))
    ground.rotation.x = -Math.PI / 2
    ground.receiveShadow = true
    this.scene.add(ground)
    const path = new THREE.Mesh(new THREE.PlaneGeometry(40, 3), this.mat(0xc9c2b4))
    path.rotation.x = -Math.PI / 2
    path.position.set(0, 0.01, 6)
    this.scene.add(path)
    // árvores com InstancedMesh (tronco + copa)
    const spots: Array<[number, number]> = []
    for (let i = 0; i < 46; i++) {
      const a = (i / 46) * Math.PI * 2
      const r = 32 + (i % 5) * 3
      spots.push([Math.cos(a) * r, Math.sin(a) * r * 0.8])
    }
    const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.2, 0.3, 2, 6), this.mat(0x7c5a3a), spots.length)
    const crowns = new THREE.InstancedMesh(new THREE.ConeGeometry(1.4, 3.2, 7), this.mat(0x2f7d4a), spots.length)
    spots.forEach(([x, z], i) => {
      this.dummy.position.set(x, 1, z)
      this.dummy.scale.setScalar(1)
      this.dummy.updateMatrix()
      trunks.setMatrixAt(i, this.dummy.matrix)
      this.dummy.position.set(x, 3.4, z)
      this.dummy.scale.setScalar(0.8 + (i % 3) * 0.25)
      this.dummy.updateMatrix()
      crowns.setMatrixAt(i, this.dummy.matrix)
    })
    trunks.castShadow = crowns.castShadow = true
    this.scene.add(trunks, crowns)
  }

  private buildRoom(room: string) {
    const cx = ROOMS[room]
    const n = roomNumber(room)
    const floorMat = this.mat(0xd9d4c7)
    const floor = new THREE.Mesh(new THREE.BoxGeometry(ROOM_W, 0.1, ROOM_D), floorMat)
    floor.position.set(cx, 0.05, 0)
    floor.receiveShadow = true
    this.scene.add(floor)
    const wallMat = { transparent: false }
    this.scene.add(this.box(ROOM_W, WALL_H, 0.2, 0xeef0ea, [cx, WALL_H / 2, BACK_Z - 0.1], wallMat))
    this.scene.add(this.box(0.2, WALL_H, ROOM_D, 0xe4e7df, [cx - ROOM_W / 2 - 0.1, WALL_H / 2, 0], wallMat))
    this.scene.add(this.box(0.2, WALL_H, ROOM_D, 0xe4e7df, [cx + ROOM_W / 2 + 0.1, WALL_H / 2, 0], wallMat))
    this.scene.add(this.box(ROOM_W + 0.4, 0.6, 0.15, 0xe4e7df, [cx, 0.3, ROOM_D / 2]))
    this.label(room, [cx, WALL_H + 1.1, BACK_Z])

    // carteiras (InstancedMesh)
    const slots = deskSlots(room)
    const desks = new THREE.InstancedMesh(new THREE.BoxGeometry(0.9, 0.08, 0.55), this.mat(0xa47148), slots.length)
    slots.forEach(([x, , z], i) => {
      this.dummy.position.set(x, 0.75, z)
      this.dummy.scale.setScalar(1)
      this.dummy.updateMatrix()
      desks.setMatrixAt(i, this.dummy.matrix)
    })
    desks.castShadow = true
    this.scene.add(desks)
    // pessoas (InstancedMesh): quantidade vem do sensor de presença
    const people = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.18, 0.55, 3, 8), this.mat(0x3b82f6), slots.length)
    slots.forEach(([x, , z], i) => {
      this.dummy.position.set(x, 0.6, z + 0.45)
      this.dummy.updateMatrix()
      people.setMatrixAt(i, this.dummy.matrix)
    })
    people.count = 0
    this.scene.add(people)
    // névoa de CO₂
    const haze = new THREE.Mesh(new THREE.BoxGeometry(ROOM_W - 0.2, WALL_H - 0.2, ROOM_D - 0.3),
      new THREE.MeshBasicMaterial({ color: 0x9c9a6b, transparent: true, opacity: 0, depthWrite: false }))
    haze.position.set(cx, WALL_H / 2, 0)
    this.scene.add(haze)
    this.roomFx[room] = { haze, people, floor: floorMat }

    // sensores na parede
    for (const prefix of ['temp', 'umid', 'lum', 'co2', 'pres']) {
      const id = `${prefix}-${n}`
      const p = itemPosition(id)!
      const g = new THREE.Group()
      g.position.set(...p)
      const body = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.36, 0.12), this.mat(0xffffff))
      if (prefix === 'pres') body.rotation.y = Math.PI / 2
      const led = new THREE.Mesh(new THREE.SphereGeometry(0.09, 12, 8), new THREE.MeshStandardMaterial({ color: 0x94a3b8, emissive: 0x94a3b8, emissiveIntensity: 0.8 }))
      led.position.set(prefix === 'pres' ? 0.1 : 0, 0, prefix === 'pres' ? 0 : 0.1)
      g.add(body, led)
      this.register(id, g, [led])
    }

    // ventilador de teto (atuador automático por regra)
    {
      const id = `vent-${n}`
      const g = new THREE.Group()
      g.position.set(...itemPosition(id)!)
      const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.3), this.mat(0x555555))
      rod.position.y = 0.12
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.12, 16), this.mat(0x94a3b8))
      const blades = new THREE.Group()
      for (let i = 0; i < 4; i++) {
        const b = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.03, 0.2), this.mat(0xf1f5f9))
        b.position.x = 0.62
        const arm = new THREE.Group()
        arm.rotation.y = (i * Math.PI) / 2
        arm.add(b)
        blades.add(arm)
      }
      g.add(rod, hub, blades)
      let speed = 0
      this.register(id, g, [hub], (dt, _t, live) => {
        const target = live && this.data.state(id) ? 9 : 0
        speed += (target - speed) * Math.min(1, dt * 2)
        blades.rotation.y += speed * dt
      })
    }

    // luminária (controlada pela Web)
    {
      const id = `luz-${n}`
      const g = new THREE.Group()
      g.position.set(...itemPosition(id)!)
      const lampMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff3c4, emissiveIntensity: 0 })
      const panel = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.06, 0.8), lampMat)
      const frame = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.04, 0.9), this.mat(0x94a3b8))
      frame.position.y = 0.03
      const light = new THREE.PointLight(0xfff1c1, 0, 9, 1.5)
      light.position.y = -0.4
      g.add(panel, frame, light)
      this.register(id, g, [frame], (_dt, _t, live) => {
        const on = live && this.data.state(id)
        lampMat.emissiveIntensity += ((on ? 1.4 : 0) - lampMat.emissiveIntensity) * 0.15
        light.intensity = lampMat.emissiveIntensity * 6
      })
    }

    // sinalização / alarme (acionado pelo alerta crítico da IA)
    {
      const id = `alarme-${n}`
      const g = new THREE.Group()
      g.position.set(...itemPosition(id)!)
      const base = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.25, 0.25), this.mat(0x334155))
      const domeMat = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, emissive: 0xff0000, emissiveIntensity: 0, transparent: true, opacity: 0.9 })
      const dome = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2), domeMat)
      dome.rotation.z = Math.PI / 2
      dome.position.x = -0.06
      const beam = new THREE.SpotLight(0xff2222, 0, 6, 0.5, 0.5)
      beam.position.set(-0.1, 0, 0)
      g.add(base, dome, beam, beam.target)
      this.register(id, g, [base], (_dt, t, live) => {
        const on = live && this.data.state(id)
        domeMat.emissiveIntensity = on ? 1 + Math.sin(t * 12) : 0
        beam.intensity = on ? 30 : 0
        beam.target.position.set(-2, -1 + Math.sin(t * 6), Math.cos(t * 6) * 2)
      })
    }

    // ar-condicionado: evaporadora (interna) + condensadora (externa, monitorada) + tubulação
    {
      const id = `ac-${n}`
      const ip = itemPosition(id)!
      const indoor = new THREE.Group()
      indoor.position.set(...ip)
      const body = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.45, 0.3), this.mat(0xf8fafc))
      const strip = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.05, 0.02), new THREE.MeshStandardMaterial({ color: 0x94a3b8, emissive: 0x94a3b8, emissiveIntensity: 0.8 }))
      strip.position.set(0, -0.12, 0.16)
      indoor.add(body, strip)
      // fluxo de ar (partículas simples)
      const flow = new THREE.Group()
      const flowMat = new THREE.MeshBasicMaterial({ color: 0xbfe9ff, transparent: true, opacity: 0.6 })
      for (let i = 0; i < 8; i++) {
        const p = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.02, 0.08), flowMat)
        p.position.set(-0.55 + (i % 4) * 0.37, -0.3, 0.25 + Math.floor(i / 4) * 0.2)
        p.userData.phase = i / 8
        flow.add(p)
      }
      indoor.add(flow)
      this.register(id, indoor, [strip], (_dt, t, live) => {
        const eq = this.data.equipment(id)
        const running = live && !!eq?.running
        flow.visible = running
        if (running) flow.children.forEach((p) => {
          const k = (t * 0.7 + (p.userData.phase as number)) % 1
          p.position.y = -0.3 - k * 1.2
          p.position.z = 0.25 + k * 0.8
        })
      })

      const cp = condenserPosition(room)
      const outdoor = new THREE.Group()
      outdoor.position.set(...cp)
      const caseMat = this.mat(0xd1d5db, { metalness: 0.3, roughness: 0.5 })
      const cbody = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.0, 0.6), caseMat)
      const grille = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.04, 24), this.mat(0x334155))
      grille.rotation.x = Math.PI / 2
      grille.position.set(-0.15, 0, -0.31)
      const fan = new THREE.Group()
      for (let i = 0; i < 3; i++) {
        const b = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.1, 0.02), this.mat(0x111827))
        b.rotation.z = (i * Math.PI * 2) / 3
        fan.add(b)
      }
      fan.position.set(-0.15, 0, -0.34)
      const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 8), new THREE.MeshStandardMaterial({ color: 0x94a3b8, emissive: 0x94a3b8, emissiveIntensity: 1 }))
      lamp.position.set(0.45, 0.38, 0.31)
      const pad = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.08, 0.9), this.mat(0x9ca3af))
      pad.position.y = -0.54
      outdoor.add(cbody, grille, fan, lamp, pad)
      const shell = new THREE.Group()
      shell.add(outdoor)
      let fanSpeed = 0
      this.register(id, shell, [lamp], (dt, t, live) => {
        const eq = this.data.equipment(id)
        const running = live && !!eq?.running
        fanSpeed += ((running ? 14 : 0) - fanSpeed) * Math.min(1, dt * 2)
        fan.rotation.z += fanSpeed * dt
        // tremor proporcional à vibração medida
        const vib = typeof eq?.vibration === 'number' ? eq.vibration : 0
        const amp = running ? Math.min(0.12, Math.max(0, vib - 1.2) * 0.018) : 0
        outdoor.position.set(cp[0] + Math.sin(t * 53) * amp, cp[1] + Math.abs(Math.sin(t * 41)) * amp * 0.5,
          cp[2] + Math.cos(t * 47) * amp)
        const st = this.data.status(id)
        caseMat.color.setHex(st === 'critico' ? 0xfca5a5 : st === 'atencao' ? 0xfde68a : 0xd1d5db)
      })

      // tubulação: sai exatamente das conexões da evaporadora e chega nas da condensadora
      for (const [k, color] of [[0, 0xb87333], [1, 0x9ca3af]] as Array<[number, number]>) {
        const a = new THREE.Vector3(ip[0] + 0.45 + k * 0.15, ip[1] - 0.05, ip[2] - 0.15)        // traseira da evaporadora
        const b = new THREE.Vector3(cp[0] + 0.3 + k * 0.15, cp[1] + 0.2, cp[2] + 0.3)          // frente da condensadora
        const curve = new THREE.CatmullRomCurve3([
          a,
          new THREE.Vector3(a.x, a.y, BACK_Z - 0.6),
          new THREE.Vector3(a.x, b.y + 0.6, (BACK_Z - 0.6 + CONDENSER_Z + 0.3) / 2 - 0.2),
          new THREE.Vector3(b.x, b.y, b.z + 0.25),
          b,
        ])
        const pipe = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, 0.045, 8, false), this.mat(color, { metalness: 0.6, roughness: 0.35 }))
        pipe.castShadow = true
        this.scene.add(pipe)
        for (const end of [a, b]) {
          const cap = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 8), this.mat(0x6b7280))
          cap.position.copy(end)
          this.scene.add(cap)
        }
      }
    }
  }

  private buildStation() {
    const [x, , z] = STATION
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 3.2, 8), this.mat(0x6b7280))
    pole.position.set(x, 1.6, z)
    this.scene.add(pole)
    this.label('estação externa', [x, 4, z], 1.2)
    for (const id of ['temp-ext', 'lum-ext']) {
      const g = new THREE.Group()
      g.position.set(...itemPosition(id)!)
      const body = id === 'lum-ext'
        ? new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.04, 0.4), this.mat(0x1e3a8a, { metalness: 0.4 }))
        : new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 0.4, 10), this.mat(0xffffff))
      const led = new THREE.Mesh(new THREE.SphereGeometry(0.08, 10, 8), new THREE.MeshStandardMaterial({ color: 0x94a3b8, emissive: 0x94a3b8, emissiveIntensity: 0.8 }))
      led.position.set(0.25, 0.05, 0)
      g.add(body, led)
      this.register(id, g, [led])
    }
  }

  // --------------------------------------------------------------------- loop
  private loop = () => {
    this.raf = requestAnimationFrame(this.loop)
    const dt = Math.min(this.clock.getDelta(), 0.1)
    const t = this.clock.elapsedTime
    const live = this.data.hasData()
    for (const list of this.items.values()) {
      for (const item of list) {
        const st = this.data.status(item.id)
        if (st !== item.lastStatus) {
          item.lastStatus = st
          for (const m of item.status) {
            const mat = m.material as THREE.MeshStandardMaterial
            mat.color.setHex(STATUS_HEX[st])
            if ('emissive' in mat) mat.emissive.setHex(STATUS_HEX[st])
          }
        }
        if (live) item.animate?.(dt, t, live)
        else item.animate?.(0, t, false)
      }
    }
    if (live) this.updateEnvironment()
    this.controls.update()
    this.renderer.render(this.scene, this.camera)
  }

  private updateEnvironment() {
    // dia/noite pela luminosidade externa
    const lux = this.data.value('lum-ext') ?? 30000
    const day = Math.min(1, Math.max(0, lux / 40000))
    this.bg.copy(this.nightColor).lerp(this.dayColor, day)
    this.fog.color.copy(this.bg)
    this.hemi.intensity = 0.25 + 0.75 * day
    this.sun.intensity = 0.1 + 1.6 * day
    const elev = Math.asin(Math.min(1, day)) || 0.05
    this.sunMesh.position.set(-60 * Math.cos(elev), 5 + 60 * Math.sin(elev), -50)
    this.sunMesh.visible = day > 0.02
    ;(this.stars.material as THREE.PointsMaterial).opacity = Math.max(0, 1 - day * 3)
    for (const [room, fx] of Object.entries(this.roomFx)) {
      const n = roomNumber(room)
      // névoa proporcional ao CO₂
      const co2 = this.data.value(`co2-${n}`) ?? 450
      const target = Math.min(0.38, Math.max(0, (co2 - 600) / 1800) * 0.38)
      const hm = fx.haze.material as THREE.MeshBasicMaterial
      hm.opacity += (target - hm.opacity) * 0.05
      // ocupação pela presença
      const pres = Math.round(this.data.value(`pres-${n}`) ?? 0)
      const count = Math.min(fx.people.instanceMatrix.count, Math.max(0, Math.round(pres * 20 / 30)))
      if (fx.people.count !== count) fx.people.count = count
      // piso mais claro com mais luz interna; levemente avermelhado com calor
      const lumIn = this.data.value(`lum-${n}`) ?? 300
      const temp = this.data.value(`temp-${n}`) ?? 24
      const k = Math.min(1, lumIn / 700)
      const heat = Math.min(1, Math.max(0, (temp - 26) / 6))
      fx.floor.color.setRGB(0.45 + 0.4 * k + 0.1 * heat, 0.45 + 0.38 * k - 0.05 * heat, 0.42 + 0.36 * k - 0.1 * heat)
    }
  }

  // --------------------------------------------------------------- interação
  private onDown = (e: PointerEvent) => { this.downAt = [e.clientX, e.clientY] }
  private onUp = (e: PointerEvent) => {
    if (!this.downAt) return
    const moved = Math.hypot(e.clientX - this.downAt[0], e.clientY - this.downAt[1])
    this.downAt = null
    if (moved > 5) return
    const rect = this.renderer.domElement.getBoundingClientRect()
    const ndc = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1)
    const ray = new THREE.Raycaster()
    ray.setFromCamera(ndc, this.camera)
    const hit = ray.intersectObjects(this.pickables, true)[0]
    const id = (hit?.object.userData.deviceId as string | undefined) ?? null
    this.select(id)
    this.onPick(id)
  }

  select(id: string | null) {
    if (!id) {
      this.highlight.visible = false
      return
    }
    const item = this.items.get(id)?.[0]
    if (!item) return
    const p = new THREE.Vector3()
    item.root.getWorldPosition(p)
    if (item.root.children[0] && item.root.children[0].type === 'Group') item.root.children[0].getWorldPosition(p)
    this.highlight.position.set(p.x, p.y + 0.6, p.z)
    this.highlight.lookAt(this.camera.position)
    this.highlight.visible = true
  }

  private resize() {
    const w = this.container.clientWidth || 800
    const h = this.container.clientHeight || 500
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(w, h)
  }

  dispose() {
    cancelAnimationFrame(this.raf)
    this.ro.disconnect()
    const el = this.renderer.domElement
    el.removeEventListener('pointerdown', this.onDown)
    el.removeEventListener('pointerup', this.onUp)
    this.controls.dispose()
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh
      m.geometry?.dispose?.()
      const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : []
      mats.forEach((mm) => { (mm as THREE.MeshBasicMaterial).map?.dispose(); mm.dispose() })
    })
    this.renderer.dispose()
    el.remove()
  }
}
