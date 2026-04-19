#!/usr/bin/env bash
# Undo the tweaks applied by enable-power-saving.sh.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    exec sudo -E "$0" "$@"
fi

MARKER_BEGIN="# >>> kick-power-tweaks >>>"
MARKER_END="# <<< kick-power-tweaks <<<"

if [[ -f /boot/firmware/config.txt ]]; then
    CONFIG_TXT=/boot/firmware/config.txt
elif [[ -f /boot/config.txt ]]; then
    CONFIG_TXT=/boot/config.txt
else
    echo "Could not find config.txt in /boot or /boot/firmware" >&2
    exit 1
fi

echo "Using $CONFIG_TXT"

if grep -qF "$MARKER_BEGIN" "$CONFIG_TXT"; then
    echo "Removing power-saving block from $CONFIG_TXT"
    # Strip everything between (and including) the markers, with the blank line before it.
    sed -i "/^$/N;/\n$MARKER_BEGIN$/,/$MARKER_END/d" "$CONFIG_TXT"
    # Fallback in case the preceding blank line wasn't present.
    sed -i "/$MARKER_BEGIN/,/$MARKER_END/d" "$CONFIG_TXT"
else
    echo "No power-saving block found in $CONFIG_TXT — skipping."
fi

echo "Re-enabling Bluetooth services"
systemctl enable --now bluetooth.service 2>/dev/null || true
systemctl enable --now hciuart.service 2>/dev/null || true

if [[ -f /etc/systemd/system/kick-power.service ]]; then
    echo "Removing kick-power.service"
    systemctl disable --now kick-power.service 2>/dev/null || true
    rm -f /etc/systemd/system/kick-power.service
    systemctl daemon-reload
fi

echo
echo "Done. Reboot to fully restore HDMI/BT/LED defaults."
