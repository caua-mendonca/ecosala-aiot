# Ambientes: dev e produção

Os dois ambientes usam o mesmo `docker-compose.yml` (base) mais um arquivo de sobreposição.
Cada um tem **nome de projeto próprio** (`ecosala-dev`, `ecosala-prod`), então volumes e dados são separados.
O fluxo original (`testar.bat` / `docker compose up -d --build`) continua funcionando e não muda.

| | dev | produção |
|---|---|---|
| Arquivo | `docker-compose.dev.yml` | `docker-compose.prod.yml` |
| Branch | `develop` | `main` (tag `vX.Y.Z`) |
| Imagens | build local | `ghcr.io/<dono>/ecosala-backend` e `ecosala-frontend` (tag versionada) |
| Código do backend | montado no container; API com `--reload` | embutido na imagem |
| Logs | `DEBUG` | `WARNING` |
| Portas no host | 8080 (app), 8000 (API), 1883 (MQTT), 5432 (Postgres), 15672, 8086, 5050 — tudo de depuração só em `127.0.0.1` | só o frontend (`FRONTEND_PORT`, padrão 80) |
| pgAdmin | ligado | desligado (`--profile tools` para ligar) |
| Reinício | `unless-stopped` | `always` |
| GitHub Environment | `dev` | `production` (com aprovação manual) |

## Dev

```bash
python scripts/gerar_segredos.py
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
cd frontend && npm install && npm run dev      # hot reload em http://localhost:5173
```

## Produção

```bash
python scripts/gerar_segredos.py               # uma vez, no servidor
export GHCR_OWNER=<dono-do-repo-em-minusculas> IMAGE_TAG=2.0.0
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --wait
```

Se o pacote no GHCR for privado, faça `docker login ghcr.io` antes (token com `read:packages`).
Rollback: suba de novo com o `IMAGE_TAG` anterior.

## Pipeline

- **CI** (`.github/workflows/ci.yml`, em todo PR e push para `develop`/`main`): título do PR, `gitleaks`, pytest, type-check e build do frontend, validação do Compose (base, dev, prod) e smoke test que sobe a pilha (sem o LLM) e chama `/api/v1/health`.
- **CD** (`.github/workflows/cd.yml`): push em `develop` publica `:dev` e `:sha-<commit>` (ambiente `dev`); tag `vX.Y.Z` publica `:X.Y.Z` e `:latest` e cria a GitHub Release (ambiente `production`, pede aprovação).

## Configuração única no GitHub (Settings)

1. **Environments**: criar `dev` e `production`; em `production`, ativar *Required reviewers* e limitar a tags `v*`.
2. **Branches** (ou *Rulesets*): proteger `main` e `develop` — exigir PR, 1 aprovação, status checks do CI e conversas resolvidas; bloquear force-push.
3. **Packages**: ao primeiro push, ligar os pacotes `ecosala-backend` e `ecosala-frontend` ao repositório.
