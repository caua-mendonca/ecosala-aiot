# Como contribuir

## Git Flow

| Branch | Papel | Ambiente | Quem escreve |
|---|---|---|---|
| `main` | Produção. Cada commit é uma versão (tag `vX.Y.Z`) | `production` | só por PR de `release/*` ou `hotfix/*` |
| `develop` | Integração. Última versão em desenvolvimento | `dev` | só por PR de `feature/*`, `fix/*` |
| `feature/<tema>` | Nova funcionalidade (sai de `develop`) | — | quem desenvolve |
| `fix/<tema>` | Correção não urgente (sai de `develop`) | — | quem corrige |
| `release/<X.Y.Z>` | Estabilização antes de publicar (sai de `develop`) | — | responsável pela release |
| `hotfix/<tema>` | Correção urgente em produção (sai de `main`) | — | quem corrige |

`main` e `develop` são protegidas: não há push direto, tudo entra por Pull Request com CI verde.

### Fluxo do dia a dia

```bash
git switch develop && git pull
git switch -c feature/alertas-por-sala
# ... commits pequenos ...
git push -u origin feature/alertas-por-sala
# abrir PR para develop (título: feat(api): alertas por sala) e pedir revisão
```

Faça **squash merge** de feature/fix em `develop` (histórico limpo, um commit por PR).

### Release

```bash
git switch develop && git pull
git switch -c release/2.1.0
# ajustar versão e CHANGELOG.md; só correções nesta branch
# PR release/2.1.0 -> main  (merge commit)
git switch main && git pull
git tag -a v2.1.0 -m "v2.1.0" && git push origin v2.1.0   # dispara o CD de produção
# PR release/2.1.0 -> develop  (traz as correções de volta)
```

### Hotfix

```bash
git switch main && git pull
git switch -c hotfix/login-quebrado
# corrigir, PR -> main, tag vX.Y.Z+1, e PR/merge de volta em develop
```

## Commits e títulos de PR (Conventional Commits)

`tipo(escopo opcional): descrição no imperativo`

Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
O CI reprova PR com título fora desse padrão. Exemplos: `feat(frontend): painel 3D`, `fix(gateway): reconecta ao RabbitMQ`.

## Antes de abrir o PR

```bash
cd backend && python -m pytest
cd frontend && npm run type-check && npm run build
docker compose -f docker-compose.yml -f docker-compose.dev.yml config -q
```

## Regras de ouro

- Nunca commitar `.env`, `credenciais-demo.txt` ou qualquer senha (o CI roda `gitleaks`).
- Um PR = um assunto. Prefira PRs pequenos.
- Todo PR precisa de pelo menos 1 aprovação de outro integrante (veja `.github/CODEOWNERS`).

Ambientes e deploy: [docs/ambientes.md](docs/ambientes.md).
