#!/usr/bin/env bash
# Setup (re-runnable): containers -> databases/users -> schema + dummy data.
set -e
cd "$(dirname "$0")"
docker compose up -d
python3 -m lab.provision
python3 -m lab.seed
echo "Setup complete. Start the apps with ./run.sh"
