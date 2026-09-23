#!/usr/bin/env python3
"""Epsilon-greedy online learning baseline for set-valued FH.

The transmitter maintains EMA collision scores per subcarrier and selects
subcarriers using epsilon-greedy (exploit = lowest collision scores).
After each symbol, it observes exact per-subcarrier collision and updates
EMA scores — same feedback quality the causal attacker enjoys.

This is an intentionally strong (best-case) learning baseline to stress-test
the open-loop PASH-cap argument: if online learning with perfect feedback
cannot outperform PASH-cap, the open-loop claim is robust.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "redesign"))

from advanced_experiment import (
    AdvancedConfig,
    bootstrap_ci,
    CausalLagState,
    jammer_sets,
    seeded_rng,
    wilson_interval,
)
from fair_grid_sim import conv_encode_k7, qpsk_mod, qpsk_soft
from innovation_sim import posterior_collision, viterbi_decode_weighted


def mixture_llrs(rx, v0, v1, prior):
    """Mixture log-likelihood ratios (imported from advanced_experiment)."""
    from advanced_experiment import mixture_llrs as _mlr
    return _mlr(rx, v0, v1, prior)


def viterbi_decode_llr(llrs):
    """Viterbi decode from LLRs (imported from advanced_experiment)."""
    from advanced_experiment import viterbi_decode_llr as _vdl
    return _vdl(llrs)


def run_baseline(
    threat: str = "causal_adaptive_lag",
    epsilon: float = 0.10,
    ema_alpha: float = 0.10,
    min_frames: int = 2000,
    max_frames: int = 5000,
    target_errors: int = 100,
) -> dict:
    cfg = AdvancedConfig(snr_db=12.0)
    N, S, M = cfg.n_phys, cfg.n_active, cfg.n_sym

    # Per-subcarrier EMA collision scores: lower = less jammed → exploit chooses these
    scores = np.full(N, cfg.n_active / cfg.n_phys, dtype=float)
    causal_state = CausalLagState.create(cfg) if threat == "causal_adaptive_lag" else None

    totals = {
        "bit_errors": 0, "total_bits": 0, "frame_errors": 0,
        "total_frames": 0, "collisions": 0, "active_symbols": 0,
        "mean_posterior": 0.0,
    }
    frame_errors_list = []

    t0 = time.perf_counter()
    for frame_idx in range(max_frames):
        rng = seeded_rng(cfg.seed, "epsgreedy", threat, "mixllr", frame_idx)

        # ── Generate hopping pattern symbol-by-symbol (online) ──
        pattern = np.empty((M, S), dtype=np.int32)
        for m in range(M):
            if rng.random() < epsilon:
                chosen = rng.choice(N, size=S, replace=False)
            else:
                noisy = scores + rng.uniform(0, 1e-10, N)
                chosen = np.argpartition(noisy, S)[:S]
            pattern[m] = np.sort(chosen.astype(np.int32))

        # ── Generate jammer (offline for the frame, using same infrastructure) ──
        pattern_rng = seeded_rng(cfg.seed, "epsgreedy-pat", threat, frame_idx)
        # Use random pattern generation for the jammer's POV — the jammer doesn't
        # know the epsilon-greedy pattern.  We pass the ACTUAL pattern so the
        # jammer can use it for fixed-delay followers.
        jam_rng = seeded_rng(cfg.seed, "epsgreedy-jam", threat, frame_idx)
        # For candidate_aware, we need the true conditional probabilities.
        # We approximate them empirically from the pattern.
        pred = np.zeros((M, N))
        for m in range(M):
            pred[m, pattern[m]] = 1.0 / S
        pred *= S  # rescale so row sums = S

        jams = jammer_sets(threat, pattern, pred, cfg, jam_rng, causal_state)

        # ── Transmit ──
        n_qpsk = S * M
        info = rng.integers(0, 2, n_qpsk - 6, dtype=np.uint8)
        tx = qpsk_mod(conv_encode_k7(info)).reshape(M, S)

        noise_var = 10 ** (-cfg.snr_db / 10.0)
        jsr = 10 ** (cfg.jsr_db / 10.0)
        rx = tx + math.sqrt(noise_var / 2) * (
            rng.standard_normal(tx.shape) + 1j * rng.standard_normal(tx.shape)
        )

        collision_mask = np.zeros((M, S), dtype=bool)
        jam_var = np.zeros(M)
        for m_idx, jam_bins in enumerate(jams):
            mask = np.isin(pattern[m_idx], jam_bins)
            collision_mask[m_idx] = mask
            var = S * jsr / max(len(jam_bins), 1)
            jam_var[m_idx] = var
            n_hit = int(mask.sum())
            if n_hit:
                rx[m_idx, mask] += math.sqrt(var / 2) * (
                    rng.standard_normal(n_hit) + 1j * rng.standard_normal(n_hit)
                )

        # ── Decode ──
        v0 = np.full_like(rx.real, noise_var, dtype=float)
        width = np.asarray([len(j) for j in jams], dtype=float)
        prior = np.repeat(
            np.clip(width / N, 1e-4, 0.95)[:, None], S, axis=1
        )
        v1 = v0 + np.repeat(jam_var[:, None], S, axis=1)
        posterior = posterior_collision(rx, v0, v1, prior)

        decoded = viterbi_decode_llr(mixture_llrs(rx, v0, v1, prior))
        errors = int(np.sum(decoded != info))

        # ── Update EMA scores (online learning step) ──
        for m_idx in range(M):
            hit_bins = pattern[m_idx][collision_mask[m_idx]]
            collision_vec = np.zeros(N)
            collision_vec[hit_bins] = 1.0
            scores = (1 - ema_alpha) * scores + ema_alpha * collision_vec

        # ── Accumulate ──
        totals["bit_errors"] += errors
        totals["total_bits"] += int(info.size)
        totals["frame_errors"] += int(errors > 0)
        totals["total_frames"] += 1
        totals["collisions"] += int(collision_mask.sum())
        totals["active_symbols"] += int(collision_mask.size)
        totals["mean_posterior"] += float(np.mean(posterior))
        frame_errors_list.append(int(errors > 0))

        if frame_idx >= min_frames - 1 and totals["frame_errors"] >= target_errors:
            break

    elapsed = time.perf_counter() - t0
    nf = totals["total_frames"]
    fe = int(totals["frame_errors"])
    bler = fe / nf
    ber = totals["bit_errors"] / totals["total_bits"]
    coll = totals["collisions"] / totals["active_symbols"]
    frame_arr = np.asarray(frame_errors_list, dtype=np.int32)
    _, bl_lo, bl_hi = bootstrap_ci(frame_arr)
    ber_lo, ber_hi = wilson_interval(int(totals["bit_errors"]), int(totals["total_bits"]))

    return {
        "threat": threat,
        "bler": bler, "bler_boot_low": bl_lo, "bler_boot_high": bl_hi,
        "ber": ber, "ber_ci_low": ber_lo, "ber_ci_high": ber_hi,
        "frame_errors": fe, "total_frames": nf,
        "collision_rate": coll,
        "stats_sufficient": fe >= target_errors,
        "elapsed_s": elapsed,
    }


def run_baseline_ucb(
    threat: str = "causal_adaptive_lag",
    ema_alpha: float = 0.10,
    beta: float = 1.0,
    min_frames: int = 2000,
    max_frames: int = 5000,
    target_errors: int = 100,
) -> dict:
    """UCB subcarrier selector: deterministic optimism for exploration.

    Selects S bins minimizing: collision_score - beta * sqrt(2*log(t) / (n_k+1))
    where n_k = selection count, t = total selections so far.
    This is fundamentally different from epsilon-greedy: exploration is
    deterministic and directed toward under-explored bins, not random.
    """
    cfg = AdvancedConfig(snr_db=12.0)
    N, S, M = cfg.n_phys, cfg.n_active, cfg.n_sym

    scores = np.full(N, cfg.n_active / cfg.n_phys, dtype=float)
    select_counts = np.zeros(N, dtype=np.float64)
    total_selects = 0
    causal_state = CausalLagState.create(cfg) if threat == "causal_adaptive_lag" else None

    totals = {
        "bit_errors": 0, "total_bits": 0, "frame_errors": 0,
        "total_frames": 0, "collisions": 0, "active_symbols": 0,
        "mean_posterior": 0.0,
    }
    frame_errors_list = []

    t0 = time.perf_counter()
    for frame_idx in range(max_frames):
        rng = seeded_rng(cfg.seed, "ucb", threat, "mixllr", frame_idx)

        pattern = np.empty((M, S), dtype=np.int32)
        for m in range(M):
            total_selects += S
            # UCB: low collision score = good, low selection count = explore
            ucb_scores = scores - beta * np.sqrt(2.0 * np.log(max(total_selects, 2)) / (select_counts + 1.0))
            chosen = np.argpartition(ucb_scores, S)[:S]
            select_counts[chosen] += 1
            pattern[m] = np.sort(chosen.astype(np.int32))

        pattern_rng = seeded_rng(cfg.seed, "ucb-pat", threat, frame_idx)
        jam_rng = seeded_rng(cfg.seed, "ucb-jam", threat, frame_idx)
        pred = np.zeros((M, N))
        for m in range(M):
            pred[m, pattern[m]] = 1.0 / S
        pred *= S

        jams = jammer_sets(threat, pattern, pred, cfg, jam_rng, causal_state)

        n_qpsk = S * M
        info = rng.integers(0, 2, n_qpsk - 6, dtype=np.uint8)
        tx = qpsk_mod(conv_encode_k7(info)).reshape(M, S)

        noise_var = 10 ** (-cfg.snr_db / 10.0)
        jsr = 10 ** (cfg.jsr_db / 10.0)
        rx = tx + math.sqrt(noise_var / 2) * (
            rng.standard_normal(tx.shape) + 1j * rng.standard_normal(tx.shape)
        )

        collision_mask = np.zeros((M, S), dtype=bool)
        jam_var = np.zeros(M)
        for m_idx, jam_bins in enumerate(jams):
            mask = np.isin(pattern[m_idx], jam_bins)
            collision_mask[m_idx] = mask
            var = S * jsr / max(len(jam_bins), 1)
            jam_var[m_idx] = var
            n_hit = int(mask.sum())
            if n_hit:
                rx[m_idx, mask] += math.sqrt(var / 2) * (
                    rng.standard_normal(n_hit) + 1j * rng.standard_normal(n_hit)
                )

        v0 = np.full_like(rx.real, noise_var, dtype=float)
        width = np.asarray([len(j) for j in jams], dtype=float)
        prior = np.repeat(
            np.clip(width / N, 1e-4, 0.95)[:, None], S, axis=1
        )
        v1 = v0 + np.repeat(jam_var[:, None], S, axis=1)
        decoded = viterbi_decode_llr(mixture_llrs(rx, v0, v1, prior))
        errors = int(np.sum(decoded != info))

        for m_idx in range(M):
            hit_bins = pattern[m_idx][collision_mask[m_idx]]
            collision_vec = np.zeros(N)
            collision_vec[hit_bins] = 1.0
            scores = (1 - ema_alpha) * scores + ema_alpha * collision_vec

        totals["bit_errors"] += errors
        totals["total_bits"] += int(info.size)
        totals["frame_errors"] += int(errors > 0)
        totals["total_frames"] += 1
        totals["collisions"] += int(collision_mask.sum())
        totals["active_symbols"] += int(collision_mask.size)
        frame_errors_list.append(int(errors > 0))

        if frame_idx >= min_frames - 1 and totals["frame_errors"] >= target_errors:
            break

    elapsed = time.perf_counter() - t0
    nf = totals["total_frames"]
    fe = int(totals["frame_errors"])
    bler = fe / nf
    ber = totals["bit_errors"] / totals["total_bits"]
    coll = totals["collisions"] / totals["active_symbols"]
    frame_arr = np.asarray(frame_errors_list, dtype=np.int32)
    _, bl_lo, bl_hi = bootstrap_ci(frame_arr)
    ber_lo, ber_hi = wilson_interval(int(totals["bit_errors"]), int(totals["total_bits"]))

    return {
        "threat": threat,
        "bler": bler, "bler_boot_low": bl_lo, "bler_boot_high": bl_hi,
        "ber": ber, "ber_ci_low": ber_lo, "ber_ci_high": ber_hi,
        "frame_errors": fe, "total_frames": nf,
        "collision_rate": coll,
        "stats_sufficient": fe >= target_errors,
        "elapsed_s": elapsed,
    }


def run_baseline_entropy(
    threat: str = "causal_adaptive_lag",
    epsilon: float = 0.10,
    ema_alpha: float = 0.10,
    entropy_weight: float = 0.5,
    min_frames: int = 2000,
    max_frames: int = 5000,
    target_errors: int = 100,
) -> dict:
    """Entropy-regularized epsilon-greedy: adds entropy bonus to discourage convergence."""
    cfg = AdvancedConfig(snr_db=12.0)
    N, S, M = cfg.n_phys, cfg.n_active, cfg.n_sym

    scores = np.full(N, cfg.n_active / cfg.n_phys, dtype=float)
    causal_state = CausalLagState.create(cfg) if threat == "causal_adaptive_lag" else None

    totals = {
        "bit_errors": 0, "total_bits": 0, "frame_errors": 0,
        "total_frames": 0, "collisions": 0, "active_symbols": 0,
        "mean_posterior": 0.0,
    }
    frame_errors_list = []

    t0 = time.perf_counter()
    for frame_idx in range(max_frames):
        rng = seeded_rng(cfg.seed, "epsgreedy-ent", threat, "mixllr", frame_idx)

        pattern = np.empty((M, S), dtype=np.int32)
        for m in range(M):
            if rng.random() < epsilon:
                # Entropy-regularized exploration: prefer under-explored bins
                explore_probs = 1.0 / (1.0 + scores)
                explore_probs /= explore_probs.sum()
                chosen = rng.choice(N, size=S, replace=False, p=explore_probs)
            else:
                noisy = scores + rng.uniform(0, 1e-10, N)
                chosen = np.argpartition(noisy, S)[:S]
            pattern[m] = np.sort(chosen.astype(np.int32))

        pattern_rng = seeded_rng(cfg.seed, "epsgreedy-ent-pat", threat, frame_idx)
        jam_rng = seeded_rng(cfg.seed, "epsgreedy-ent-jam", threat, frame_idx)
        pred = np.zeros((M, N))
        for m in range(M):
            pred[m, pattern[m]] = 1.0 / S
        pred *= S

        jams = jammer_sets(threat, pattern, pred, cfg, jam_rng, causal_state)

        n_qpsk = S * M
        info = rng.integers(0, 2, n_qpsk - 6, dtype=np.uint8)
        tx = qpsk_mod(conv_encode_k7(info)).reshape(M, S)

        noise_var = 10 ** (-cfg.snr_db / 10.0)
        jsr = 10 ** (cfg.jsr_db / 10.0)
        rx = tx + math.sqrt(noise_var / 2) * (
            rng.standard_normal(tx.shape) + 1j * rng.standard_normal(tx.shape)
        )

        collision_mask = np.zeros((M, S), dtype=bool)
        jam_var = np.zeros(M)
        for m_idx, jam_bins in enumerate(jams):
            mask = np.isin(pattern[m_idx], jam_bins)
            collision_mask[m_idx] = mask
            var = S * jsr / max(len(jam_bins), 1)
            jam_var[m_idx] = var
            n_hit = int(mask.sum())
            if n_hit:
                rx[m_idx, mask] += math.sqrt(var / 2) * (
                    rng.standard_normal(n_hit) + 1j * rng.standard_normal(n_hit)
                )

        v0 = np.full_like(rx.real, noise_var, dtype=float)
        width = np.asarray([len(j) for j in jams], dtype=float)
        prior = np.repeat(
            np.clip(width / N, 1e-4, 0.95)[:, None], S, axis=1
        )
        v1 = v0 + np.repeat(jam_var[:, None], S, axis=1)
        decoded = viterbi_decode_llr(mixture_llrs(rx, v0, v1, prior))
        errors = int(np.sum(decoded != info))

        for m_idx in range(M):
            hit_bins = pattern[m_idx][collision_mask[m_idx]]
            collision_vec = np.zeros(N)
            collision_vec[hit_bins] = 1.0
            scores = (1 - ema_alpha) * scores + ema_alpha * collision_vec

        totals["bit_errors"] += errors
        totals["total_bits"] += int(info.size)
        totals["frame_errors"] += int(errors > 0)
        totals["total_frames"] += 1
        totals["collisions"] += int(collision_mask.sum())
        totals["active_symbols"] += int(collision_mask.size)
        frame_errors_list.append(int(errors > 0))

        if frame_idx >= min_frames - 1 and totals["frame_errors"] >= target_errors:
            break

    elapsed = time.perf_counter() - t0
    nf = totals["total_frames"]
    fe = int(totals["frame_errors"])
    bler = fe / nf
    ber = totals["bit_errors"] / totals["total_bits"]
    coll = totals["collisions"] / totals["active_symbols"]
    frame_arr = np.asarray(frame_errors_list, dtype=np.int32)
    _, bl_lo, bl_hi = bootstrap_ci(frame_arr)
    ber_lo, ber_hi = wilson_interval(int(totals["bit_errors"]), int(totals["total_bits"]))

    return {
        "threat": threat,
        "bler": bler, "bler_boot_low": bl_lo, "bler_boot_high": bl_hi,
        "ber": ber, "ber_ci_low": ber_lo, "ber_ci_high": ber_hi,
        "frame_errors": fe, "total_frames": nf,
        "collision_rate": coll,
        "stats_sufficient": fe >= target_errors,
        "elapsed_s": elapsed,
    }


def main():
    import argparse
    import csv
    import hashlib
    import json

    parser = argparse.ArgumentParser(description="ε-greedy RL baseline comparison matrix")
    parser.add_argument("profile", choices=["smoke", "paper"], default="smoke", nargs="?",
                        help="smoke = fast (500 frames), paper = full (2000-5000 frames)")
    args = parser.parse_args()

    is_smoke = args.profile == "smoke"
    min_frames = 200 if is_smoke else 2000
    max_frames = 500 if is_smoke else 5000
    target_errors = 20 if is_smoke else 100

    threats = ["fixed_d1", "fixed_d3", "causal_adaptive_lag", "candidate_aware"]

    # Reference BLER from v1.0 formal experiment (Table I in paper)
    ref = {
        "fixed_d1": {"Random": 0.0425, "MCSH-L2": 0.0010, "PASH-cap": 0.0172},
        "fixed_d3": {"Random": 0.0535, "MCSH-L2": 0.1375, "PASH-cap": 0.0200},
        "causal_adaptive_lag": {"Random": 0.0476, "MCSH-L2": 0.1230, "PASH-cap": 0.0183},
        "candidate_aware": {"Random": 0.0422, "MCSH-L2": 0.1435, "PASH-cap": 0.0870},
    }

    # RL configurations to test
    configs = [
        {"label": "ε=0.10 α=0.10", "epsilon": 0.10, "ema_alpha": 0.10, "variant": "base"},
        {"label": "ε=0.50 α=0.10", "epsilon": 0.50, "ema_alpha": 0.10, "variant": "high_explore"},
        {"label": "ε=0.10 α=0.50", "epsilon": 0.10, "ema_alpha": 0.50, "variant": "fast_adapt"},
        {"label": "entropy-reg ε=0.10", "epsilon": 0.10, "ema_alpha": 0.10, "variant": "entropy_reg"},
        {"label": "UCB β=1.0 α=0.10", "epsilon": 0.0, "ema_alpha": 0.10, "variant": "ucb"},
    ]

    print("=" * 80)
    print(f"Online Learning Baseline Matrix  |  Profile={args.profile}  SNR=12 dB  JSR=5 dB")
    print(f"Configs: {len(configs)}  Threats: {len(threats)}  Total runs: {len(configs)*len(threats)}")
    print("=" * 80)

    all_rows = []
    for cfg_i, cfg in enumerate(configs):
        print(f"\n[{cfg_i+1}/{len(configs)}] {cfg['label']}")
        print("-" * 60)
        for threat in threats:
            t0 = time.perf_counter()
            if cfg["variant"] == "entropy_reg":
                r = run_baseline_entropy(threat, epsilon=cfg["epsilon"],
                                         ema_alpha=cfg["ema_alpha"],
                                         min_frames=min_frames, max_frames=max_frames,
                                         target_errors=target_errors)
            elif cfg["variant"] == "ucb":
                r = run_baseline_ucb(threat, ema_alpha=cfg["ema_alpha"],
                                     min_frames=min_frames, max_frames=max_frames,
                                     target_errors=target_errors)
            else:
                r = run_baseline(threat, epsilon=cfg["epsilon"],
                                 ema_alpha=cfg["ema_alpha"],
                                 min_frames=min_frames, max_frames=max_frames,
                                 target_errors=target_errors)

            ref_bler = ref[threat]
            best_open_loop = min(ref_bler.values())
            row = {
                "variant": cfg["variant"],
                "variant_label": cfg["label"],
                "epsilon": cfg["epsilon"],
                "ema_alpha": cfg["ema_alpha"],
                "threat": threat,
                "bler": round(r["bler"], 6),
                "bler_boot_low": round(r["bler_boot_low"], 6),
                "bler_boot_high": round(r["bler_boot_high"], 6),
                "ber": r["ber"],
                "collision_rate": round(r["collision_rate"], 6),
                "frame_errors": r["frame_errors"],
                "total_frames": r["total_frames"],
                "stats_sufficient": r["stats_sufficient"],
                "elapsed_s": round(r["elapsed_s"], 1),
                "best_open_loop_bler": best_open_loop,
                "ratio_vs_best_open": round(r["bler"] / best_open_loop, 2),
            }
            all_rows.append(row)

            vs_best = f"{row['ratio_vs_best_open']:.1f}×" if row['ratio_vs_best_open'] < 100 else ">>100×"
            print(
                f"  {threat:20s}  BLER={r['bler']:.4f} [{r['bler_boot_low']:.4f},{r['bler_boot_high']:.4f}]  "
                f"fe={r['frame_errors']}/{r['total_frames']}  "
                f"vs_best_open={vs_best}  {r['elapsed_s']:.0f}s"
            )

    # ── Summary table ──
    print(f"\n{'='*80}")
    print(f"{'Threat':<22s}", end="")
    for c in configs:
        print(f" {c['label']:>20s}", end="")
    print(f" {'Best Open':>12s}")
    print("-" * 80)
    for threat in threats:
        print(f"{threat:<22s}", end="")
        best_open = min(ref[threat].values())
        for c in configs:
            row = [r for r in all_rows if r["threat"] == threat and r["variant"] == c["variant"]][0]
            tag = " *" if row["bler"] <= best_open * 1.1 else ""
            print(f" {row['bler']:>19.4f}{tag}", end="")
        print(f" {best_open:>12.4f}")
    print("-" * 80)
    print(" *  = within 10% of best open-loop method")

    # ── Save to CSV ──
    is_smoke = args.profile == "smoke"
    output_dir = ROOT / "tmp" / "smoke-rl-baselines" if is_smoke else ROOT / "results" / "comml" / "rl_baselines"
    output_dir.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "variant", "variant_label", "epsilon", "ema_alpha", "threat",
        "bler", "bler_boot_low", "bler_boot_high", "ber", "collision_rate",
        "frame_errors", "total_frames", "stats_sufficient", "elapsed_s",
        "best_open_loop_bler", "ratio_vs_best_open",
    ]
    with (output_dir / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    # Write manifest
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = {
        "script": str(Path(__file__).relative_to(ROOT)),
        "source_sha256": source_hash,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "profile": args.profile,
        "n_configs": len(configs),
        "n_threats": len(threats),
    }
    with (output_dir / "run_manifest.json").open("w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nResults written to {output_dir}")
    print(f"  summary.csv: {len(all_rows)} rows")
    print(f"  run_manifest.json")


if __name__ == "__main__":
    main()
