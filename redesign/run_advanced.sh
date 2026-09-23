#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROFILE=${1:-paper}
PLOT_ONLY=${2:-}

if [ "$PLOT_ONLY" = "--plot-only" ]; then
    "$ROOT/.venv/bin/python" "$ROOT/redesign/advanced_experiment.py" --profile "$PROFILE" --plot-only
else
    "$ROOT/.venv/bin/python" "$ROOT/redesign/advanced_experiment.py" --profile "$PROFILE"
fi
