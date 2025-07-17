#!/bin/bash
set -e

echo "Starting CUPS..."
cupsd

# Wait until CUPS is ready (optional but recommended)
for i in {1..10}; do
    if lpstat -r >/dev/null 2>&1; then
        break
    fi
    echo "Waiting for CUPS to start..."
    sleep 1
done

echo "Adding printer ${PRINTER_NAME} at ${PRINTER_IP}"
lpadmin -p "$PRINTER_NAME" -E -v "socket://${PRINTER_IP}" -P "/usr/share/cups/model/Zebra${PRINTER_NAME}Printer.ppd"

echo "Starting FastAPI server..."
cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000