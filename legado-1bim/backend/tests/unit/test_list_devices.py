from __future__ import annotations

from datetime import UTC, datetime

from fakes import FakeMessageSubscriber

from app.application.use_cases.list_devices import ListDevices
from app.domain.entities.device_connection import DeviceConnection


def test_list_devices_maps_connections_to_dto() -> None:
    subscriber = FakeMessageSubscriber(
        devices=[
            DeviceConnection(
                device_id="esp32-sala-101",
                room_id="sala-101",
                online=True,
                last_seen=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
            )
        ]
    )
    use_case = ListDevices(subscriber)

    result = use_case.execute()

    assert len(result) == 1
    assert result[0].device_id == "esp32-sala-101"
    assert result[0].online is True


def test_list_devices_returns_empty_when_no_devices_known() -> None:
    subscriber = FakeMessageSubscriber(devices=[])
    use_case = ListDevices(subscriber)

    assert use_case.execute() == []
