#!/usr/bin/env bash
# Stop DB containers (frees RAM). Data is kept. Stop the web app with Ctrl+C.
cd "$(dirname "$0")"
docker compose stop
