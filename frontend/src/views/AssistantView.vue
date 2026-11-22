<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { api, streamNdjson } from '../api'
import { renderMarkdown } from '../utils/markdown'

interface Msg { role: 'user' | 'assistant'; content: string; status?: string; error?: boolean }
const messages = ref<Msg[]>([])
const question = ref('')
const busy = ref(false)
const status = ref<{ model: string; reachable: boolean; pulled: boolean; loaded: boolean } | null>(null)
const box = ref<HTMLElement | null>(null)
const context = ref('')
const showContext = ref(false)
const suggestions = [
  'Qual equipamento está com a pior saúde e o que devo fazer?',
  'O que significa o alerta aberto agora?',
  'Explique as métricas do último treino em palavras simples.',
  'Como os dados fluem pela arquitetura e por que usamos RabbitMQ?',
  'Quais as últimas leituras da sala-101?',
]

async function loadStatus() { try { status.value = await api('/assistant/status') } catch { /* */ } }
onMounted(() => { void loadStatus(); window.setInterval(loadStatus, 10000) })

async function ask(q?: string) {
  const text = (q ?? question.value).trim()
  if (!text || busy.value) return
  question.value = ''
  const history = messages.value.filter((m) => !m.error).map(({ role, content }) => ({ role, content }))
  messages.value.push({ role: 'user', content: text })
  const answer = ref<Msg>({ role: 'assistant', content: '', status: 'enviando…' })
  messages.value.push(answer.value)
  const a = messages.value[messages.value.length - 1]
  busy.value = true
  try {
    await streamNdjson('/assistant/chat', { question: text, history }, (o) => {
      if (o.t === 'status') a.status = o.v === 'carregando o modelo' && !status.value?.loaded ? 'carregando o modelo na memória (a 1ª resposta em CPU demora)…' : o.v
      else if (o.t === 'token') { a.status = ''; a.content += o.v }
      else if (o.t === 'error') { a.error = true; a.content = o.v }
      else if (o.t === 'done') a.status = ''
      void nextTick(() => box.value?.scrollTo({ top: box.value.scrollHeight }))
    })
  } catch (e) {
    a.error = true
    a.content = (e as Error).message
  } finally {
    a.status = ''
    busy.value = false
    void loadStatus()
  }
}
async function toggleContext() {
  showContext.value = !showContext.value
  if (showContext.value) context.value = (await api<{ context: string }>('/assistant/context')).context
}
</script>

<template>
  <div class="stack">
    <div class="card row">
      <b>LLM local:</b> <span class="mono">{{ status?.model ?? '…' }}</span>
      <span class="pill" :class="status?.loaded ? 'normal' : status?.pulled ? 'atencao' : 'nodata'">
        {{ !status?.reachable ? 'Ollama indisponível' : status.loaded ? 'modelo carregado' : status.pulled ? 'baixado (carrega na 1ª pergunta)' : 'baixando o modelo…' }}</span>
      <small>Roda no Ollama dentro do Docker Compose, em CPU, sem nuvem e sem chave de API. O backend envia um resumo dos dados atuais junto com a pergunta.</small>
      <span class="spacer" /><button class="btn small ghost" @click="toggleContext">{{ showContext ? 'Ocultar' : 'Ver' }} resumo enviado ao LLM</button>
    </div>
    <pre v-if="showContext">{{ context }}</pre>
    <div ref="box" class="card chat">
      <p v-if="!messages.length" class="muted">Pergunte sobre o estado atual, as previsões da IA, os modelos ou a arquitetura.</p>
      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
        <div v-if="m.role === 'user'">{{ m.content }}</div>
        <div v-else>
          <div v-if="m.status" class="muted">⏳ {{ m.status }}</div>
          <div v-if="m.error" class="error">{{ m.content }}</div>
          <div v-else class="md" v-html="renderMarkdown(m.content)" />
        </div>
      </div>
    </div>
    <div class="row">
      <button v-for="s in suggestions" :key="s" class="btn small ghost" :disabled="busy" @click="ask(s)">{{ s }}</button>
    </div>
    <form class="row" @submit.prevent="ask()">
      <input v-model="question" placeholder="Digite sua pergunta…" maxlength="1000" style="flex:1" :disabled="busy" />
      <button class="btn" :disabled="busy || !question.trim()">Perguntar</button>
    </form>
  </div>
</template>

<style scoped>
.chat { height: 52vh; overflow-y: auto; display: flex; flex-direction: column; gap: .6rem; }
.msg { max-width: 80%; padding: .55rem .8rem; border-radius: 10px; }
.msg.user { align-self: flex-end; background: var(--brand); color: #fff; }
.msg.assistant { align-self: flex-start; background: #f1f5f4; }
</style>
