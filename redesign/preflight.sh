#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MODE=${1:-quick}

case "$MODE" in
    quick)
        "$ROOT/.venv/bin/python" "$ROOT/run.py" quick
        ;;
    smoke)
        "$ROOT/.venv/bin/python" "$ROOT/run.py" smoke
        ;;
    full|preflight)
        "$ROOT/.venv/bin/python" "$ROOT/run.py" preflight
        ;;
    *)
        echo "Usage: sh redesign/preflight.sh [quick|smoke|full]" >&2
        exit 2
        ;;
esac
