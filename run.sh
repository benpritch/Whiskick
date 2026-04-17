#!/bin/bash
# Wrapper script to run the Kick Whisplay Alerter
# Ensures the virtual environment is used

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Setting up..."
    python3 -m venv venv
    ./venv/bin/pip install tiny-tts --no-deps && \
    ./venv/bin/pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "Failed to install dependencies."
        exit 1
    fi
fi

echo "Starting Display Alerter..."
./venv/bin/python src/main.py
