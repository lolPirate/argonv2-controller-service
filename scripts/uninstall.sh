#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "Run this uninstaller with sudo."
    exit 1
fi

systemctl disable --now argonv2-controller.service 2>/dev/null || true
rm -f /etc/systemd/system/argonv2-controller.service
rm -f /usr/lib/systemd/system-shutdown/argonv2-controller
systemctl daemon-reload

echo "Service and shutdown hook removed."
echo
echo "Preserved intentionally:"
echo "  $PROJECT_DIR/config.toml"
echo "  $PROJECT_DIR (including .argonv2_controller)"
echo
echo "Delete the checkout manually if you want a complete purge."
