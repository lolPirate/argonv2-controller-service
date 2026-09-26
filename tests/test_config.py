from pathlib import Path

from argonv2_controller.config import load_config


def test_load_config(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[i2c]
bus = 1
address = 0x1a

[temperature]
poll_interval_seconds = 5

[fan]
hysteresis_c = 3
minimum_change_percent = 1

[[fan.curve]]
temp_c = 55
speed_percent = 35

[[fan.curve]]
temp_c = 65
speed_percent = 100

[button]
enabled = true
line = 4
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.i2c.address == 0x1A
    assert config.fan.curve[0].speed_percent == 35
    assert config.button.line == 4
