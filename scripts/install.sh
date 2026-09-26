#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="$PROJECT_DIR/config.toml"
SERVICE_PATH="/etc/systemd/system/argonv2-controller.service"
SHUTDOWN_HOOK="/usr/lib/systemd/system-shutdown/argonv2-controller"

if [[ $EUID -ne 0 ]]; then
    echo "Run this installer with sudo."
    exit 1
fi

for command in python3 i2cset; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Missing required command: $command"
        exit 1
    fi
done

echo "Installing from checkout: $PROJECT_DIR"

echo "Creating Python virtual environment"
python3 -m venv "$PROJECT_DIR/.argonv2_controller"
"$PROJECT_DIR/.argonv2_controller/bin/python" -m pip install --upgrade pip
"$PROJECT_DIR/.argonv2_controller/bin/pip" install --editable "$PROJECT_DIR"

echo "Installing configuration"
if [[ ! -f "$CONFIG_PATH" ]]; then
    cp "$PROJECT_DIR/config.example.toml" "$CONFIG_PATH"
else
    echo "Keeping existing $CONFIG_PATH"
fi

echo "Installing systemd service"
python3 - "$PROJECT_DIR" "$SERVICE_PATH" <<'PYTHON'
from pathlib import Path
import sys

project = Path(sys.argv[1])
# Escape literal paths for systemd's quoted values and specifier expansion.
path = str(project).replace("\\", "\\\\").replace('"', '\\"')
path = path.replace("%", "%%").replace("\n", "\\n").replace("\r", "\\r")
template = (project / "systemd/argonv2-controller.service").read_text()
lines = []
for line in template.splitlines():
    value = path.replace("$", "$$") if line.startswith("ExecStart=") else path
    lines.append(line.replace("@PROJECT_DIR@", value))
Path(sys.argv[2]).write_text("\n".join(lines) + "\n")
PYTHON

echo "Installing final-shutdown hook"
install -m 0755 "$PROJECT_DIR/scripts/argonv2-system-shutdown" "$SHUTDOWN_HOOK"

systemctl daemon-reload
systemctl enable argonv2-controller.service
systemctl restart argonv2-controller.service

echo
echo "Installed."
echo "Status:"
systemctl --no-pager --full status argonv2-controller.service || true
echo
echo "Logs:"
echo "  journalctl -u argonv2-controller -f"
