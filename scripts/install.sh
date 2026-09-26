#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/argonv2-controller"
CONFIG_DIR="/etc/argonv2-controller"
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

echo "Installing project to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -a "$PROJECT_DIR/." "$INSTALL_DIR/"

echo "Creating Python virtual environment"
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install "$INSTALL_DIR"

echo "Installing configuration"
mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    cp "$INSTALL_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
else
    echo "Keeping existing $CONFIG_DIR/config.toml"
fi

echo "Installing systemd service"
cp "$INSTALL_DIR/systemd/argonv2-controller.service" "$SERVICE_PATH"

echo "Installing final-shutdown hook"
install -m 0755 "$INSTALL_DIR/scripts/argonv2-system-shutdown" "$SHUTDOWN_HOOK"

systemctl daemon-reload
systemctl enable --now argonv2-controller.service

echo
echo "Installed."
echo "Status:"
systemctl --no-pager --full status argonv2-controller.service || true
echo
echo "Logs:"
echo "  journalctl -u argonv2-controller -f"
