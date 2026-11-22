<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push(typeof route.query.next === 'string' ? route.query.next : '/')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <form class="login card" @submit.prevent="submit">
    <div class="brand-row">
      <img src="/favicon.svg" alt="" width="40" height="40" />
      <div>
        <h1>EcoSala AIoT</h1>
        <small>Conforto em salas de aula + manutenção preditiva</small>
      </div>
    </div>
    <label class="field">Usuário<input v-model="username" autocomplete="username" required /></label>
    <label class="field">Senha<input v-model="password" type="password" autocomplete="current-password" required /></label>
    <button class="btn" :disabled="loading">{{ loading ? 'Entrando…' : 'Entrar' }}</button>
    <p v-if="error" class="error">{{ error }}</p>
    <small>Papéis: <b>visualizador</b> só vê · <b>operador</b> comanda atuadores e simulador · <b>administrador</b> também gera dados, treina modelos e vê a auditoria.</small>
  </form>
</template>

<style scoped>
.login { width: min(380px, 92vw); display: flex; flex-direction: column; gap: .8rem; padding: 1.5rem; }
.brand-row { display: flex; gap: .8rem; align-items: center; }
</style>
