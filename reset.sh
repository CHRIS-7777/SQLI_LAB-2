#!/usr/bin/env bash
# Restore every database to its original state (use if data gets damaged).
cd "$(dirname "$0")"
python3 -m lab.seed
