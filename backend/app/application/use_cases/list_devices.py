from __future__ import annotations

from app.application.dto.device_summary import DeviceSummaryDTO
from app.domain.ports.message_subscriber import MessageSubscriber


class ListDevices:
    """Caso de uso: retorna os dispositivos conhecidos e seu status online/offline."""

    def __init__(self, message_subscriber: MessageSubscriber) -> None:
        self._message_subscriber = message_subscriber

    def execute(self) -> list[DeviceSummaryDTO]:
        devices = self._message_subscriber.get_known_devices()
        return [
            DeviceSummaryDTO(
                device_id=device.device_id,
                room_id=device.room_id,
                online=device.online,
                last_seen=device.last_seen,
            )
            for device in devices
        ]
