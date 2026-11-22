import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, api, getToken, setToken } from '../api'

export type Role = 'viewer' | 'operator' | 'admin'
const LEVEL: Record<Role, number> = { viewer: 1, operator: 2, admin: 3 }

export const useAuth = defineStore('auth', () => {
  const username = ref<string | null>(null)
  const role = ref<Role | null>(null)
  const roleLabel = ref('')
  const token = ref<string | null>(getToken())

  const isLogged = computed(() => !!token.value && !!role.value)
  const can = (r: Role) => !!role.value && LEVEL[role.value] >= LEVEL[r]

  async function login(user: string, password: string) {
    const r = await api<{ access_token: string; username: string; role: Role; role_label: string }>(
      '/auth/login', { method: 'POST', json: { username: user, password } })
    setToken(r.access_token)
    token.value = r.access_token
    username.value = r.username
    role.value = r.role
    roleLabel.value = r.role_label
  }

  async function restore(): Promise<boolean> {
    if (!token.value) return false
    try {
      const me = await api<{ username: string; role: Role; role_label: string }>('/auth/me')
      username.value = me.username
      role.value = me.role
      roleLabel.value = me.role_label
      return true
    } catch (e) {
      // só desloga se o token for realmente inválido (401); falha de rede mantém a sessão
      if (e instanceof ApiError && e.status === 401) logout()
      return false
    }
  }

  function logout() {
    setToken(null)
    token.value = null
    username.value = null
    role.value = null
  }

  return { username, role, roleLabel, token, isLogged, can, login, restore, logout }
})
