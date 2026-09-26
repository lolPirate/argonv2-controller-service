from __future__ import annotations

from pathlib import Path


class CpuTemperature:
    def __init__(
        self,
        path: str | Path = "/sys/class/thermal/thermal_zone0/temp",
    ):
        self.path = Path(path)

    def read_celsius(self) -> float:
        raw = self.path.read_text(encoding="ascii").strip()
        return int(raw) / 1000.0
