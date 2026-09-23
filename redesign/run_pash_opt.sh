#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROFILE=${1:-paper}

"$ROOT/.venv/bin/python" "$ROOT/redesign/pash_optimization_experiment.py" "$PROFILE"
