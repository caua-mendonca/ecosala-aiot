#!/usr/bin/env bash
# Publica o projeto no GitHub e monta o Git Flow: repositório, branches, Environments,
# proteção de branches e o primeiro PR. Idempotente: pode rodar de novo sem quebrar.
#
# Uso (Git Bash, na raiz do projeto):
#   bash scripts/github-setup.sh                      # cria <seu-login>/ecosala-aiot (privado)
#   REPO=meu-repo VISIBILITY=public bash scripts/github-setup.sh
#
# Pré-requisito: gh autenticado com escopos repo, workflow e read:org. A variável de ambiente
# GITHUB_TOKEN, se existir, sobrepõe o login do gh e é ignorada aqui (unset).
set -euo pipefail
cd "$(dirname "$0")/.."

unset GITHUB_TOKEN GH_TOKEN
REPO="${REPO:-ecosala-aiot}"
VISIBILITY="${VISIBILITY:-private}"      # private | public
FEATURE="feature/git-flow-ci-ambientes"

if ! gh auth status >/dev/null 2>&1; then
  echo ">> Faça login (escopos repo, workflow, read:org):"
  gh auth login -h github.com -s repo,workflow,read:org -w
fi
OWNER="${OWNER:-$(gh api user --jq .login)}"
SLUG="$OWNER/$REPO"
echo ">> Alvo: https://github.com/$SLUG ($VISIBILITY)"

# --- remotes: o antigo 'origin' (repositório do grupo) vira 'grupo' para não receber push sem querer
if git remote get-url origin 2>/dev/null | grep -qi "LuisBarbosaa/ecosala"; then
  git remote rename origin grupo
fi

# --- repositório
if ! gh repo view "$SLUG" >/dev/null 2>&1; then
  gh repo create "$SLUG" "--$VISIBILITY" --description "EcoSala AIoT — monitoramento e manutenção preditiva de salas (Vue 3, FastAPI, MQTT, RabbitMQ, IA)"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$SLUG.git"

# --- CODEOWNERS (dono do repositório revisa tudo; ajuste depois com os demais integrantes)
git switch -q "$FEATURE"
mkdir -p .github
if [ ! -f .github/CODEOWNERS ]; then
  printf '# Todo PR pede revisão destes donos. Acrescente os demais integrantes.\n* @%s\n' "$OWNER" > .github/CODEOWNERS
  git add .github/CODEOWNERS
  git commit -q -m "chore: adiciona CODEOWNERS" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
fi

# --- push das branches
git push -u origin main develop "$FEATURE"

# --- configurações do repositório: develop como padrão, squash, apagar branch após merge
gh repo edit "$SLUG" --default-branch develop --delete-branch-on-merge \
  --enable-squash-merge --enable-merge-commit --enable-rebase-merge=false
gh api -X PATCH "repos/$SLUG" -f allow_auto_merge=true >/dev/null || true

# --- Environments: dev (livre) e production (aprovação manual, só tags v*)
UID_NUM="$(gh api user --jq .id)"
gh api -X PUT "repos/$SLUG/environments/dev" >/dev/null
gh api -X PUT "repos/$SLUG/environments/production" --input - >/dev/null <<EOF || echo "!! Environment production: configure a aprovação manualmente (plano do repo)"
{"reviewers":[{"type":"User","id":$UID_NUM}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
EOF
gh api -X POST "repos/$SLUG/environments/production/deployment-branch-policies" -f name='v*' -f type=tag >/dev/null 2>&1 || true
gh api -X POST "repos/$SLUG/environments/dev/deployment-branch-policies" -f name='develop' -f type=branch >/dev/null 2>&1 || true

# --- proteção de main e develop (em repo privado exige plano pago; se falhar, só avisa)
CHECKS='["Título do PR (Conventional Commits)","Varredura de segredos","Backend (pytest)","Frontend (type-check e build)","Compose (dev e prod válidos)","Smoke test (sobe a pilha sem o LLM)"]'
for B in main develop; do
  gh api -X PUT "repos/$SLUG/branches/$B/protection" --input - >/dev/null <<EOF || echo "!! Não foi possível proteger '$B' (repo privado em plano gratuito? use repo público ou plano Pro)"
{
  "required_status_checks": {"strict": true, "contexts": $CHECKS},
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 1, "dismiss_stale_reviews": true, "require_code_owner_reviews": false},
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
EOF
done

# --- primeiro PR do fluxo: feature -> develop
if ! gh pr view "$FEATURE" --repo "$SLUG" >/dev/null 2>&1; then
  gh pr create --repo "$SLUG" --base develop --head "$FEATURE" \
    --title "ci: adiciona Git Flow, CI/CD e ambientes dev/prod" \
    --body "$(cat <<'EOF'
## O que muda e por quê
Estrutura o repositório: workflows de CI (pytest, type-check, build, Compose, gitleaks, smoke test) e CD (imagens no GHCR + Release), ambientes `dev` e `prod` via Compose, templates de PR/issues, Dependabot e guias (CONTRIBUTING, docs/ambientes).

## Como testar
`docker compose -f docker-compose.yml -f docker-compose.dev.yml config -q` e o mesmo com `docker-compose.prod.yml` (exige `GHCR_OWNER`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
fi

cat <<EOF

Pronto. Próximos passos:
  1. Espere o CI do PR ficar verde e faça o squash merge em develop (o CD publica :dev).
  2. Abra o PR develop -> main (release) e, depois do merge:  git tag -a v2.0.0 -m v2.0.0 && git push origin v2.0.0
  3. Convide os demais integrantes (Settings > Collaborators) e acrescente-os ao CODEOWNERS.
  4. Cada integrante deve commitar com o próprio usuário (git config user.name / user.email).
EOF
