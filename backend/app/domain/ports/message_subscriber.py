from __future__ import annotations

from typing import Protocol

from app.domain.entities.device_connection import DeviceConnection


class MessageSubscriber(Protocol):
    """Porta de assinatura de mensagens MQTT.

    Implementada pela infraestrutura (paho-mqtt, Etapa 5), rodando em thread
    propria e invocando o caso de uso IngestReading para cada telemetria
    valida recebida.
    """

    def start(self) -> None:
        """Inicia a assinatura dos topicos em thread propria."""
        ...

    def stop(self) -> None:
        """Encerra a assinatura e a conexao com o broker."""
        ...

    def get_known_devices(self) -> list[DeviceConnection]:
        """Retorna os dispositivos conhecidos e seu status online/offline."""
        ...
