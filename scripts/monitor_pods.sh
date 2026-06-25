#!/bin/bash
# Weave eval pod monitor — delegates to monitor_pods.py for rich display
# Usage: bash scripts/monitor_pods.sh [--once]
exec python3 "$(dirname "$0")/monitor_pods.py" "$@"
