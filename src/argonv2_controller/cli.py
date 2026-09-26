from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path

from .button import PowerButtonMonitor
from .config import DEFAULT_CONFIG_PATH, Config, load_config
from .controller import FanCurveController
from .fan import ArgonFan
from .temperature import CpuTemperature


LOG = logging.getLogger("argonv2_controller")


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run_daemon(config: Config) -> int:
    stop = threading.Event()

    def request_stop(signum, _frame):
        LOG.info("received signal %s; stopping", signum)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    temp = CpuTemperature(config.temperature.path)
    controller = FanCurveController(config.fan)

    button: PowerButtonMonitor | None = None
    if config.button.enabled:
        button = PowerButtonMonitor(
            chip=config.button.chip,
            line=config.button.line,
            reboot_min_ms=config.button.reboot_min_ms,
            reboot_max_ms=config.button.reboot_max_ms,
            shutdown_min_ms=config.button.shutdown_min_ms,
            shutdown_max_ms=config.button.shutdown_max_ms,
        )

    with ArgonFan(config.i2c.bus, config.i2c.address) as fan:
        if button:
            button.start()

        LOG.info(
            "controller started: i2c-%d address=0x%02x poll=%.1fs hysteresis=%.1fC",
            config.i2c.bus,
            config.i2c.address,
            config.temperature.poll_interval_seconds,
            config.fan.hysteresis_c,
        )

        current_speed: int | None = None

        try:
            while not stop.is_set():
                temperature_c = temp.read_celsius()
                decision = controller.decide(temperature_c)

                should_write = (
                    current_speed is None
                    or abs(decision.speed_percent - current_speed)
                    >= config.fan.minimum_change_percent
                )

                if should_write:
                    fan.set_speed(decision.speed_percent)
                    current_speed = decision.speed_percent
                    LOG.info(
                        "CPU %.1fC -> requested fan %d%%",
                        temperature_c,
                        current_speed,
                    )
                else:
                    LOG.debug(
                        "CPU %.1fC -> fan remains requested at %d%%",
                        temperature_c,
                        current_speed,
                    )

                stop.wait(config.temperature.poll_interval_seconds)

        finally:
            if button:
                button.stop()

            # A service restart is not a system shutdown. Do not send 0xff here.
            # We do leave the fan off when the controller exits normally.
            try:
                fan.set_speed(0)
                LOG.info("controller stopped; requested fan 0%%")
            except OSError:
                LOG.exception("could not request fan 0%% while stopping")

    return 0


def cmd_status(config: Config) -> int:
    temperature = CpuTemperature(config.temperature.path).read_celsius()
    print(f"CPU temperature : {temperature:.1f} C")
    print(f"I2C bus         : {config.i2c.bus}")
    print(f"I2C address     : 0x{config.i2c.address:02x}")
    print(f"GPIO chip       : {config.button.chip}")
    print(f"GPIO line       : {config.button.line}")
    print(f"Button enabled  : {config.button.enabled}")

    device = Path(f"/dev/i2c-{config.i2c.bus}")
    print(f"I2C device      : {'present' if device.exists() else 'MISSING'}")
    print(
        f"GPIO device     : {'present' if Path(config.button.chip).exists() else 'MISSING'}"
    )

    try:
        with ArgonFan(config.i2c.bus, config.i2c.address) as fan:
            # A safe write-only presence check: preserve no unknown state;
            # command 0 simply asks the fan to stop.
            fan.set_speed(0)
        print("Argon I2C write : OK")
    except OSError as exc:
        print(f"Argon I2C write : FAILED ({exc})")
        return 1

    return 0


def cmd_set_fan(config: Config, speed: int) -> int:
    with ArgonFan(config.i2c.bus, config.i2c.address) as fan:
        fan.set_speed(speed)
    print(f"Requested fan speed: {speed}%")
    return 0


def cmd_test_fan(config: Config) -> int:
    stages = ((0, 3), (25, 5), (50, 5), (100, 8), (0, 0))

    with ArgonFan(config.i2c.bus, config.i2c.address) as fan:
        temp = CpuTemperature(config.temperature.path)
        try:
            for speed, delay in stages:
                fan.set_speed(speed)
                print(f"fan={speed:3d}%  CPU={temp.read_celsius():5.1f} C")
                if delay:
                    time.sleep(delay)
        finally:
            fan.set_speed(0)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="argonv2-controller")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="path to TOML configuration",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run the controller daemon")
    sub.add_parser("status", help="check temperature and hardware access")

    set_fan = sub.add_parser("set-fan", help="request a fan speed")
    set_fan.add_argument("speed", type=int, choices=range(0, 101), metavar="0..100")

    sub.add_parser("test-fan", help="cycle through several fan speeds")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.verbose)

    try:
        config = load_config(args.config)

        match args.command:
            case "run":
                return run_daemon(config)
            case "status":
                return cmd_status(config)
            case "set-fan":
                return cmd_set_fan(config, args.speed)
            case "test-fan":
                return cmd_test_fan(config)
            case _:
                parser.error(f"unknown command: {args.command}")
    except (OSError, ValueError) as exc:
        LOG.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
