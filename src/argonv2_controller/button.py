from __future__ import annotations

import logging
import subprocess
import threading
from datetime import timedelta
from enum import Enum, auto
from typing import Callable

import gpiod
from gpiod.line import Bias, Direction, Edge


LOG = logging.getLogger(__name__)


class ButtonAction(Enum):
    REBOOT = auto()
    SHUTDOWN = auto()
    UNKNOWN = auto()


class PowerButtonMonitor:
    def __init__(
        self,
        *,
        chip: str,
        line: int,
        reboot_min_ms: float,
        reboot_max_ms: float,
        shutdown_min_ms: float,
        shutdown_max_ms: float,
        on_action: Callable[[ButtonAction, float], None] | None = None,
    ):
        self.chip = chip
        self.line = line
        self.reboot_min_ms = reboot_min_ms
        self.reboot_max_ms = reboot_max_ms
        self.shutdown_min_ms = shutdown_min_ms
        self.shutdown_max_ms = shutdown_max_ms
        self.on_action = on_action or self._default_action
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def classify(self, width_ms: float) -> ButtonAction:
        if self.reboot_min_ms <= width_ms < self.reboot_max_ms:
            return ButtonAction.REBOOT
        if self.shutdown_min_ms <= width_ms <= self.shutdown_max_ms:
            return ButtonAction.SHUTDOWN
        return ButtonAction.UNKNOWN

    @staticmethod
    def _default_action(action: ButtonAction, width_ms: float) -> None:
        if action is ButtonAction.REBOOT:
            LOG.warning("power button requested reboot (pulse %.2f ms)", width_ms)
            subprocess.run(
                ["/usr/bin/systemctl", "reboot"],
                check=False,
            )
        elif action is ButtonAction.SHUTDOWN:
            LOG.warning("power button requested shutdown (pulse %.2f ms)", width_ms)
            subprocess.run(
                ["/usr/bin/systemctl", "poweroff"],
                check=False,
            )
        else:
            LOG.info("ignored unknown power-button pulse %.2f ms", width_ms)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="argonv2-power-button",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        settings = gpiod.LineSettings(
            direction=Direction.INPUT,
            edge_detection=Edge.BOTH,
            bias=Bias.PULL_DOWN,
        )

        LOG.info("monitoring Argon power button on %s line %d", self.chip, self.line)

        try:
            with gpiod.request_lines(
                self.chip,
                consumer="argonv2-controller",
                config={self.line: settings},
            ) as request:
                rising_ns: int | None = None

                while not self._stop.is_set():
                    if not request.wait_edge_events(timeout=timedelta(seconds=1)):
                        continue

                    for event in request.read_edge_events():
                        if event.event_type is gpiod.EdgeEvent.Type.RISING_EDGE:
                            rising_ns = event.timestamp_ns
                        elif (
                            event.event_type is gpiod.EdgeEvent.Type.FALLING_EDGE
                            and rising_ns is not None
                        ):
                            width_ms = (event.timestamp_ns - rising_ns) / 1_000_000
                            rising_ns = None
                            action = self.classify(width_ms)
                            self.on_action(action, width_ms)
        except Exception:
            LOG.exception("power-button monitor failed")
            raise
