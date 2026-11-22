## O que muda e por quê

<!-- Resuma a mudança e o motivo. Título do PR no formato: tipo(escopo): descrição — ex.: feat(api): adiciona rota de alertas -->

## Tipo

- [ ] feat (nova funcionalidade)
- [ ] fix (correção)
- [ ] refactor / perf
- [ ] docs / ci / chore / test

## Como testar

<!-- Passos ou comandos. Ex.: docker compose up -d --build; abrir http://localhost:8080 -->

## Checklist

- [ ] A branch parte de `develop` (feature/fix) ou de `main` (hotfix)
- [ ] `pytest` (backend) e `npm run type-check` / `npm run build` (frontend) passam
- [ ] Nenhum segredo, `.env` ou `credenciais-demo.txt` foi adicionado
- [ ] Documentação/README atualizados, se aplicável
- [ ] Se mexeu no Compose: validei `dev` e `prod` com `docker compose ... config -q`

Closes #
