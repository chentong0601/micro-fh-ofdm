#!/usr/bin/env python3
"""Parameter sweep for predictability-aware soft hopping.

The advanced experiment already shows that a capped PASH rule can reduce the
lag spike and candidate-aware exposure created by hard MCSH exclusion.  This
script makes the parameter choice auditable: it sweeps alpha, floor, and cap,
then reports the best feasible design under short-delay collision constraints.
"""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from advanced_experiment import (
    AdvancedConfig,
    capped_inclusion_probs,
    lag_collision,
    recent_counts,
    systematic_sample_from_inclusion_probs,
)
from fair_grid_sim import seeded_rng


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "pash_sweep"
FIGURE_DIR = ROOT / "figures" / "paper"
REPORT = ROOT / "docs" / "experiments" / "pash_parameter_sweep_results.md"
SMOKE_RESULT_DIR = ROOT / "tmp" / "smoke-pash-sweep" / "results"
SMOKE_FIGURE_DIR = ROOT / "tmp" / "smoke-pash-sweep" / "figures"
SMOKE_REPORT = ROOT / "tmp" / "smoke-pash-sweep" / "pash_parameter_sweep_results.md"


def sweep_grid(profile: str) -> Tuple[Sequence[float], Sequence[float], Sequence[float]]:
    if profile == "smoke":
        return [0.8, 1.2, 1.4], [0.15, 0.20, 0.30], [0.13, 0.15, 0.18]
    return (
        [0.6, 0.8, 1.0, 1.2, 1.4, 1.8],
        [0.10, 0.20, 0.30, 0.40],
        [0.13, 0.14, 0.15, 0.16, 0.18],
    )


def profile_cfg(profile: str, base: AdvancedConfig) -> Tuple[AdvancedConfig, range]:
    if profile == "smoke":
        return AdvancedConfig(**{**asdict(base), "n_sym": 900}), range(4)
    return AdvancedConfig(**{**asdict(base), "n_sym": 2200}), range(8)


def pash_weights(
    history: Sequence[np.ndarray],
    cfg: AdvancedConfig,
    alpha: float,
    floor: float,
    cap: float,
    memory: int = 6,
) -> Tuple[np.ndarray, np.ndarray]:
    counts = recent_counts(history, memory, cfg.n_phys)
    raw = floor + np.exp(-alpha * counts)
    probs = capped_inclusion_probs(raw, cfg.n_active, cap)
    return probs.copy(), probs


def sample_pash(
    history: Sequence[np.ndarray],
    cfg: AdvancedConfig,
    rng: np.random.Generator,
    alpha: float,
    floor: float,
    cap: float,
) -> Tuple[np.ndarray, np.ndarray]:
    weights, probs = pash_weights(history, cfg, alpha, floor, cap)
    chosen = systematic_sample_from_inclusion_probs(probs, rng)
    return chosen, probs


