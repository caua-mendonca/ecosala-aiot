"""Serviço de inferência em tempo real.

Consome q.inference (telemetria dos equipamentos + avisos model.updated),
aplica os modelos de regressão e publica no exchange ecosala.events:
  prediction.<zona>.equipment.<id>  (saúde, vida útil restante, tendência)
  alert.<zona>.<id>                 (alertas preditivos com histerese)
Ao receber model.updated recarrega o modelo SEM reiniciar o serviço.
"""
from __future__ import annotations

import logging
import os

from ecosala_common import ml
from ecosala_common import topology as T
from ecosala_common.config import MODELS_DIR
from ecosala_common.envelope import make_envelope
from ecosala_common.rabbit import consume_forever, publish

from .engine import InferenceEngine

log = logging.getLogger("inferencia")


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    engine = InferenceEngine(ml.load_active(MODELS_DIR))
    log.info("modelo em uso: %s", engine.model.version if engine.model else "nenhum (aguardando treino)")
    checks = {"n": 0}

    def handle(ch, msg: dict, routing_key: str) -> None:  # noqa: ANN001
        if msg["type"] == "model.updated":
            engine.set_model(ml.load_active(MODELS_DIR))
            log.info("modelo recarregado em tempo real: versão %s", engine.model.version if engine.model else None)
            return
        if msg["type"] != "telemetry":
            return
        # a cada 300 mensagens confere se surgiu modelo novo (ex.: treino automático inicial)
        checks["n"] += 1
        if engine.model is None and checks["n"] % 300 == 0:
            engine.set_model(ml.load_active(MODELS_DIR))
        device, room = msg["device"], msg.get("room") or "?"
        prediction, alerts = engine.process(device, msg["payload"])
        if prediction:
            publish(ch, T.EX_EVENTS, T.key("prediction", room, "equipment", device),
                    make_envelope("prediction", device, prediction, room=room))
        for a in alerts:
            publish(ch, T.EX_EVENTS, T.key("alert", room, device), make_envelope("alert", device, a, room=room))
            log.info("alerta %s %s: %s", a["state"], device, a["message"])

    consume_forever(T.Q_INFERENCE, handle, prefetch=20)


if __name__ == "__main__":
    main()
