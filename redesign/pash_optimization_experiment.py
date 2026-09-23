#!/usr/bin/env python3
"""PASH optimization experiment: heuristic PASH-cap vs optimization-based PASH-opt.

Stage B of the execution plan: reformulate PASH from a capped exponential
heuristic into an auditable risk-control optimization problem.

Objective:
    min_p  lambda * sum_d w_d sum_{k in A_{m-d}} p_k
         + (1-lambda) * max_{|J|=S} sum_{k in J} p_k
    s.t.  0 <= p_k <= p_max
          sum_k p_k = S

The first term penalises expected short-delay follower collision.
The second term penalises the maximum probability mass a candidate-aware
jammer can capture.  p_max caps the per-bin predictability.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from advanced_experiment import (
    AdvancedConfig,
    capped_inclusion_probs,
    lag_collision,
    recent_counts,
    systematic_sample_from_inclusion_probs,
)
from fair_grid_sim import seeded_rng


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "pash_opt"
FIGURE_DIR = ROOT / "figures" / "diagnostics"
REPORT = ROOT / "docs" / "experiments" / "pash_optimization_results.md"
SMOKE_RESULT_DIR = ROOT / "tmp" / "smoke-pash-opt" / "results"
SMOKE_FIGURE_DIR = ROOT / "tmp" / "smoke-pash-opt" / "figures"
SMOKE_REPORT = ROOT / "tmp" / "smoke-pash-opt" / "pash_optimization_results.md"


@dataclass(frozen=True)
class OptConfig:
    n_phys: int = 512
    n_active: int = 64
    n_sym: int = 32
    max_delay: int = 6
    seed: int = 20260607
    memory: int = 6
    p_max: float = 0.15
    alpha: float = 1.4
    floor: float = 0.20
    opt_iters: int = 500
    lam_values: Tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)


# ── probability solvers ────────────────────────────────────────────────


def compute_cost_vector(
    history: Sequence[np.ndarray], n_phys: int, max_delay: int, beta: float = 0.5
) -> np.ndarray:
    """c_k = sum_{d=1}^{D} w_d * I(k in A_{m-d})  with  w_d = exp(-beta*(d-1))."""
    costs = np.zeros(n_phys)
    if not history:
        return costs
    for d_idx, past_set in enumerate(reversed(history[-max_delay:])):
        d = d_idx + 1
        w = np.exp(-beta * (d - 1))
        costs[past_set.astype(int)] += w
    return costs


def project_capped_simplex(v: np.ndarray, S: int, p_max: float) -> np.ndarray:
    """Project v onto {0 <= p_k <= p_max, sum_k p_k = S} via bisection."""
    v = np.asarray(v, dtype=float)
    lo = float(v.min() - S)
    hi = float(v.max())
    for _ in range(80):
        mid = (lo + hi) / 2
        p = np.clip(v - mid, 0, p_max)
        total = float(p.sum())
        if abs(total - S) < 1e-10:
            break
        if total > S:
            lo = mid
        else:
            hi = mid
    return np.clip(v - hi, 0, p_max)


def pash_opt_probs(
    history: Sequence[np.ndarray],
    cfg: OptConfig,
    lam: float,
) -> Tuple[np.ndarray, float]:
    """Solve PASH-opt via projected subgradient descent.

    Returns (p_k, final_objective_value).
    """
    costs = compute_cost_vector(history, cfg.n_phys, cfg.max_delay)
    if not history:
        p = np.full(cfg.n_phys, cfg.n_active / cfg.n_phys)
        return p, float(np.dot(costs, p))

    # Initialise at PASH-cap heuristic for warm start
    counts = recent_counts(history, cfg.memory, cfg.n_phys)
    raw = cfg.floor + np.exp(-cfg.alpha * counts)
    p = capped_inclusion_probs(raw, cfg.n_active, cfg.p_max)

    step0 = 0.5 / cfg.n_phys
    best_p = p.copy()
    best_obj = float("inf")

    for t in range(cfg.opt_iters):
        # subgradient: lambda * costs + (1-lambda) * indicator(top_S)
        top_S = np.argpartition(p, -cfg.n_active)[-cfg.n_active:]
        grad = lam * costs + (1 - lam) * np.isin(
            np.arange(cfg.n_phys), top_S
        ).astype(float)

        step = step0 / np.sqrt(float(t + 1))
        v = p - step * grad
        p = project_capped_simplex(v, cfg.n_active, cfg.p_max)

        obj = lam * float(np.dot(costs, p)) + (1 - lam) * float(
            np.sum(np.sort(p)[-cfg.n_active:])
        )
        if obj < best_obj:
            best_obj = obj
            best_p = p.copy()

    return best_p, best_obj


def pash_cap_probs(
    history: Sequence[np.ndarray], cfg: OptConfig
) -> np.ndarray:
    """Current heuristic PASH-cap inclusion probabilities."""
    counts = recent_counts(history, cfg.memory, cfg.n_phys)
    raw = cfg.floor + np.exp(-cfg.alpha * counts)
    return capped_inclusion_probs(raw, cfg.n_active, cfg.p_max)


# ── sampling ───────────────────────────────────────────────────────────


def sample_from_probs(
    probs: np.ndarray, n_phys: int, n_active: int, rng: np.random.Generator
) -> np.ndarray:
    """Sample n_active distinct bins with inclusion probabilities probs."""
    if probs.size != n_phys or not np.isclose(np.sum(probs), n_active, atol=1e-9):
        raise ValueError("Probability vector does not match the requested fixed-size sample")
    return systematic_sample_from_inclusion_probs(probs, rng)


def generate_sequence(
    probs_fn,
    cfg: OptConfig,
    rng: np.random.Generator,
    desc: str = "",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate a hopping pattern sequence."""
    history: List[np.ndarray] = []
    pattern = np.empty((cfg.n_sym, cfg.n_active), dtype=np.int32)
    probs_mat = np.empty((cfg.n_sym, cfg.n_phys), dtype=float)
    candidate_collision = np.zeros(cfg.n_sym)
    sym_iter = tqdm(range(cfg.n_sym), desc=desc, leave=False, unit="sym") if desc else range(cfg.n_sym)
    for m in sym_iter:
        pred = probs_fn(history)
        chosen = sample_from_probs(pred, cfg.n_phys, cfg.n_active, rng)
        jammer = np.argsort(pred)[-cfg.n_active:]
        pattern[m] = chosen
        probs_mat[m] = pred
        candidate_collision[m] = len(np.intersect1d(chosen, jammer)) / cfg.n_active
        history.append(chosen)
    return pattern, probs_mat, candidate_collision


