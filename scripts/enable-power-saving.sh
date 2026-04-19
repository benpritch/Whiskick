#!/usr/bin/env bash
# Apply battery-saving tweaks for a Raspberry Pi Zero 2 running the Kick alerter.
# Re-runnable: changes are fenced with a marker block so disable-power-saving.sh
# can cleanly remove them.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    exec sudo -E "$0" "$@"
fi

MARKER_BEGIN="# >>> kick-power-tweaks >>>"
MARKER_END="# <<< kick-power-tweaks <<<"

# Pi OS Bookworm moved config.txt to /boot/firmware; older releases use /boot.
if [[ -f /boot/firmware/config.txt ]]; then
    CONFIG_TXT=/boot/firmware/config.txt
elif [[ -f /boot/config.txt ]]; then
    CONFIG_TXT=/boot/config.txt
else
    echo "Could not find config.txt in /boot or /boot/firmware" >&2
    exit 1
fi

echo "Using $CONFIG_TXT"

if ! grep -qF "$MARKER_BEGIN" "$CONFIG_TXT"; then
    echo "Appending power-saving block to $CONFIG_TXT"
    cat >> "$CONFIG_TXT" <<EOF

$MARKER_BEGIN
# Disable onboard Bluetooth (uses UART power even when idle)
dtoverlay=disable-bt
# Blank HDMI output when no signal consumer is attached
hdmi_blanking=2
# Turn off the green ACT LED
dtparam=act_led_trigger=none
dtparam=act_led_activelow=off
$MARKER_END
EOF
else
    echo "Power-saving block already present in $CONFIG_TXT — skipping."
fi

echo "Disabling Bluetooth services"
systemctl disable --now hciuart.service 2>/dev/null || true
systemctl disable --now bluetooth.service 2>/dev/null || true

echo "Installing kick-power.service (sets CPU governor to ondemand at boot)"
cat > /etc/systemd/system/kick-power.service <<'EOF'
[Unit]
Description=Kick alerter power tuning (CPU governor)
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo ondemand > "$g"; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now kick-power.service

echo
echo "Done. Reboot to apply the config.txt changes (HDMI/BT/LED)."
