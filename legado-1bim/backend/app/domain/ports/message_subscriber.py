from __future__ import annotations

from typing import Protocol

from app.domain.entities.device_connection import DeviceConnection


class MessageSubscriber(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def get_known_devices(self) -> list[DeviceConnection]: ...

    def is_connected(self) -> bool: ...