# ── experiment runner ──────────────────────────────────────────────────


def run_structural(profile: str, cfg: OptConfig, checkpoint_dir: Path | None = None) -> List[Dict[str, object]]:
    """Structural comparison of PASH-cap vs PASH-opt variants.

    If checkpoint_dir is provided, saves per-seed intermediate results after
    every seed and resumes on restart.
    """
    max_lag = 12
    seeds = list(range(3 if profile == "smoke" else 20))
    n_sym = 600 if profile == "smoke" else 3000
    scfg = OptConfig(**{**asdict(cfg), "n_sym": n_sym})

    methods: List[Tuple[str, str, object]] = [
        ("random", "Random", lambda h: np.full(scfg.n_phys, scfg.n_active / scfg.n_phys)),
        (
            "pash_cap",
            "PASH-cap (heuristic)",
            lambda h: pash_cap_probs(h, scfg),
        ),
    ]
    for lam in scfg.lam_values:
        methods.append(
            (
                f"pash_opt_{lam:.2f}",
                f"PASH-opt $\\lambda={lam:.2f}$",
                lambda h, lam=lam: pash_opt_probs(h, scfg, lam)[0],
            )
        )

    # Load per-seed checkpoints
    completed: Dict[str, Dict[int, dict]] = {}  # method -> {seed: lag_runs_row, ...}
    if checkpoint_dir:
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        for key, _, _ in methods:
            cp_file = checkpoint_dir / f"{key}.json"
            if cp_file.exists():
                try:
                    completed[key] = {}
                    data = json.loads(cp_file.read_text(encoding="utf-8"))
                    for seed_str, val in data.items():
                        completed[key][int(seed_str)] = val
                    tqdm.write(f"  Checkpoint: {key} has {len(completed[key])} seeds saved")
                except Exception:
                    completed[key] = {}

    rows: List[Dict[str, object]] = []
    method_pbar = tqdm(methods, desc="Methods", unit="method", position=0)
    for key, label, probs_fn in method_pbar:
        method_pbar.set_postfix_str(label[:30])
        done = completed.get(key, {})
        pending_seeds = [s for s in seeds if s not in done]
        if not pending_seeds:
            tqdm.write(f"  {key:20s} all {len(seeds)} seeds cached, skipping")

        # Restore cached seed results
        lag_runs = [done[s]["lag_runs"] for s in seeds if s in done]
        candidate_runs = [done[s]["candidate"] for s in seeds if s in done]
        usage_cvs = [done[s]["usage_cv"] for s in seeds if s in done]
        max_probs = [done[s]["max_prob"] for s in seeds if s in done]
        top_mass = [done[s]["top_mass"] for s in seeds if s in done]
        entropies = [done[s]["entropy"] for s in seeds if s in done]

        seed_iter = tqdm(pending_seeds, desc=f"  Seeds", leave=False, unit="seed", position=1)
        for seed in seed_iter:
            rng = seeded_rng(scfg.seed, "pash-opt", key, seed)
            seed_desc = f"  {label} seed={seed}"
            pattern, probs_mat, cc = generate_sequence(probs_fn, scfg, rng,
                                                       desc=seed_desc if scfg.n_sym <= 1000 else "")
            lag_vals = [lag_collision(pattern, lag, scfg.n_active) for lag in range(1, max_lag + 1)]
            lag_runs.append(lag_vals)
            c_val = float(np.mean(cc))
            candidate_runs.append(c_val)
            counts = np.bincount(pattern.reshape(-1), minlength=scfg.n_phys)
            cv_val = float(counts.std() / counts.mean())
            usage_cvs.append(cv_val)
            mp_val = float(np.mean(np.max(probs_mat, axis=1)))
            max_probs.append(mp_val)
            sorted_probs = np.sort(probs_mat, axis=1)
            tm_val = float(np.mean(np.sum(sorted_probs[:, -scfg.n_active:], axis=1) / scfg.n_active))
            top_mass.append(tm_val)
            ent_val = -np.log(max(mp_val, 1e-12))
            entropies.append(ent_val)

            sc = float(np.mean(lag_vals[:2]))
            risk = max(float(np.mean(lag_vals)), c_val)
            tqdm.write(f"  {key:20s} seed={seed:2d} short={sc:.4f} risk={risk:.4f}")

            # Save checkpoint
            if checkpoint_dir:
                done[seed] = {"lag_runs": lag_vals, "candidate": c_val, "usage_cv": cv_val,
                              "max_prob": mp_val, "top_mass": tm_val, "entropy": ent_val}
                cp_file = checkpoint_dir / f"{key}.json"
                cp_file.write_text(json.dumps({str(s): v for s, v in done.items()}), encoding="utf-8")

        values = np.asarray(lag_runs)
        mean_lags = values.mean(axis=0)
        short_mean = float(np.mean(mean_lags[:2]))
        worst_idx = int(np.argmax(mean_lags))
        rows.append(
            {
                "method": key,
                "label": label,
                "short_delay_collision": short_mean,
                "worst_lag": worst_idx + 1,
                "worst_lag_collision": float(mean_lags[worst_idx]),
                "candidate_collision": float(np.mean(candidate_runs)),
                "usage_cv": float(np.mean(usage_cvs)),
                "max_inclusion_prob": float(np.mean(max_probs)),
                "top_s_mass_fraction": float(np.mean(top_mass)),
                "min_entropy_approx": float(np.mean(entropies)),
                **{f"lag_{lag}": float(mean_lags[lag - 1]) for lag in range(1, max_lag + 1)},
            }
        )
    return rows


