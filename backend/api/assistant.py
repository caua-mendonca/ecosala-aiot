"""Assistente com LLM local (Ollama, dentro do Docker Compose).

O backend monta um RESUMO dos dados atuais e o envia pronto no prompt, junto
com a pergunta. O LLM nunca acessa bancos ou ferramentas. A resposta é
devolvida em streaming (NDJSON) e tratada como texto não confiável no frontend.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from . import db, live, settings

log = logging.getLogger("api.assistant")

ARCHITECTURE = """\
Arquitetura do EcoSala AIoT (Smart Campus, conforto em salas de aula + manutenção preditiva dos ar-condicionados):
- Simulador Python (substitui o ESP32) publica telemetria via MQTT no Mosquitto e recebe comandos (bidirecional).
- Gateway lê o MQTT e republica no RabbitMQ (exchange topic ecosala.telemetry, routing key telemetry.<sala>.<tipo>.<id>).
- RabbitMQ é o barramento interno: filas q.influx (gravador no InfluxDB), q.inference (IA), q.websocket (interface),
  q.commands (comandos de volta ao dispositivo), q.rules (regras de negócio), q.persist (alertas/jobs no PostgreSQL),
  q.jobs.generate e q.jobs.train (jobs demorados) e q.dlq (mensagens mortas).
- InfluxDB guarda leituras e telemetria (séries temporais); PostgreSQL guarda usuários, dispositivos, configurações,
  regras, alertas, jobs, versões de modelo e auditoria.
- IA: gerador de dados sintéticos massivos (numpy) + 2 modelos de regressão (scikit-learn HistGradientBoosting):
  vida útil restante (RUL, horas) e índice de saúde (0-100), treinados com divisão por equipamento e comparados com
  a base simples (prever a média). A inferência roda em tempo real e publica previsões e alertas com histerese.
- FastAPI expõe a API REST e o WebSocket; o frontend Vue 3 + TypeScript mostra dashboard, gêmeo digital 3D
  (Three.js), insights, laboratório, treinamento, mensageria e este assistente (LLM local no Ollama, sem nuvem).
