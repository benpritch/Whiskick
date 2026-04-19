#!/bin/bash
set -e

SERVICE_NAME="kick-alerter"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Removing ${SERVICE_NAME} systemd service..."

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    sudo systemctl stop "${SERVICE_NAME}"
fi

if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
    sudo systemctl disable "${SERVICE_NAME}"
fi

if [ -f "${SERVICE_FILE}" ]; then
    sudo rm "${SERVICE_FILE}"
fi

sudo systemctl daemon-reload

echo "Done. ${SERVICE_NAME} has been removed from startup."
