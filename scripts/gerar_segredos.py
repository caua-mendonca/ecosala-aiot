#!/usr/bin/env python3
"""Gera o arquivo .env com senhas e chaves aleatórias (rode UMA vez antes do docker compose up).

- Nenhuma senha fica no Git: .env e credenciais-demo.txt estão no .gitignore.
- Não existe usuário/senha padrão (nada de admin/admin): tudo é aleatório.
- Uso:  python scripts/gerar_segredos.py          (não sobrescreve um .env existente)
        python scripts/gerar_segredos.py --force  (gera tudo de novo; apague os volumes antes:
                                                   docker compose down -v)
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
CREDS = ROOT / "credenciais-demo.txt"


def pw(n: int = 18) -> str:
    return secrets.token_urlsafe(n)


def main() -> int:
    if ENV.exists() and "--force" not in sys.argv:
        print(f"{ENV} já existe; nada foi alterado (use --force para gerar de novo).")
        return 0
    demo = {"administrador": pw(9), "operador": pw(9), "visualizador": pw(9)}
    values = {
        "RABBITMQ_ADMIN_USER": "ecosala-admin",
        "RABBITMQ_ADMIN_PASSWORD": pw(),
        **{f"RABBITMQ_{s}_USER": f"svc-{s.lower()}" for s in ("GATEWAY", "WRITER", "INFERENCE", "WORKER", "API")},
        **{f"RABBITMQ_{s}_PASSWORD": pw() for s in ("GATEWAY", "WRITER", "INFERENCE", "WORKER", "API")},
        "POSTGRES_PASSWORD": pw(),
        "INFLUXDB_ADMIN_USER": "ecosala-admin",
        "INFLUXDB_ADMIN_PASSWORD": pw(),
        "INFLUXDB_TOKEN": secrets.token_hex(32),
        "MQTT_DEVICE_PASSWORD": pw(),
        "MQTT_GATEWAY_PASSWORD": pw(),
        "JWT_SECRET": secrets.token_hex(32),
        "DEMO_ADMIN_PASSWORD": demo["administrador"],
        "DEMO_OPERATOR_PASSWORD": demo["operador"],
        "DEMO_VIEWER_PASSWORD": demo["visualizador"],
        "PGADMIN_EMAIL": "admin@ecosala.com",
        "PGADMIN_PASSWORD": pw(),
        "OLLAMA_MODEL": "llama3.2:3b",
    }
    lines = ["# Gerado por scripts/gerar_segredos.py — NÃO versionar (está no .gitignore)"]
    lines += [f"{k}={v}" for k, v in values.items()]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    creds = [
        "EcoSala AIoT — credenciais de demonstração (NÃO versionar)",
        "",
        "Aplicação: http://localhost:8080",
        *[f"  {u:<14} senha: {p}" for u, p in demo.items()],
        "",
        f"RabbitMQ  http://127.0.0.1:15672  usuário {values['RABBITMQ_ADMIN_USER']}  senha {values['RABBITMQ_ADMIN_PASSWORD']}",
        f"InfluxDB  http://127.0.0.1:8086   usuário {values['INFLUXDB_ADMIN_USER']}  senha {values['INFLUXDB_ADMIN_PASSWORD']}",
        f"pgAdmin   http://127.0.0.1:5050   e-mail {values['PGADMIN_EMAIL']}  senha {values['PGADMIN_PASSWORD']}",
        f"          (senha do banco 'ecosala' no pgAdmin: {values['POSTGRES_PASSWORD']})",
    ]
    CREDS.write_text("\n".join(creds) + "\n", encoding="utf-8")
    print("\n".join(creds))
    print(f"\n.env criado em {ENV}\nCredenciais salvas em {CREDS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
