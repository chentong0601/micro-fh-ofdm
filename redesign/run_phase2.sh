#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROFILE=${1:-paper}

if [ "$PROFILE" = "smoke" ]; then
    "$ROOT/.venv/bin/python" "$ROOT/redesign/innovation_sim.py" \
        --profile smoke --result-dir "$ROOT/tmp/innovation-smoke"
    exit 0
fi

"$ROOT/.venv/bin/python" "$ROOT/redesign/innovation_sim.py" --profile paper
"$ROOT/.venv/bin/python" "$ROOT/redesign/plot_innovation.py"
