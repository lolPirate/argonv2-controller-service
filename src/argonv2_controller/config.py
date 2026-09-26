from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


DEFAULT_CONFIG_PATH = Path("/etc/argonv2-controller/config.toml")


@dataclass(frozen=True, slots=True)
class I2CConfig:
    bus: int = 1
    address: int = 0x1A


@dataclass(frozen=True, slots=True)
class TemperatureConfig:
    path: str = "/sys/class/thermal/thermal_zone0/temp"
    poll_interval_seconds: float = 5.0


@dataclass(frozen=True, slots=True)
class FanPoint:
    temp_c: float
    speed_percent: int


@dataclass(frozen=True, slots=True)
class FanConfig:
    hysteresis_c: float
    minimum_change_percent: int
    curve: tuple[FanPoint, ...]


@dataclass(frozen=True, slots=True)
class ButtonConfig:
    enabled: bool = True
    chip: str = "/dev/gpiochip0"
    line: int = 4
    reboot_min_ms: float = 10.0
    reboot_max_ms: float = 30.0
    shutdown_min_ms: float = 30.0
    shutdown_max_ms: float = 55.0


@dataclass(frozen=True, slots=True)
class Config:
    i2c: I2CConfig
    temperature: TemperatureConfig
    fan: FanConfig
    button: ButtonConfig


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Config:
    path = Path(path)
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    i2c_raw = raw.get("i2c", {})
    temp_raw = raw.get("temperature", {})
    fan_raw = raw.get("fan", {})
    button_raw = raw.get("button", {})

    curve = tuple(
        FanPoint(float(point["temp_c"]), int(point["speed_percent"]))
        for point in fan_raw.get("curve", [])
    )
    if not curve:
        raise ValueError("fan.curve must contain at least one entry")

    curve = tuple(sorted(curve, key=lambda point: point.temp_c))

    for point in curve:
        if not 0 <= point.speed_percent <= 100:
            raise ValueError(
                f"fan speed must be in 0..100; got {point.speed_percent}"
            )

    for previous, current in zip(curve, curve[1:]):
        if current.temp_c == previous.temp_c:
            raise ValueError(f"duplicate fan threshold: {current.temp_c}")

    hysteresis = float(fan_raw.get("hysteresis_c", 3.0))
    if hysteresis < 0:
        raise ValueError("fan.hysteresis_c must be >= 0")

    poll_interval = float(temp_raw.get("poll_interval_seconds", 5.0))
    if poll_interval <= 0:
        raise ValueError("temperature.poll_interval_seconds must be > 0")

    minimum_change = int(fan_raw.get("minimum_change_percent", 1))
    if not 0 <= minimum_change <= 100:
        raise ValueError("fan.minimum_change_percent must be in 0..100")

    return Config(
        i2c=I2CConfig(
            bus=int(i2c_raw.get("bus", 1)),
            address=int(i2c_raw.get("address", 0x1A)),
        ),
        temperature=TemperatureConfig(
            path=str(
                temp_raw.get(
                    "path", "/sys/class/thermal/thermal_zone0/temp"
                )
            ),
            poll_interval_seconds=poll_interval,
        ),
        fan=FanConfig(
            hysteresis_c=hysteresis,
            minimum_change_percent=minimum_change,
            curve=curve,
        ),
        button=ButtonConfig(
            enabled=bool(button_raw.get("enabled", True)),
            chip=str(button_raw.get("chip", "/dev/gpiochip0")),
            line=int(button_raw.get("line", 4)),
            reboot_min_ms=float(button_raw.get("reboot_min_ms", 10)),
            reboot_max_ms=float(button_raw.get("reboot_max_ms", 30)),
            shutdown_min_ms=float(button_raw.get("shutdown_min_ms", 30)),
            shutdown_max_ms=float(button_raw.get("shutdown_max_ms", 55)),
        ),
    )
