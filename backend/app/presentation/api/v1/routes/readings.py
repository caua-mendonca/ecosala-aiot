"""GET /readings/latest, /readings/history e /comfort/thresholds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.application.use_cases.get_latest_readings import GetLatestReadings
from app.application.use_cases.get_reading_history import GetReadingHistory
from app.domain.value_objects.comfort_thresholds import ComfortThresholds
from app.presentation.api.v1.dependencies import (
    get_comfort_thresholds,
    get_latest_readings_use_case,
    get_reading_history_use_case,
)
from app.presentation.api.v1.schemas import ComfortThresholdsSchema, ReadingSummarySchema

router = APIRouter(tags=["readings"])


@router.get("/readings/latest", response_model=list[ReadingSummarySchema])
def get_latest_readings(
    room_id: str | None = Query(default=None, description="Filtra por sala, ex.: sala-101"),
    use_case: GetLatestReadings = Depends(get_latest_readings_use_case),
) -> list[ReadingSummarySchema]:
    results = use_case.execute(room_id=room_id)
    return [ReadingSummarySchema.model_validate(item, from_attributes=True) for item in results]


@router.get("/readings/history", response_model=list[ReadingSummarySchema])
def get_reading_history(
    device_id: str = Query(description="Identificador do dispositivo, ex.: esp32-sala-101"),
    start: str = Query(default="-1h", description="Inicio do intervalo (sintaxe Flux)"),
    stop: str = Query(default="now()", description="Fim do intervalo (sintaxe Flux)"),
    window: str = Query(default="1m", description="Janela de agregacao (sintaxe Flux)"),
    use_case: GetReadingHistory = Depends(get_reading_history_use_case),
) -> list[ReadingSummarySchema]:
    results = use_case.execute(device_id=device_id, start=start, stop=stop, window=window)
    return [ReadingSummarySchema.model_validate(item, from_attributes=True) for item in results]


@router.get("/comfort/thresholds", response_model=ComfortThresholdsSchema)
def get_thresholds(
    thresholds: ComfortThresholds = Depends(get_comfort_thresholds),
) -> ComfortThresholdsSchema:
    return ComfortThresholdsSchema.model_validate(thresholds, from_attributes=True)
