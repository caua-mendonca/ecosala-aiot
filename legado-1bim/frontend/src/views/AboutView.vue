<script setup lang="ts">
import BaseCard from '@/components/common/BaseCard.vue'
</script>

<template>
  <section class="about-view">
    <h1>Sobre o EcoSala</h1>

    <BaseCard>
      <h2>O problema</h2>
      <p>
        Salas de aula com temperatura alta, umidade inadequada ou pouca iluminação reduzem a
        concentração e o rendimento dos alunos. Hoje a instituição não possui dados objetivos para
        saber quais salas apresentam problemas, em quais horários e com que frequência.
      </p>
    </BaseCard>

    <BaseCard>
      <h2>A solução</h2>
      <p>
        Um ESP32 instalado em cada sala mede temperatura e umidade (DHT22) e luminosidade
        (fotoresistor) e publica as leituras via MQTT. Um backend em Python consome as mensagens,
        valida os dados, classifica o nível de conforto (OK, Atenção ou Crítico) e grava tudo no
        InfluxDB. Este dashboard exibe os valores atuais de cada sala e o histórico em gráficos.
      </p>
    </BaseCard>

    <BaseCard>
      <h2>Fluxo de dados</h2>
      <div class="about-view__flow">
        <span class="about-view__flow-step">ESP32 (Wokwi)</span>
        <span class="about-view__flow-arrow">→</span>
        <span class="about-view__flow-step">MQTT / Mosquitto</span>
        <span class="about-view__flow-arrow">→</span>
        <span class="about-view__flow-step">Backend Python</span>
        <span class="about-view__flow-arrow">→</span>
        <span class="about-view__flow-step">InfluxDB</span>
        <span class="about-view__flow-arrow">→</span>
        <span class="about-view__flow-step">API REST</span>
        <span class="about-view__flow-arrow">→</span>
        <span class="about-view__flow-step">Dashboard (Vue)</span>
      </div>
    </BaseCard>

    <BaseCard>
      <h2>Faixas de conforto (padrão, configuráveis)</h2>
      <ul class="about-view__list">
        <li>Temperatura ideal: 20 °C a 26 °C</li>
        <li>Umidade ideal: 40% a 60%</li>
        <li>Luminosidade mínima: 300 lux</li>
      </ul>
      <p class="about-view__note">
        Os valores exatos usados no momento podem ser consultados em
        <code>/api/v1/comfort/thresholds</code>.
      </p>
    </BaseCard>
  </section>
</template>

<style scoped>
.about-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.about-view h2 {
  margin-bottom: 0.5rem;
}

.about-view__flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.about-view__flow-step {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  padding: 0.5rem 0.85rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.85rem;
}

.about-view__flow-arrow {
  color: var(--color-text-muted);
}

.about-view__list {
  padding-left: 1.25rem;
}

.about-view__note {
  margin-top: 0.75rem;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}
</style>
