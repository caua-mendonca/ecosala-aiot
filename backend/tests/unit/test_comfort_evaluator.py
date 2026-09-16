from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.entities.reading import Reading
from app.domain.services.comfort_evaluator import ComfortEvaluator
from app.domain.value_objects.comfort_status import ComfortStatus
from app.domain.value_objects.comfort_thresholds import ComfortThresholds


@pytest.fixture
def thresholds() -> ComfortThresholds:
    return ComfortThresholds(
        temperature_min_c=20.0,
        temperature_max_c=26.0,
        humidity_min_percent=40.0,
        humidity_max_percent=60.0,
        luminosity_min_lux=300.0,
        temperature_critical_margin_c=4.0,
        humidity_critical_margin_percent=15.0,
        luminosity_critical_margin_lux=150.0,
    )


def make_reading(temperature: float, humidity: float, luminosity: float) -> Reading:
    return Reading(
        device_id="esp32-sala-101",
        room_id="sala-101",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=UTC),
        temperature=temperature,
        humidity=humidity,
        luminosity=luminosity,
    )


def test_all_within_range_is_ok(thresholds: ComfortThresholds) -> None:
    evaluator = ComfortEvaluator(thresholds)
    reading = make_reading(temperature=23.0, humidity=50.0, luminosity=400.0)

    assert evaluator.evaluate(reading) == ComfortStatus.OK


def test_slightly_above_max_temperature_is_atencao(thresholds: ComfortThresholds) -> None:
    evaluator = ComfortEvaluator(thresholds)
    reading = make_reading(temperature=27.0, humidity=50.0, luminosity=400.0)

    assert evaluator.evaluate(reading) == ComfortStatus.ATENCAO


def test_far_above_max_temperature_is_critico(thresholds: ComfortThresholds) -> None:
    evaluator = ComfortEvaluator(thresholds)
    reading = make_reading(temperature=32.0, humidity=50.0, luminosity=400.0)

    assert evaluator.evaluate(reading) == ComfortStatus.CRITICO


def test_slightly_below_min_humidity_is_atencao(thresholds: ComfortThresholds) -> None:
    evaluator = ComfortEvaluator(thresholds)
    reading = make_reading(temperature=23.0, humidity=35.0, luminosity=400.0)

    assert evaluator.evaluate(reading) == ComfortStatus.ATENCAO


def test_far_below_min_humidity_is_critico(thresholds: ComfortThresholds) -> None:
    evaluator = ComfortEvaluator(thresholds)
    reading = make_reading(temperature=23.0, humidity=20.0, luminosity=400.0)

    assert evaluator.evaluate(reading) == ComfortStatus.CRITICO


def test_low_luminosity_is_atencao_then_critico(thresholds: ComfortThresholds) -> None:
    evaluator = ComfortEvaluator(thresholds)

    slightly_low = make_reading(temperature=23.0, humidity=50.0, luminosity=200.0)
    very_low = make_reading(temperature=23.0, humidity=50.0, luminosity=50.0)

    assert evaluator.evaluate(slightly_low) == ComfortStatus.ATENCAO
    assert evaluator.evaluate(very_low) == ComfortStatus.CRITICO


def test_multiple_metrics_out_of_range_is_critico_if_any_is_critical(
    thresholds: ComfortThresholds,
) -> None:
    evaluator = ComfortEvaluator(thresholds)
    reading = make_reading(temperature=27.0, humidity=35.0, luminosity=50.0)

    assert evaluator.evaluate(reading) == ComfortStatus.CRITICO


def test_boundary_values_are_exactly_ok(thresholds: ComfortThresholds) -> None:
    evaluator = ComfortEvaluator(thresholds)
    reading = make_reading(temperature=20.0, humidity=60.0, luminosity=300.0)

    assert evaluator.evaluate(reading) == ComfortStatus.OK
