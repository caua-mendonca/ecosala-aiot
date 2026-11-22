<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <header class="app-shell__header">
      <span class="app-shell__brand">EcoSala</span>
      <nav class="app-shell__nav">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/historico">Histórico</RouterLink>
        <RouterLink to="/sobre">Sobre</RouterLink>
      </nav>
    </header>

    <main class="app-shell__content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--color-border);
  flex-wrap: wrap;
  gap: 0.75rem;
}

.app-shell__brand {
  font-weight: 700;
  font-size: 1.25rem;
  color: var(--color-primary);
}

.app-shell__nav {
  display: flex;
  gap: 1.25rem;
  flex-wrap: wrap;
}

.app-shell__nav a {
  color: var(--color-text-muted);
  text-decoration: none;
  font-weight: 500;
}

.app-shell__nav a.router-link-active {
  color: var(--color-primary);
}

.app-shell__content {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
}
</style>