# ── output ─────────────────────────────────────────────────────────────


def save_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path: Path) -> List[Dict[str, object]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def plot_comparison(rows: List[Dict[str, object]], figure_dir: Path) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 3.0), constrained_layout=True)

    cfg_text = "$N{=}512,\\,S{=}64,\\,M{=}32,\\,p_{\\max}{=}0.15$"
    fig.text(0.5, 0.01, cfg_text, ha="center", fontsize=7, color="#555555")

    # Separate opt, cap, random
    cap_row = next(r for r in rows if r["method"] == "pash_cap")
    rand_row = next(r for r in rows if r["method"] == "random")
    opt_rows = [r for r in rows if r["method"].startswith("pash_opt_")]

    # (a) Tradeoff frontier: short-delay vs candidate-aware
    lams = [float(r["method"].split("_")[-1]) for r in opt_rows]
    short_vals = [r["short_delay_collision"] for r in opt_rows]
    cand_vals = [r["candidate_collision"] for r in opt_rows]

    sc = axes[0].scatter(short_vals, cand_vals, c=lams, cmap="coolwarm", s=80, edgecolors="black", linewidth=0.5)
    axes[0].scatter(
        cap_row["short_delay_collision"],
        cap_row["candidate_collision"],
        marker="s", s=100, color="#F0E442", edgecolors="black", zorder=5, label="PASH-cap"
    )
    axes[0].scatter(
        rand_row["short_delay_collision"],
        rand_row["candidate_collision"],
        marker="D", s=60, color="#222222", zorder=5, label="Random"
    )
    for r in opt_rows:
        lam = float(r["method"].split("_")[-1])
        axes[0].annotate(f"$\\lambda={lam:.2f}$", (r["short_delay_collision"], r["candidate_collision"]),
                         xytext=(4, 4), textcoords="offset points", fontsize=6)
    axes[0].set_xlabel("Short-delay collision ($d=1,2$)")
    axes[0].set_ylabel("Candidate-aware collision")
    axes[0].set_title("(a) Risk tradeoff frontier")
    axes[0].grid(True, linestyle=":", linewidth=0.55)
    axes[0].legend(frameon=False, fontsize=7)
    fig.colorbar(sc, ax=axes[0], label="$\\lambda$")

    # (b) Lag spectrum comparison
    lags = np.arange(1, 13)
    axes[1].plot(lags, [cap_row[f"lag_{lag}"] for lag in lags], "s-", color="#F0E442", label="PASH-cap")
    axes[1].plot(lags, [rand_row[f"lag_{lag}"] for lag in lags], "D--", color="#222222", label="Random")
    # best and worst opt
    if opt_rows:
        best_opt = min(opt_rows, key=lambda r: max(r["worst_lag_collision"], r["candidate_collision"]))
        worst_opt = max(opt_rows, key=lambda r: max(r["worst_lag_collision"], r["candidate_collision"]))
        axes[1].plot(lags, [best_opt[f"lag_{lag}"] for lag in lags], "o-", color="#0072B2", label=best_opt["label"])
        if best_opt is not worst_opt:
            axes[1].plot(lags, [worst_opt[f"lag_{lag}"] for lag in lags], "o-", color="#D55E00", alpha=0.6, label=worst_opt["label"])
    axes[1].axhline(64 / 512, color="black", linestyle=":", label="$S/N$")
    axes[1].set_xlabel("Follower delay $d$")
    axes[1].set_ylabel("Collision rate")
    axes[1].set_title("(b) Delay-collision spectrum")
    axes[1].grid(True, linestyle=":", linewidth=0.55)
    axes[1].legend(frameon=False, fontsize=6)

    for ext in ("pdf", "png"):
        fig.savefig(figure_dir / f"fig9_pash_optimization.{ext}", dpi=300)
    plt.close(fig)


