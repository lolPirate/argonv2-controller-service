#!/usr/bin/env bash
set -euo pipefail

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
echo "  /etc/argonv2-controller/config.toml"
echo "  /opt/argonv2-controller"
echo
echo "Delete those manually if you want a complete purge."
