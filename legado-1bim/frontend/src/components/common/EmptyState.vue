<script setup lang="ts">
withDefaults(defineProps<{ message?: string }>(), {
  message: 'Nenhum dado encontrado.',
})
</script>

<template>
  <div class="empty-state">
    <p>{{ message }}</p>
  </div>
</template>

<style scoped>
.empty-state {
  padding: 2.5rem 1rem;
  text-align: center;
  color: var(--color-text-muted);
}
</style>
