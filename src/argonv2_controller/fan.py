from __future__ import annotations

from contextlib import AbstractContextManager
from smbus2 import SMBus


class ArgonFan(AbstractContextManager["ArgonFan"]):
    """Fan interface for the Argon ONE V2 microcontroller.

    The controller accepts a single byte at I2C address 0x1a:
      0..100 -> requested fan speed
      0xff   -> power-cut request

    Fan writes intentionally use SMBus.write_byte(), not write_byte_data().
    """

    POWER_CUT = 0xFF

    def __init__(self, bus_number: int = 1, address: int = 0x1A):
        self.bus_number = bus_number
        self.address = address
        self._bus: SMBus | None = None
        self.last_requested_speed: int | None = None

    def open(self) -> None:
        if self._bus is None:
            self._bus = SMBus(self.bus_number)

    def close(self) -> None:
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def __enter__(self) -> "ArgonFan":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def set_speed(self, speed_percent: int) -> None:
        if not 0 <= speed_percent <= 100:
            raise ValueError("speed_percent must be between 0 and 100")

        self.open()
        assert self._bus is not None
        self._bus.write_byte(self.address, speed_percent)
        self.last_requested_speed = speed_percent

    def request_power_cut(self) -> None:
        self.open()
        assert self._bus is not None
        self._bus.write_byte(self.address, self.POWER_CUT)
