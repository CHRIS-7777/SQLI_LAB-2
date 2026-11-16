#!/usr/bin/env bash
cd "$(dirname "$0")"
docker compose up -d >/dev/null 2>&1
echo "Serving on http://$(hostname -I | awk '{print $1}'):5050/  (Ctrl+C to stop)"
exec python3 -m lab
