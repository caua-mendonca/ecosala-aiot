<script setup lang="ts">
import { computed } from 'vue'
import type { ComfortStatus } from '@/domain/Reading'

const props = defineProps<{ status: ComfortStatus }>()

const STATUS_LABELS: Record<ComfortStatus, string> = {
  OK: 'OK',
  ATENCAO: 'Atenção',
  CRITICO: 'Crítico',
}

const label = computed(() => STATUS_LABELS[props.status])
const modifierClass = computed(() => `status-badge--${props.status.toLowerCase()}`)
</script>

<template>
  <span class="status-badge" :class="modifierClass" data-testid="status-badge">
    {{ label }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.85rem;
  white-space: nowrap;
}

.status-badge--ok {
  background: var(--color-status-ok-bg);
  color: var(--color-status-ok-text);
}

.status-badge--atencao {
  background: var(--color-status-atencao-bg);
  color: var(--color-status-atencao-text);
}

.status-badge--critico {
  background: var(--color-status-critico-bg);
  color: var(--color-status-critico-text);
}
</style>
