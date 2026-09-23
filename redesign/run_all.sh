#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROFILE=${1:-paper}

if [ "$PROFILE" = "smoke" ]; then
    "$ROOT/.venv/bin/python" "$ROOT/redesign/fair_grid_sim.py" \
        --profile smoke --result-dir "$ROOT/tmp/smoke-results"
    exit 0
fi

"$ROOT/.venv/bin/python" "$ROOT/redesign/fair_grid_sim.py" --profile paper
"$ROOT/.venv/bin/python" "$ROOT/redesign/plot_results.py"
