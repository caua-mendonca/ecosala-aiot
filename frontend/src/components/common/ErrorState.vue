<script setup lang="ts">
defineProps<{ message: string }>()
const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="error-state">
    <p>{{ message }}</p>
    <button type="button" class="error-state__retry" @click="emit('retry')">
      Tentar novamente
    </button>
  </div>
</template>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2.5rem 1rem;
  color: var(--color-danger);
  text-align: center;
}

.error-state__retry {
  border: 1px solid var(--color-danger);
  background: transparent;
  color: var(--color-danger);
  border-radius: 8px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font: inherit;
}

.error-state__retry:hover {
  background: var(--color-danger);
  color: white;
}
</style>