- Tempo simulado: cada leitura representa 10 minutos; por isso as horas de vida útil são em tempo simulado.
"""

SYSTEM = """Você é o assistente do EcoSala AIoT. Responda SEMPRE em português do Brasil, de forma curta,
clara e prática (no máximo ~8 frases ou uma lista curta). Use SOMENTE os dados do RESUMO abaixo; se a resposta
não estiver nos dados, diga que não sabe. Nunca invente números. Explique termos técnicos em palavras simples.
Quando falar de alertas, diga o que significam e o que fazer (ex.: agendar manutenção, verificar filtro,
rolamento ou ventilação do condensador). Não escreva HTML nem imagens."""

FAULT_HINTS = {
    "vibration": "vibração alta costuma indicar rolamento gasto ou desbalanceamento do ventilador/compressor",
    "temperature": "temperatura de descarga alta indica superaquecimento (condensador sujo, falta de gás, ventilação ruim)",
    "current": "corrente alta indica esforço do compressor (filtro entupido, obstrução, problema elétrico)",
}


def build_context() -> str:
    s = live.state
    lines = ["RESUMO DOS DADOS ATUAIS (gerado pelo backend):"]
    age = s.snapshot()["last_telemetry_age_s"]
    lines.append(f"- Última telemetria recebida há {age} s." if age is not None else "- Ainda sem telemetria.")
    rooms: dict[str, list[str]] = {}
    for dev, msg in sorted(s.latest.items()):
        p = msg["payload"]
        room = msg.get("room") or "?"
        if p.get("kind") == "sensor":
            rooms.setdefault(room, []).append(f"{p.get('sensor_type')}({dev})={p.get('value')}")
        elif p.get("kind") == "actuator":
            rooms.setdefault(room, []).append(f"{dev}={'ligado' if p.get('state') else 'desligado'}")
        elif p.get("kind") == "equipment":
            rooms.setdefault(room, []).append(
                f"{dev}: vibração={p.get('vibration')} mm/s, corrente={p.get('current')} A, "
                f"temp. descarga={p.get('temperature')} °C, ligado={p.get('running')}, quebrado={p.get('failed')}")
    for room, items in rooms.items():
        lines.append(f"- Sala {room}: " + "; ".join(items))
    preds = sorted(s.predictions.values(), key=lambda m: m["payload"].get("health", 100))
    if preds:
        lines.append("- Previsões da IA (pior saúde primeiro):")
        for m in preds:
            p = m["payload"]
            rul = "acima de 168 h (sem sinal de falha)" if p.get("rul_capped") else f"{p.get('rul_h')} h"
            lines.append(f"  * {m['device']} ({m.get('room')}): saúde {p.get('health')}/100, vida útil restante {rul}, "
                         f"tendência {p.get('trend')} pontos/leitura, estado {p.get('status')}, modelo v{p.get('model_version')}")
    else:
        lines.append("- Ainda não há previsões da IA (modelo não treinado ou sem dados).")
    try:
        alerts = db.query("SELECT device, kind, severity, message, opened_at FROM alerts WHERE state='open' "
                          "ORDER BY opened_at DESC LIMIT 10")
        lines.append(f"- Alertas abertos: {len(alerts)}")
        for a in alerts:
            lines.append(f"  * {a['device']}: {a['message']} (severidade {a['severity']}, desde {a['opened_at']:%d/%m %H:%M})")
        model = db.one("SELECT version, result FROM model_versions WHERE active ORDER BY version DESC LIMIT 1")
        if model:
            lines.append(f"- Modelo em uso: versão {model['version']}. Métricas no conjunto de teste:")
            for name, t in (model["result"].get("targets") or {}).items():
                m, b = t["metrics"].get("test", {}), t["baseline"].get("test", {})
                lines.append(f"  * {t['label']}: MAE={m.get('mae', 0):.2f}, RMSE={m.get('rmse', 0):.2f}, "
                             f"R²={m.get('r2', 0):.2f}; base simples MAE={b.get('mae', 0):.2f}, R²={b.get('r2', 0):.2f}; "
                             f"vence a base: {'sim' if t.get('beats_baseline') else 'não'}; atributos mais importantes: "
                             + ", ".join(f[0] for f in t.get("feature_importance", [])[:4]))
    except Exception:  # noqa: BLE001
        log.exception("falha ao montar contexto do banco")
    lines.append("- Dicas de diagnóstico: " + "; ".join(FAULT_HINTS.values()) + ".")
    lines.append(ARCHITECTURE)
    return "\n".join(lines)


async def status() -> dict[str, Any]:
    out = {"model": settings.OLLAMA_MODEL, "reachable": False, "pulled": False, "loaded": False}
    try:
        async with httpx.AsyncClient(timeout=3) as cli:
            tags = (await cli.get(f"{settings.OLLAMA_URL}/api/tags")).json()
            out["reachable"] = True
            names = {m.get("name") for m in tags.get("models", [])}
            out["pulled"] = settings.OLLAMA_MODEL in names or f"{settings.OLLAMA_MODEL}:latest" in names
            ps = (await cli.get(f"{settings.OLLAMA_URL}/api/ps")).json()
            out["loaded"] = any(m.get("name", "").startswith(settings.OLLAMA_MODEL) for m in ps.get("models", []))
    except Exception:  # noqa: BLE001
        pass
    return out


async def stream_answer(question: str, history: list[dict[str, str]] | None = None) -> AsyncIterator[str]:
    context = build_context()
    messages = [{"role": "system", "content": SYSTEM + "\n\n" + context}]
    for h in (history or [])[-4:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            messages.append({"role": h["role"], "content": h["content"][:2000]})
    messages.append({"role": "user", "content": question})
    body = {"model": settings.OLLAMA_MODEL, "messages": messages, "stream": True, "keep_alive": "24h",
            "options": {"temperature": 0.2, "num_ctx": 4096, "num_predict": 350}}
    yield json.dumps({"t": "status", "v": "carregando o modelo"}) + "\n"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5)) as cli:
            async with cli.stream("POST", f"{settings.OLLAMA_URL}/api/chat", json=body) as resp:
                if resp.status_code != 200:
                    text = (await resp.aread()).decode(errors="replace")[:300]
                    yield json.dumps({"t": "error", "v": f"Ollama respondeu {resp.status_code}: {text}"}) + "\n"
                    return
                first = True
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    token = (data.get("message") or {}).get("content", "")
                    if token:
                        if first:
                            yield json.dumps({"t": "status", "v": "respondendo"}) + "\n"
                            first = False
                        yield json.dumps({"t": "token", "v": token}) + "\n"
                    if data.get("done"):
                        break
    except httpx.HTTPError as exc:
        yield json.dumps({"t": "error", "v": f"LLM local indisponível: {exc}"}) + "\n"
        return
    yield json.dumps({"t": "done"}) + "\n"
