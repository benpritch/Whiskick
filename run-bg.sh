#!/bin/bash
# Runs the Kick Whisplay Alerter in the background

cd "$(dirname "$0")"

LOG_FILE="alerter.log"

nohup ./run.sh >> "$LOG_FILE" 2>&1 &
PID=$!

echo "Started in background (PID: $PID)"
echo "Logs: $LOG_FILE"
echo "Stop with: kill $PID"
