<script setup lang="ts">
withDefaults(defineProps<{ message?: string }>(), {
  message: 'Carregando...',
})
</script>

<template>
  <div class="loading-state">
    <span class="loading-state__spinner" aria-hidden="true" />
    <p>{{ message }}</p>
  </div>
</template>

<style scoped>
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2.5rem 1rem;
  color: var(--color-text-muted);
}

.loading-state__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: loading-state-spin 0.8s linear infinite;
}

@keyframes loading-state-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
