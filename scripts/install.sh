#!/bin/bash
set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="kick-alerter"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
USER=$(whoami)

echo "Installing ${SERVICE_NAME} as a systemd service..."

# Set up venv if needed
if [ ! -d "${INSTALL_DIR}/venv" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv "${INSTALL_DIR}/venv"
    "${INSTALL_DIR}/venv/bin/pip" install tiny-tts --no-deps
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"
fi

sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Kick Whisplay Alerter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/src/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl start "${SERVICE_NAME}"

echo "Done. Service status:"
sudo systemctl status "${SERVICE_NAME}" --no-pager
