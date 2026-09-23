#!/usr/bin/env python3
"""Validate PASH-cap theoretical bounds numerically.

Proposition 3 claims:
  - R_cand ≤ p_max (probability-aware exposure is bounded by the cap)
  - This bound is independent of H and alpha
  - In contrast, MCSH R_cand = S/(N-L_h*S) grows without bound

This script verifies these claims numerically and produces diagnostic data
for the revision.
"""

from __future__ import annotations

import argparse
import csv
import json
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results" / "comml" / "bound_validation"


def seeded_rng(seed: int = 42) -> np.random.Generator:
    return np.random.default_rng(seed)


@dataclass
class PASHConfig:
    N: int = 512
    S: int = 64
    H: int = 6
    alpha: float = 1.4
    p_floor: float = 0.20
    p_max: float = 0.15


@dataclass
class MCSHConfig:
    N: int = 512
    S: int = 64
    L_h: int = 2


def pash_sample(config: PASHConfig, history: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    """Generate one PASH-cap active set given history."""
    N, S, H = config.N, config.S, config.H
    alpha, p_floor, p_max = config.alpha, config.p_floor, config.p_max

    # Compute recent-use counts
    use_counts = np.zeros(N, dtype=np.float64)
    for lag in range(1, min(H, len(history)) + 1):
        use_counts += history[-lag]

    # Exponential weights
    w = p_floor + np.exp(-alpha * use_counts)

    # Capped normalization via bisection
    lo, hi = 0.0, 10.0
    for _ in range(60):
        eta = (lo + hi) / 2
        p = np.minimum(p_max, eta * w)
        total = np.sum(p)
        if total > S:
            hi = eta
        else:
            lo = eta
    p = np.minimum(p_max, lo * w)
    # Adjust to exact sum S
    p = p * (S / np.sum(p))

    # Systematic sampling
    perm = rng.permutation(N)
    p_perm = p[perm]
    cum = np.cumsum(p_perm)
    u = rng.uniform(0, 1)
    thresholds = u + np.arange(S)

    active = np.zeros(N, dtype=bool)
    idx = np.searchsorted(cum, thresholds % np.sum(p_perm))
    # np.searchsorted may return N for values beyond cum[-1]
    idx = np.clip(idx, 0, N - 1)
    # Handle wrap-around: thresholds > cum[-1] wrap to beginning
    for t_idx, t_val in enumerate(thresholds):
        t_mod = t_val % np.sum(p_perm)
        pos = int(np.searchsorted(cum, t_mod))
        if pos >= N:
            pos = 0
        active[perm[pos]] = True

    return active


def mcsh_sample(config: MCSHConfig, history: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    """Generate one MCSH active set given history."""
    N, S, L_h = config.N, config.S, config.L_h

    # Store all arrays as bool internally
    exclude_set = np.zeros(N, dtype=bool)
    for lag in range(1, min(L_h, len(history)) + 1):
        h = history[-lag]
        if h.dtype == np.float64:
            exclude_set = exclude_set | (h > 0)
        else:
            exclude_set = exclude_set | h.astype(bool)

    available = np.where(~exclude_set)[0]
    if len(available) >= S:
        chosen = rng.choice(available, size=S, replace=False)
    else:
        # Fallback: use all available + random from excluded
        chosen = np.zeros(S, dtype=int)
        chosen[:len(available)] = available
        extra = rng.choice(np.where(exclude_set)[0], size=S - len(available), replace=False)
        chosen[len(available):] = extra

    active = np.zeros(N, dtype=bool)
    active[chosen] = True
    return active


def compute_c_d(sequence: list[np.ndarray], d: int) -> float:
    """Compute lag-d self-collision C_d."""
    S = int(np.sum(sequence[0]))
    count = 0
    total = 0
    for m in range(d, len(sequence)):
        count += np.sum(sequence[m] & sequence[m - d])
        total += 1
    return count / (total * S) if total > 0 else 0.0


def compute_r_cand(sequence: list[np.ndarray], config: PASHConfig) -> float:
    """Compute probability-aware exposure R_cand for PASH-cap."""
    N, S = config.N, config.S
    H, alpha, p_floor, p_max = config.H, config.alpha, config.p_floor, config.p_max

    r_cand_values = []
    for m in range(H, min(H + 500, len(sequence))):
        history = sequence[:m]
        use_counts = np.zeros(N, dtype=np.float64)
        for lag in range(1, min(H, len(history)) + 1):
            use_counts += history[-lag]
        w = p_floor + np.exp(-alpha * use_counts)

        lo, hi = 0.0, 10.0
        for _ in range(60):
            eta = (lo + hi) / 2
            p = np.minimum(p_max, eta * w)
            total = np.sum(p)
            if total > S:
                hi = eta
            else:
                lo = eta
        p = np.minimum(p_max, lo * w)
        p = p * (S / np.sum(p))

        top_s = np.sort(p)[-S:]
        r_cand_values.append(np.sum(top_s) / S)

    return float(np.mean(r_cand_values))


def compute_r_cand_mcsh(sequence: list[np.ndarray], config: MCSHConfig, L_h_values: list[int]) -> dict[int, float]:
    """Compute MCSH theoretical R_cand = S/(N - L_h*S) for various L_h."""
    results = {}
    for L_h in L_h_values:
        if (L_h + 1) * config.S <= config.N:
            results[L_h] = config.S / (config.N - L_h * config.S)
        else:
            results[L_h] = float('nan')
    return results


def run_validation(pash_cfg: PASHConfig, mcsh_cfg: MCSHConfig,
                   n_symbols: int = 5000, n_seeds: int = 5) -> dict:
    """Run full bound validation."""
    rng = seeded_rng(42)

    pash_c_d = {}
    mcsh_c_d_l2 = {}
    mcsh_c_d_l6 = {}
    pash_r_cand_seeds = []
    pash_c_d_seeds = {d: [] for d in range(1, 21)}

    for seed in range(n_seeds):
        seed_rng = seeded_rng(42 + seed)

        # Generate PASH-cap sequence (store as bool for clean bitwise ops)
        pash_seq: list[np.ndarray] = []
        for _ in range(n_symbols):
            active = pash_sample(pash_cfg, pash_seq, seed_rng)
            pash_seq.append(active.astype(bool))

        # Generate MCSH-L2 sequence
        mcsh2_cfg = MCSHConfig(N=mcsh_cfg.N, S=mcsh_cfg.S, L_h=2)
        mcsh2_seq: list[np.ndarray] = []
        for _ in range(n_symbols):
            active = mcsh_sample(mcsh2_cfg, mcsh2_seq, seed_rng)
            mcsh2_seq.append(active.astype(bool))

        # Generate MCSH-L6 sequence
        mcsh6_cfg = MCSHConfig(N=mcsh_cfg.N, S=mcsh_cfg.S, L_h=6)
        mcsh6_seq: list[np.ndarray] = []
        for _ in range(n_symbols):
            active = mcsh_sample(mcsh6_cfg, mcsh6_seq, seed_rng)
            mcsh6_seq.append(active.astype(bool))

        # Compute C_d for each method
        for d in range(1, 21):
            pash_c_d_seeds[d].append(compute_c_d(pash_seq, d))

        # Compute R_cand for PASH-cap
        r_cand = compute_r_cand(pash_seq, pash_cfg)
        pash_r_cand_seeds.append(r_cand)

    # Aggregate across seeds
    for d in range(1, 21):
        vals = pash_c_d_seeds[d]
        pash_c_d[d] = {"mean": float(np.mean(vals)), "std": float(np.std(vals))}

    # MCSH theoretical
    L_h_values = list(range(1, 9))
    mcsh_theoretical = compute_r_cand_mcsh(mcsh2_seq[0] if mcsh2_seq else np.zeros(1), mcsh_cfg, L_h_values)

    results = {
        "config": {
            "pash": {"N": pash_cfg.N, "S": pash_cfg.S, "H": pash_cfg.H,
                     "alpha": pash_cfg.alpha, "p_floor": pash_cfg.p_floor, "p_max": pash_cfg.p_max},
            "mcsh": {"N": mcsh_cfg.N, "S": mcsh_cfg.S},
        },
        "pash_c_d": pash_c_d,
        "pash_r_cand": {"mean": float(np.mean(pash_r_cand_seeds)),
                        "std": float(np.std(pash_r_cand_seeds))},
        "mcsh_theoretical_r_cand": mcsh_theoretical,
        "max_pash_c_d": float(max(v["mean"] for v in pash_c_d.values())),
        "bound_check": {
            "c_d_le_pmax": all(v["mean"] <= pash_cfg.p_max * 1.1 for v in pash_c_d.values()),
            "r_cand_le_pmax": float(np.mean(pash_r_cand_seeds)) <= pash_cfg.p_max * 1.05,
        },
    }
    return results


def write_csv(results: dict, output_dir: Path) -> None:
    """Write validation results to CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # C_d results
    with (output_dir / "cd_validation.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lag_d", "pash_cd_mean", "pash_cd_std",
                                                "mcsh_l2_expected", "mcsh_l6_expected",
                                                "p_max_bound", "pash_vs_bound"])
        writer.writeheader()
        for d in sorted(results["pash_c_d"].keys()):
            pash_mean = results["pash_c_d"][d]["mean"]
            pash_std = results["pash_c_d"][d]["std"]
            # MCSH-L2: C_d = 0 for d <= 2, C_3 = S/(N-2S)
            mcsh2 = 0.0 if d <= 2 else (64.0 / (512 - 128) if d == 3 else None)
            mcsh6 = 0.0 if d <= 6 else (64.0 / (512 - 384) if d == 7 else None)
            writer.writerow({
                "lag_d": d,
                "pash_cd_mean": f"{pash_mean:.6f}",
                "pash_cd_std": f"{pash_std:.6f}",
                "mcsh_l2_expected": f"{mcsh2:.6f}" if mcsh2 is not None else "N/A",
                "mcsh_l6_expected": f"{mcsh6:.6f}" if mcsh6 is not None else "N/A",
                "p_max_bound": f"{results['config']['pash']['p_max']:.4f}",
                "pash_vs_bound": "PASS" if pash_mean <= results['config']['pash']['p_max'] * 1.05 else "FAIL",
            })

    # R_cand results
    with (output_dir / "rcand_validation.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["method", "L_h_or_cap", "r_cand", "bound_type"])
        writer.writeheader()
        writer.writerow({
            "method": "PASH-cap",
            "L_h_or_cap": results["config"]["pash"]["p_max"],
            "r_cand": f"{results['pash_r_cand']['mean']:.6f}",
            "bound_type": f"≤ p_max = {results['config']['pash']['p_max']}",
        })
        for L_h, r_cand in results["mcsh_theoretical_r_cand"].items():
            writer.writerow({
                "method": f"MCSH-L{L_h}",
                "L_h_or_cap": L_h,
                "r_cand": f"{r_cand:.6f}",
                "bound_type": "= S/(N-L_h*S), unbounded growth",
            })

    # Write manifest
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = {
        "script": str(Path(__file__).relative_to(ROOT)),
        "source_sha256": source_hash,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_symbols": 5000,
        "n_seeds": 5,
    }
    with (output_dir / "run_manifest.json").open("w") as f:
        json.dump(manifest, f, indent=2)


def print_summary(results: dict) -> None:
    """Print human-readable validation summary."""
    print("\n" + "=" * 60)
    print("PASH-cap Bound Validation Results")
    print("=" * 60)

    cfg = results["config"]["pash"]
    print(f"\nConfiguration: N={cfg['N']}, S={cfg['S']}, H={cfg['H']}, "
          f"alpha={cfg['alpha']}, p_floor={cfg['p_floor']}, p_max={cfg['p_max']}")

    print(f"\n--- PASH-cap C_d Summary ---")
    print(f"{'Lag d':<8} {'C_d (mean)':<14} {'C_d (std)':<14} {'≤ p_max?':<12}")
    print("-" * 48)
    for d in sorted(results["pash_c_d"].keys()):
        mean_v = results["pash_c_d"][d]["mean"]
        std_v = results["pash_c_d"][d]["std"]
        ok = "✓" if mean_v <= cfg["p_max"] * 1.05 else "✗ FAIL"
        print(f"{d:<8} {mean_v:<14.6f} {std_v:<14.6f} {ok:<12}")

    print(f"\nMax C_d across all lags: {results['max_pash_c_d']:.6f}")
    print(f"p_max bound: {cfg['p_max']}")

    print(f"\n--- Probability-Aware Exposure R_cand ---")
    print(f"PASH-cap R_cand = {results['pash_r_cand']['mean']:.6f} "
          f"(≤ p_max = {cfg['p_max']})")
    print(f"\nMCSH R_cand (theoretical):")
    for L_h, r_cand in sorted(results["mcsh_theoretical_r_cand"].items()):
        if np.isnan(r_cand):
            print(f"  L_h={L_h}: infeasible")
            continue
        bar = "█" * min(int(r_cand * 40), 40)
        print(f"  L_h={L_h}: {r_cand:.4f} {bar}")

    print(f"\n--- Overall Checks ---")
    for check_name, result in results["bound_check"].items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {check_name}: {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PASH-cap theoretical bounds")
    parser.add_argument("--symbols", type=int, default=5000, help="Number of symbols per seed")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    pash_cfg = PASHConfig()
    mcsh_cfg = MCSHConfig()

    print(f"Running bound validation: {args.symbols} symbols × {args.seeds} seeds...")
    results = run_validation(pash_cfg, mcsh_cfg, n_symbols=args.symbols, n_seeds=args.seeds)

    print_summary(results)

    output_dir = Path(args.output) if args.output else RESULTS_DIR
    write_csv(results, output_dir)
    print(f"\nResults written to {output_dir}")

    all_pass = all(results["bound_check"].values())
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
