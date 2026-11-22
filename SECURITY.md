# Segurança

- Segredos nunca vão para o Git: `.env` e `credenciais-demo.txt` estão no `.gitignore` e o CI roda `gitleaks`.
- Para relatar uma vulnerabilidade, **não** abra issue pública: use *Security → Report a vulnerability* do repositório.
- Produção expõe apenas o frontend; RabbitMQ, InfluxDB e pgAdmin ficam fechados (ou só em `127.0.0.1` em dev).