def write_report(rows: List[Dict[str, object]], cfg: OptConfig, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    cap_row = next(r for r in rows if r["method"] == "pash_cap")
    rand_row = next(r for r in rows if r["method"] == "random")
    opt_rows = [r for r in rows if r["method"].startswith("pash_opt_")]

    lines = [
        "# PASH Optimization Experiment Results",
        "",
        f"Config: N={cfg.n_phys}, S={cfg.n_active}, M={cfg.n_sym}, p_max={cfg.p_max}.",
        "",
        "## Methods",
        "",
        "- **Random**: uniform inclusion probability, no history awareness.",
        "- **PASH-cap**: capped exponential heuristic (alpha={:.2f}, floor={:.2f}, cap={:.2f}).".format(cfg.alpha, cfg.floor, cfg.p_max),
        "- **PASH-opt**: projected subgradient descent solving "
        "min_p lambda * E[short-delay collision] + (1-lambda) * max_{|J|=S} sum_{k in J} p_k "
        "s.t. 0 <= p_k <= p_max, sum_k p_k = S.",
        "",
        "## Structural results",
        "",
        "| Method | short-delay | worst-lag | candidate | usage CV | max incl prob | top-S mass | min-entropy approx |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['label']} | {row['short_delay_collision']:.3f} | "
            f"{row['worst_lag_collision']:.3f} (d={row['worst_lag']}) | "
            f"{row['candidate_collision']:.3f} | {row['usage_cv']:.4f} | "
            f"{row['max_inclusion_prob']:.3f} | {row['top_s_mass_fraction']:.3f} | "
            f"{row['min_entropy_approx']:.2f} |"
        )

    # Acceptance criteria check
    opt_best = min(opt_rows, key=lambda r: max(r["worst_lag_collision"], r["candidate_collision"])) if opt_rows else None
    lines.append("")
    lines.append("## Acceptance criteria check")
    lines.append("")
    if opt_best:
        sc_ok = opt_best["short_delay_collision"] <= cap_row["short_delay_collision"] + 0.005
        ca_ok = opt_best["candidate_collision"] <= cap_row["candidate_collision"] + 0.005
        wl_ok = opt_best["worst_lag_collision"] <= cap_row["worst_lag_collision"] + 0.005
        risk_opt = max(opt_best["worst_lag_collision"], opt_best["candidate_collision"])
        risk_cap = max(cap_row["worst_lag_collision"], cap_row["candidate_collision"])

        lines.append(f"Best PASH-opt: {opt_best['label']}")
        lines.append(f"  risk = {risk_opt:.4f} (cap risk = {risk_cap:.4f})")
        lines.append("")
        lines.append("| Criterion | Result | Detail |")
        lines.append("|---|---|---|")
        lines.append(f"| 1. Same short-delay, lower candidate | {'PASS' if ca_ok else 'FAIL'} | opt candidate={opt_best['candidate_collision']:.4f} vs cap={cap_row['candidate_collision']:.4f} |")
        lines.append(f"| 2. Same candidate, lower short-delay | {'PASS' if sc_ok else 'FAIL'} | opt short={opt_best['short_delay_collision']:.4f} vs cap={cap_row['short_delay_collision']:.4f} |")
        lines.append(f"| 3. Flatter lag spectrum | {'PASS' if wl_ok else 'FAIL'} | opt worst-lag={opt_best['worst_lag_collision']:.4f} vs cap={cap_row['worst_lag_collision']:.4f} |")

        if ca_ok or sc_ok or wl_ok:
            lines.append("")
            lines.append("**At least one criterion met — PASH-opt is worth including in the main paper.**")
        else:
            lines.append("")
            lines.append("**No criterion met — keep PASH-opt as future work / appendix only.**")
    else:
        lines.append("No PASH-opt rows available for comparison.")

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- lambda=0: pure candidate-aware minimisation (minimise max jammer-capturable mass).",
        "- lambda=1: pure short-delay follower avoidance.",
        "- Intermediate lambda values trace the Pareto frontier between these two objectives.",
        "- PASH-cap is a single heuristic point on this frontier.",
        "- If PASH-opt achieves lower candidate-aware collision at the same short-delay cost,",
        "  it demonstrates that the exponential heuristic is not Pareto-optimal.",
        "",
        "## Outputs",
        "",
        "- Data: `results/pash_opt/summary.csv`.",
        "- Figure: `figures/paper/fig9_pash_optimization.pdf`.",
        "- Smoke outputs use `tmp/smoke-pash-opt/`.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── main ───────────────────────────────────────────────────────────────


def run(profile: str, plot_only: bool = False) -> None:
    cfg = OptConfig()
    if profile == "smoke":
        result_dir = SMOKE_RESULT_DIR
        figure_dir = SMOKE_FIGURE_DIR
        report_path = SMOKE_REPORT
    else:
        result_dir = RESULT_DIR
        figure_dir = FIGURE_DIR
        report_path = REPORT

    if plot_only:
        rows = load_csv(result_dir / "summary.csv")
        print(f"Loaded {len(rows)} rows from {result_dir}")
    else:
        result_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_dir = result_dir / ".checkpoints"
        started = time.perf_counter()
        rows = run_structural(profile, cfg, checkpoint_dir=checkpoint_dir)
        elapsed = time.perf_counter() - started
        print(f"Structural experiment completed in {elapsed:.0f}s, {len(rows)} methods")
        save_csv(result_dir / "summary.csv", rows)
        (result_dir / "config.json").write_text(
            json.dumps({"profile": profile, "config": asdict(cfg)}, indent=2),
            encoding="utf-8",
        )
    plot_comparison(rows, figure_dir)
    write_report(rows, cfg, report_path)
    print(f"Saved results to {result_dir}")
    print(f"Saved figure to {figure_dir}")
    print(f"Saved report to {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["smoke", "paper"], nargs="?", default="smoke")
    parser.add_argument("--plot-only", action="store_true", help="Skip experiment, replot from existing CSV data")
    args = parser.parse_args()
    run(args.profile, plot_only=args.plot_only)


if __name__ == "__main__":
    main()
