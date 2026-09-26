# argonv2-controller

A small Python 3.13 controller for the Argon ONE V2 case on Raspberry Pi.

It deliberately avoids the original Argon installer and legacy `RPi.GPIO`.
Fan control uses a single-byte I²C write to address `0x1a`, matching the
protocol verified on the target Argon ONE V2 hardware.

## Features

- Fan control over `/dev/i2c-1`
- Configurable temperature/fan curve
- Hysteresis to prevent fan hunting around thresholds
- GPIO4 power-button pulse detection through libgpiod
- Double-press/reboot pulse handling
- Safe-shutdown pulse handling
- Journald-friendly structured logs
- CLI fan tests and status checks
- Separate system shutdown hook for the `0xff` Argon power-cut command
- No power cut when merely restarting/stopping the controller service

## Project layout

```text
argonv2-controller/
├── pyproject.toml
├── config.example.toml
├── README.md
├── src/
│   └── argonv2_controller/
│       ├── __init__.py
│       ├── button.py
│       ├── cli.py
│       ├── config.py
│       ├── controller.py
│       ├── fan.py
│       └── temperature.py
├── systemd/
│   └── argonv2-controller.service
├── scripts/
│   ├── argonv2-system-shutdown
│   ├── install.sh
│   └── uninstall.sh
└── tests/
    ├── test_config.py
    └── test_controller.py
```

## Requirements

The Pi must expose:

```text
/dev/i2c-1
/dev/gpiochip0
```

and the Argon controller should be visible at `0x1a`:

```bash
sudo i2cdetect -y 1
```

## Install OS prerequisites

On Debian 13 / Raspberry Pi OS style systems:

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev i2c-tools libgpiod-dev gpiod
```

Make sure `/boot/firmware/config.txt` contains:

```ini
dtparam=i2c_arm=on
```

## Install

From the project root:

```bash
chmod +x scripts/install.sh scripts/uninstall.sh scripts/argonv2-system-shutdown
sudo ./scripts/install.sh
```

The installer creates:

```text
/opt/argonv2-controller/.venv
/etc/argonv2-controller/config.toml
/etc/systemd/system/argonv2-controller.service
/usr/lib/systemd/system-shutdown/argonv2-controller
```

## Configuration

Default configuration:

```toml
[i2c]
bus = 1
address = 0x1a

[temperature]
path = "/sys/class/thermal/thermal_zone0/temp"
poll_interval_seconds = 5.0

[fan]
hysteresis_c = 3.0
minimum_change_percent = 1

[[fan.curve]]
temp_c = 50
speed_percent = 20

[[fan.curve]]
temp_c = 55
speed_percent = 35

[[fan.curve]]
temp_c = 60
speed_percent = 60

[[fan.curve]]
temp_c = 65
speed_percent = 100

[button]
enabled = true
chip = "/dev/gpiochip0"
line = 4
reboot_min_ms = 10
reboot_max_ms = 30
shutdown_min_ms = 30
shutdown_max_ms = 55
```

After editing:

```bash
sudo systemctl restart argonv2-controller
```

## Useful commands

Check configuration/hardware:

```bash
sudo /opt/argonv2-controller/.venv/bin/argonv2-controller status
```

Set a fan speed:

```bash
sudo /opt/argonv2-controller/.venv/bin/argonv2-controller set-fan 100
sudo /opt/argonv2-controller/.venv/bin/argonv2-controller set-fan 0
```

Run a fan test:

```bash
sudo /opt/argonv2-controller/.venv/bin/argonv2-controller test-fan
```

Watch logs:

```bash
journalctl -u argonv2-controller -f
```

Show service state:

```bash
systemctl status argonv2-controller
```

## Power-cut behavior

Argon uses byte `0xff` as its "cut power" command.

The main daemon intentionally **never sends `0xff` merely because the daemon
is stopped**. This prevents an ordinary:

```bash
sudo systemctl restart argonv2-controller
```

from cutting power to the Pi.

Instead, `scripts/argonv2-system-shutdown` is installed under:

```text
/usr/lib/systemd/system-shutdown/
```

Systemd invokes executables in that directory during the final shutdown
phase. The hook sends `0xff` only for `poweroff` and `halt`, not for reboot.

The shutdown hook uses `/usr/sbin/i2cset` rather than Python so that it remains
small and independent of the venv during late shutdown.

## Safety notes

Do not manually send `0xff` while the Pi is running unless you intentionally
want the Argon controller to remove power.

A 5-second physical hold may still cause a hardware-enforced power cut by the
Argon controller, independently of this program.
