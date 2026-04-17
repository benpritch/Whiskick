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

## What It Does

Connects to Kick.com's real-time event stream via WebSocket and renders alerts directly on the LCD display:

| Event | Display |
|-------|---------|
| Gift subscription | Gifter name + number of subs gifted |
| Channel point redeem | Redeemer name + reward title |
| Kicks gift | Sender name + gift name + amount |

Each alert plays an LED flash sequence and stays on screen for 20 seconds or until the button is pressed.

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
├── vendor/
│   └── Whisplay/Driver/    # WhisPlay LCD driver and board installers
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
└── run.sh                  # Startup script
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
