from __future__ import annotations

from dataclasses import dataclass

from .config import FanConfig


@dataclass(slots=True)
class FanDecision:
    speed_percent: int
    level: int


class FanCurveController:
    """Stateful fan-curve evaluator with downward hysteresis."""

    def __init__(self, config: FanConfig):
        self.config = config
        self._level = -1

    @property
    def level(self) -> int:
        return self._level

    def _raw_level(self, temperature_c: float) -> int:
        level = -1
        for index, point in enumerate(self.config.curve):
            if temperature_c >= point.temp_c:
                level = index
            else:
                break
        return level

    def decide(self, temperature_c: float) -> FanDecision:
        raw_level = self._raw_level(temperature_c)

        # Increasing temperature: move upward immediately.
        if raw_level > self._level:
            self._level = raw_level

        # Falling temperature: require threshold - hysteresis before stepping down.
        while self._level >= 0:
            active_threshold = self.config.curve[self._level].temp_c
            if temperature_c < active_threshold - self.config.hysteresis_c:
                self._level -= 1
            else:
                break

        speed = (
            0
            if self._level < 0
            else self.config.curve[self._level].speed_percent
        )
        return FanDecision(speed_percent=speed, level=self._level)
