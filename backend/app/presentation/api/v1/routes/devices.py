"""GET /devices - dispositivos conhecidos e seu status online/offline."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.use_cases.list_devices import ListDevices
from app.presentation.api.v1.dependencies import get_list_devices_use_case
from app.presentation.api.v1.schemas import DeviceSchema

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=list[DeviceSchema])
def get_devices(
    use_case: ListDevices = Depends(get_list_devices_use_case),
) -> list[DeviceSchema]:
    devices = use_case.execute()
    return [DeviceSchema.model_validate(device, from_attributes=True) for device in devices]
