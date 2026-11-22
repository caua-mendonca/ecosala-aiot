# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- Git Flow (`main`/`develop`), CI (pytest, type-check, build, Compose, gitleaks, smoke test) e CD para o GHCR.
- Ambientes `dev` e `prod` via `docker-compose.dev.yml` e `docker-compose.prod.yml`.
- Templates de PR e issues, CODEOWNERS, Dependabot e guias de contribuição e ambientes.

### Corrigido
- Erro de tipo no `TrainingView.vue` que quebrava o `vue-tsc`.

## [2.0.0] — 2º bimestre

### Adicionado
- EcoSala AIoT: simulador → MQTT → RabbitMQ → InfluxDB/PostgreSQL, API FastAPI, dashboard Vue 3 + Three.js,
  gerador de dados sintéticos, modelos de regressão, insights preditivos e assistente com LLM local.
