# Kick Stream Alerter

Displays real-time [Kick.com](https://kick.com) stream alerts on a [WhisPlay](https://whisplay.com) LCD device. Monitors a streamer's channel and shows visual alerts with LED effects for gift subs, channel point redeems, and Kicks gifts.

## Hardware Requirements

- Raspberry Pi (or compatible SBC)
- WhisPlay LCD display (connected via SPI)
- Physical button connected to the WhisPlay board (for dismissing alerts)

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd kick
```

### 2. Install WhisPlay drivers

Run the appropriate installer for your board from the vendor directory:

```bash
ls vendor/Whisplay/Driver/
# e.g. sudo bash vendor/Whisplay/Driver/install_rpi.sh
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your Kick streamer username:

```
KICK_USERNAME=your_kick_username_here
```

Optionally set the log level (defaults to `WARNING` — errors and warnings only):

```
LOG_LEVEL=INFO    # INFO, DEBUG, WARNING, ERROR, CRITICAL
```

### 4. Run

```bash
./run.sh
```

The script automatically creates a Python virtual environment and installs dependencies on first run.

### 5. (Optional) Run on startup

To install as a systemd service that starts automatically on boot:

```bash
./install.sh
```

To remove the service:

```bash
./uninstall.sh
```

Use `sudo systemctl status kick-alerter` to check the service, and `journalctl -u kick-alerter -f` to follow its logs.

## What It Does

Connects to Kick.com's real-time event stream via WebSocket and renders alerts directly on the LCD display:

| Event | Display |
|-------|---------|
| Gift subscription | Gifter name + number of subs gifted |
| Channel point redeem | Redeemer name + reward title |
| Kicks gift | Sender name + gift name + amount |

Each alert plays an LED flash sequence and stays on screen for 20 seconds or until the button is pressed.

## Customizing Alerts

Alerts are customized through [config/alerts.json](config/alerts.json), keyed by alert type. If the file is missing, empty, or an alert type is omitted, that alert uses its default static layout.

### Alert types

| Key         | Triggered by          | Header text        | Dynamic text                          |
|-------------|-----------------------|--------------------|---------------------------------------|
| `gift_sub`  | A viewer gifts subs   | `GIFTED SUB!`      | gifter username + `gifted N sub(s)!`  |
| `reward`    | Channel point redeem  | `REWARD REDEEMED!` | redeemer username + reward title      |
| `kicks`     | A viewer sends Kicks  | `KICK GIFTED!`     | sender username + gift name (+ count) |

### Options

| Option | Type   | Description                                                                 |
|--------|--------|-----------------------------------------------------------------------------|
| `gif`  | string | Filename of an animated GIF in `assets/`. When set, the GIF plays centered on screen with the header above it and the username/subtitle below. Loops until the 20s timeout or button press. If the file is missing, the alert falls back to the static layout. |

### Example

Drop your GIFs into `assets/` and point to them from `config/alerts.json`:

```json
{
  "gift_sub": { "gif": "giftsub.gif" },
  "reward":   { "gif": "reward.gif" },
  "kicks":    { "gif": "kicks.gif" }
}
```

You can configure just a subset — e.g. `{ "gift_sub": { "gif": "party.gif" } }` enables the GIF only for gift subs; `reward` and `kicks` keep their default layouts.

## Battery-powered Pi Zero 2

If you're running this on a battery, there are a couple of helper scripts that apply system-level tweaks to reduce idle power draw:

```bash
./scripts/enable-power-saving.sh    # apply tweaks (requires sudo; reboot after)
./scripts/disable-power-saving.sh   # revert everything
```

The enable script:

- Appends a fenced block to `config.txt` that disables onboard Bluetooth (`dtoverlay=disable-bt`), blanks HDMI (`hdmi_blanking=2`), and turns off the green ACT LED.
- Disables the `bluetooth` and `hciuart` systemd services.
- Installs a tiny `kick-power.service` unit that pins the CPU governor to `ondemand` at boot.

The disable script reverses each of those steps. Both are idempotent and auto-`sudo`, and detect Bookworm's `/boot/firmware/config.txt` vs the older `/boot/config.txt`. A reboot is required for the `config.txt` changes to take effect.

## Project Structure

```
kick/
├── src/
│   ├── main.py             # Entry point and event loop
│   ├── kick_client.py      # Kick.com Pusher WebSocket client
│   ├── display_manager.py  # LCD rendering and LED control
│   └── logger.py           # Logging setup (controlled via LOG_LEVEL env var)
├── assets/
│   ├── background.jpg      # Alert background image
│   └── pixel.ttf           # Font used for alert text
├── config/
│   └── alerts.json         # Per-alert-type customization (GIFs, etc.)
├── scripts/
│   ├── enable-power-saving.sh   # Apply battery-saving tweaks (BT/HDMI/LED/CPU)
│   └── disable-power-saving.sh  # Revert those tweaks
├── vendor/
│   └── Whisplay/Driver/    # WhisPlay LCD driver and board installers
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
├── run.sh                  # Startup script
├── install.sh              # Install as systemd service (auto-start on boot)
└── uninstall.sh            # Remove systemd service
```

## Dependencies

Managed automatically by `run.sh` via `requirements.txt`:

- `pysher` — Pusher WebSocket client
- `requests` — HTTP for Kick API calls
- `Pillow` — Image composition for alerts
- `python-dotenv` — `.env` file loading
- `spidev` / `rpi-lgpio` — SPI and GPIO for Raspberry Pi hardware

## Development

The app runs fine on non-Pi hardware for development — the WhisPlay driver initializes with a graceful fallback if the hardware isn't present, so you can test event parsing and logic without the physical device.
