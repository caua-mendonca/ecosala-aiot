<script setup lang="ts">
defineProps<{
  label: string
  value: string
  unit?: string
}>()
</script>

<template>
  <div class="metric-card">
    <span class="metric-card__label">{{ label }}</span>
    <span class="metric-card__value">
      {{ value }}<small v-if="unit" class="metric-card__unit">{{ unit }}</small>
    </span>
  </div>
</template>

<style scoped>
.metric-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.metric-card__label {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.metric-card__value {
  font-size: 1.5rem;
  font-weight: 700;
}

.metric-card__unit {
  font-size: 0.9rem;
  font-weight: 400;
  margin-left: 0.25rem;
  color: var(--color-text-muted);
}
</style>
