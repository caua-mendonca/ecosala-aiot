from __future__ import annotations

from app.domain.entities.reading import Reading
from app.domain.value_objects.comfort_status import ComfortStatus
from app.domain.value_objects.comfort_thresholds import ComfortThresholds


class ComfortEvaluator:
    """Classifica uma leitura em OK, ATENCAO ou CRITICO.

    Regra: cada grandeza (temperatura, umidade, luminosidade) tem um desvio
    em relacao a sua faixa ideal. Se algum desvio ultrapassar a margem
    critica configurada, o status e CRITICO. Se houver desvio mas nenhum
    ultrapassar a margem critica, o status e ATENCAO. Sem nenhum desvio, OK.
    """

    def __init__(self, thresholds: ComfortThresholds) -> None:
        self._thresholds = thresholds

    def evaluate(self, reading: Reading) -> ComfortStatus:
        thresholds = self._thresholds

        temperature_deviation = self._deviation_from_range(
            reading.temperature, thresholds.temperature_min_c, thresholds.temperature_max_c
        )
        humidity_deviation = self._deviation_from_range(
            reading.humidity, thresholds.humidity_min_percent, thresholds.humidity_max_percent
        )
        luminosity_deviation = max(0.0, thresholds.luminosity_min_lux - reading.luminosity)

        is_critical = (
            temperature_deviation > thresholds.temperature_critical_margin_c
            or humidity_deviation > thresholds.humidity_critical_margin_percent
            or luminosity_deviation > thresholds.luminosity_critical_margin_lux
        )
        if is_critical:
            return ComfortStatus.CRITICO

        has_any_deviation = (
            temperature_deviation > 0 or humidity_deviation > 0 or luminosity_deviation > 0
        )
        if has_any_deviation:
            return ComfortStatus.ATENCAO

        return ComfortStatus.OK

    @staticmethod
    def _deviation_from_range(value: float, minimum: float, maximum: float) -> float:
        if value < minimum:
            return minimum - value
        if value > maximum:
            return value - maximum
        return 0.0