def generate_pash_sequence(
    cfg: AdvancedConfig,
    rng: np.random.Generator,
    alpha: float,
    floor: float,
    cap: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    history: List[np.ndarray] = []
    pattern = np.empty((cfg.n_sym, cfg.n_active), dtype=np.int32)
    probs = np.empty((cfg.n_sym, cfg.n_phys), dtype=float)
    candidate_collision = np.zeros(cfg.n_sym)
    for m in range(cfg.n_sym):
        chosen, pred = sample_pash(history, cfg, rng, alpha, floor, cap)
        jammer = np.argsort(pred)[-cfg.n_active :]
        pattern[m] = chosen
        probs[m] = pred
        candidate_collision[m] = len(np.intersect1d(chosen, jammer)) / cfg.n_active
        history.append(chosen)
    return pattern, probs, candidate_collision


def summarize_candidate(
    cfg: AdvancedConfig,
    seeds: Iterable[int],
    alpha: float,
    floor: float,
    cap: float,
) -> Dict[str, object]:
    max_lag = 12
    lag_runs = []
    candidate_runs = []
    usage_cvs = []
    max_probs = []
    started = time.perf_counter()
    for seed in seeds:
        rng = seeded_rng(cfg.seed, "pash-sweep", alpha, floor, cap, seed)
        pattern, probs, candidate_collision = generate_pash_sequence(cfg, rng, alpha, floor, cap)
        lag_runs.append([lag_collision(pattern, lag, cfg.n_active) for lag in range(1, max_lag + 1)])
        candidate_runs.append(float(np.mean(candidate_collision)))
        counts = np.bincount(pattern.reshape(-1), minlength=cfg.n_phys)
        usage_cvs.append(float(counts.std() / counts.mean()))
        max_probs.append(float(np.mean(np.max(probs, axis=1))))

    lag_array = np.asarray(lag_runs)
    mean_lags = lag_array.mean(axis=0)
    short_delay = float(np.mean(mean_lags[:2]))
    worst_idx = int(np.argmax(mean_lags))
    candidate = float(np.mean(candidate_runs))
    worst = float(mean_lags[worst_idx])
    risk = max(worst, candidate)
    return {
        "alpha": alpha,
        "floor": floor,
        "cap": cap,
        "short_delay_collision": short_delay,
        "worst_lag": worst_idx + 1,
        "worst_lag_collision": worst,
        "candidate_collision": candidate,
        "risk_max_worst_or_candidate": risk,
        "usage_cv": float(np.mean(usage_cvs)),
        "max_inclusion_prob": float(np.mean(max_probs)),
        "elapsed_s": time.perf_counter() - started,
        **{f"lag_{lag}": float(mean_lags[lag - 1]) for lag in range(1, max_lag + 1)},
    }


def run_sweep(profile: str, cfg: AdvancedConfig) -> List[Dict[str, object]]:
    alphas, floors, caps = sweep_grid(profile)
    scfg, seeds = profile_cfg(profile, cfg)
    rows: List[Dict[str, object]] = []
    total = len(alphas) * len(floors) * len(caps)
    idx = 0
    for alpha in alphas:
        for floor in floors:
            for cap in caps:
                idx += 1
                row = summarize_candidate(scfg, seeds, alpha, floor, cap)
                rows.append(row)
                print(
                    f"[{idx:03d}/{total}] a={alpha:.2f} floor={floor:.2f} cap={cap:.2f} "
                    f"short={row['short_delay_collision']:.3f} "
                    f"risk={row['risk_max_worst_or_candidate']:.3f}",
                    flush=True,
                )
    rows.sort(key=lambda r: (r["risk_max_worst_or_candidate"], r["short_delay_collision"]))
    return rows


def save_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def feasible_rows(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return [
        row
        for row in rows
        if row["short_delay_collision"] <= 0.105
        and row["usage_cv"] <= 0.055
        and row["max_inclusion_prob"] <= row["cap"] + 1e-9
    ]


def plot_sweep(rows: List[Dict[str, object]], figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    feasible = feasible_rows(rows)
    best = feasible[0] if feasible else rows[0]
    current = min(
        rows,
        key=lambda r: abs(r["alpha"] - 1.4) + abs(r["floor"] - 0.20) + abs(r["cap"] - 0.15),
    )

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.8), constrained_layout=True)

    x = np.asarray([r["short_delay_collision"] for r in rows])
    y = np.asarray([r["candidate_collision"] for r in rows])
    color = np.asarray([r["risk_max_worst_or_candidate"] for r in rows])
    size = 18 + 180 * np.asarray([r["worst_lag_collision"] for r in rows])
    sc = axes[0].scatter(x, y, c=color, s=size, cmap="viridis", alpha=0.82, edgecolors="none")
    axes[0].axvline(0.105, color="#CC3311", linestyle=":", linewidth=1.0)
    axes[0].scatter(
        best["short_delay_collision"],
        best["candidate_collision"],
        marker="*",
        s=150,
        color="#D55E00",
        label="best feasible",
        zorder=5,
    )
    axes[0].scatter(
        current["short_delay_collision"],
        current["candidate_collision"],
        marker="X",
        s=80,
        color="#0072B2",
        label="current paper",
        zorder=5,
    )
    axes[0].set_xlabel("short-delay collision")
    axes[0].set_ylabel("candidate-aware collision")
    axes[0].set_title("(a) Feasible design frontier")
    axes[0].grid(True, linestyle=":", linewidth=0.55)
    axes[0].legend(frameon=False, fontsize=7)
    fig.colorbar(sc, ax=axes[0], label="max risk")

    lags = np.arange(1, 13)
    axes[1].plot(
        lags,
        [best[f"lag_{lag}"] for lag in lags],
        marker="o",
        color="#D55E00",
        label="best feasible",
    )
    axes[1].plot(
        lags,
        [current[f"lag_{lag}"] for lag in lags],
        marker="s",
        color="#0072B2",
        label="current paper",
    )
    axes[1].axhline(64 / 512, color="black", linestyle=":", label="$S/N$")
    axes[1].set_xlabel("follower delay")
    axes[1].set_ylabel("collision rate")
    axes[1].set_title("(b) Delay spectrum")
    axes[1].grid(True, linestyle=":", linewidth=0.55)
    axes[1].legend(frameon=False, fontsize=7)

    for ext in ("pdf", "png"):
        fig.savefig(figure_dir / f"fig8_pash_parameter_sweep.{ext}", dpi=300)
    plt.close(fig)


def write_report(path: Path, rows: List[Dict[str, object]], profile: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    feasible = feasible_rows(rows)
    best = feasible[0] if feasible else rows[0]
    current = min(
        rows,
        key=lambda r: abs(r["alpha"] - 1.4) + abs(r["floor"] - 0.20) + abs(r["cap"] - 0.15),
    )
    lines = [
        "# PASH Parameter Sweep Results",
        "",
        "## Research question",
        "",
        "Can the capped PASH parameters be selected by an auditable structural criterion rather than by a hand-tuned choice?",
        "",
        "## Design",
        "",
        "- Method: capped exponential PASH with memory 6.",
        "- Parameters: alpha, probability floor, and inclusion-probability cap.",
        "- Metrics: short-delay collision, worst-lag collision, candidate-aware collision, usage CV, and max inclusion probability.",
        "- Feasibility rule: short-delay collision <= 0.105, usage CV <= 0.055, and measured max inclusion probability respecting the cap.",
        "- Objective: minimize max(worst-lag collision, candidate-aware collision) among feasible candidates.",
        f"- Profile: `{profile}`.",
        "",
        "## Best feasible setting",
        "",
        (
            f"- alpha={best['alpha']:.2f}, floor={best['floor']:.2f}, cap={best['cap']:.2f}; "
            f"short-delay={best['short_delay_collision']:.4f}, "
            f"worst-lag d={int(best['worst_lag'])} collision={best['worst_lag_collision']:.4f}, "
            f"candidate-aware={best['candidate_collision']:.4f}, "
            f"risk={best['risk_max_worst_or_candidate']:.4f}, usage-CV={best['usage_cv']:.4f}."
        ),
        "",
        "## Current paper setting located in the sweep",
        "",
        (
            f"- alpha={current['alpha']:.2f}, floor={current['floor']:.2f}, cap={current['cap']:.2f}; "
            f"short-delay={current['short_delay_collision']:.4f}, "
            f"worst-lag d={int(current['worst_lag'])} collision={current['worst_lag_collision']:.4f}, "
            f"candidate-aware={current['candidate_collision']:.4f}, "
            f"risk={current['risk_max_worst_or_candidate']:.4f}, usage-CV={current['usage_cv']:.4f}."
        ),
        "",
        "## Interpretation",
        "",
        "This sweep turns the PASH-cap choice into a reproducible design point. If the best feasible point differs from the current paper setting, the next paper iteration should either update the PASH-cap parameterization or explicitly justify the more conservative choice.",
        "",
        "## Outputs",
        "",
        "- Data: `results/pash_sweep/summary.csv`.",
        "- Figure: `figures/paper/fig8_pash_parameter_sweep.pdf`.",
        "- Temporary smoke outputs use `tmp/smoke-pash-sweep/`.",
        "",
        "## Limitations",
        "",
        "The sweep is structural. It does not yet rerun coded BER/BLER for every candidate. The selected point should be validated in coded adversarial experiments before replacing the current paper setting.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["smoke", "paper"], nargs="?", default="smoke")
    args = parser.parse_args()

    result_dir = SMOKE_RESULT_DIR if args.profile == "smoke" else RESULT_DIR
    figure_dir = SMOKE_FIGURE_DIR if args.profile == "smoke" else FIGURE_DIR
    report = SMOKE_REPORT if args.profile == "smoke" else REPORT

    cfg = AdvancedConfig()
    rows = run_sweep(args.profile, cfg)
    save_csv(result_dir / "summary.csv", rows)
    plot_sweep(rows, figure_dir)
    write_report(report, rows, args.profile)
    print(f"Wrote {len(rows)} rows to {result_dir / 'summary.csv'}")
    print(f"Wrote report to {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
