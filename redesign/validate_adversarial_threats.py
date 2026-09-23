#!/usr/bin/env python3
"""Lightweight scientific-validity checks for adversarial threat generation."""

from __future__ import annotations

import csv
import inspect
from pathlib import Path

import numpy as np

from advanced_experiment import (
    AdvancedConfig,
    CausalLagState,
    generate_sequence,
    jammer_sets,
    method_weights,
    sample_method,
    seeded_rng,
    systematic_sample_from_inclusion_probs,
    transmit_frame,
)


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "results" / "model_validity" / "adversarial_threat_checks.csv"
REPORT_PATH = ROOT / "docs" / "experiments" / "adversarial_threat_checks.md"


def causal_trajectory(cfg: AdvancedConfig, method: str, frames: int) -> list[list[np.ndarray]]:
    state = CausalLagState.create(cfg)
    trajectory = []
    for frame in range(frames):
        pattern_rng = seeded_rng(cfg.seed, "advanced-pattern", method, frame)
        jammer_rng = seeded_rng(cfg.seed, "advanced-jammer", method, "causal_adaptive_lag", frame)
        pattern, probs, _ = generate_sequence(method, cfg, pattern_rng)
        trajectory.append(
            jammer_sets("causal_adaptive_lag", pattern, probs, cfg, jammer_rng, state)
        )
    return trajectory


def trajectory_equal(left: list[list[np.ndarray]], right: list[list[np.ndarray]]) -> bool:
    return all(
        np.array_equal(a_set, b_set)
        for a_frame, b_frame in zip(left, right)
        for a_set, b_set in zip(a_frame, b_frame)
    )


def run_checks() -> list[dict[str, object]]:
    cfg = AdvancedConfig(n_sym=16)
    rows: list[dict[str, object]] = []

    select_params = list(inspect.signature(CausalLagState.select_lag).parameters)
    rows.append({
        "check": "causal_action_api_has_no_current_pattern",
        "passed": "pattern" not in select_params and "current" not in select_params,
        "detail": ",".join(select_params),
    })

    pattern_rng = seeded_rng(cfg.seed, "threat-check-pattern")
    jammer_rng = seeded_rng(cfg.seed, "threat-check-jammer")
    pattern, probs, _ = generate_sequence("mcsh_l2", cfg, pattern_rng)
    sets = jammer_sets(
        "causal_adaptive_lag", pattern, probs, cfg, jammer_rng, CausalLagState.create(cfg)
    )
    historical_only = all(
        any(np.array_equal(sets[m], pattern[m - d]) for d in range(1, min(cfg.max_delay, m) + 1))
        for m in range(1, cfg.n_sym)
    )
    rows.append({
        "check": "causal_actions_are_historical_sets",
        "passed": historical_only,
        "detail": "all m>0 actions match an available historical set",
    })

    traj_a = causal_trajectory(cfg, "mcsh_l2", 8)
    traj_b = causal_trajectory(cfg, "mcsh_l2", 8)
    rows.append({
        "check": "causal_trajectory_reproducible",
        "passed": trajectory_equal(traj_a, traj_b),
        "detail": "fresh explicit states and identical seeds produce identical trajectories",
    })

    frame = 3
    pattern_rng = seeded_rng(cfg.seed, "advanced-pattern", "mcsh_l2", frame)
    jammer_rng = seeded_rng(cfg.seed, "advanced-jammer", "mcsh_l2", "causal_adaptive_lag", frame)
    pattern, probs, _ = generate_sequence("mcsh_l2", cfg, pattern_rng)
    jam = jammer_sets(
        "causal_adaptive_lag", pattern, probs, cfg, jammer_rng, CausalLagState.create(cfg)
    )
    order_a = ["none", "mixllr", "oracle"]
    order_b = list(reversed(order_a))
    results_a = {
        receiver: transmit_frame(
            "mcsh_l2", "causal_adaptive_lag", receiver, cfg, frame, pattern=pattern, jam_sets=jam
        )["collisions"]
        for receiver in order_a
    }
    results_b = {
        receiver: transmit_frame(
            "mcsh_l2", "causal_adaptive_lag", receiver, cfg, frame, pattern=pattern, jam_sets=jam
        )["collisions"]
        for receiver in order_b
    }
    rows.append({
        "check": "receiver_order_does_not_change_attack",
        "passed": results_a == results_b and len(set(results_a.values())) == 1,
        "detail": f"collisions={results_a}",
    })

    delayed = CausalLagState.create(cfg, feedback_delay=2, feedback_error_prob=0.0)
    delayed_rng = seeded_rng(cfg.seed, "delayed-feedback-check")
    selected = delayed.select_lag(3, cfg, delayed_rng)
    before = delayed.estimates.copy()
    delayed.observe(selected, 1.0, delayed_rng)
    lag_4 = delayed.select_lag(4, cfg, delayed_rng)
    delayed.observe(lag_4, delayed.baseline, delayed_rng)
    lag_5 = delayed.select_lag(5, cfg, delayed_rng)
    unchanged_before_due = np.array_equal(before, delayed.estimates)
    delayed.observe(lag_5, delayed.baseline, delayed_rng)
    delayed.select_lag(6, cfg, delayed_rng)
    rows.append({
        "check": "delayed_feedback_not_used_early",
        "passed": unchanged_before_due and not np.array_equal(before, delayed.estimates),
        "detail": "D_f=2 report changes estimates only after two additional slots",
    })

    sample_rng = seeded_rng(cfg.seed, "systematic-sampler-fixed-size")
    test_probs = np.full(cfg.n_phys, cfg.n_active / cfg.n_phys)
    test_sample = systematic_sample_from_inclusion_probs(test_probs, sample_rng)
    rows.append({
        "check": "systematic_sampler_has_fixed_size_without_duplicates",
        "passed": len(test_sample) == cfg.n_active and np.unique(test_sample).size == cfg.n_active,
        "detail": f"size={len(test_sample)}, unique={np.unique(test_sample).size}",
    })

    history_rng = seeded_rng(cfg.seed, "systematic-sampler-history")
    history = []
    for _ in range(12):
        chosen, _ = sample_method("pash_c15", history, cfg, history_rng)
        history.append(chosen)
    _, target = method_weights("pash_c15", history, cfg)
    marginal_rng = seeded_rng(cfg.seed, "systematic-sampler-marginals")
    repetitions = 20000
    counts = np.zeros(cfg.n_phys, dtype=float)
    for _ in range(repetitions):
        counts[systematic_sample_from_inclusion_probs(target, marginal_rng)] += 1.0
    empirical = counts / repetitions
    max_error = float(np.max(np.abs(empirical - target)))
    rows.append({
        "check": "systematic_sampler_preserves_pash_marginals",
        "passed": max_error <= 0.012 and float(np.max(target)) <= 0.15 + 1e-12,
        "detail": f"max_abs_error={max_error:.5f}, target_max={float(np.max(target)):.5f}",
    })
    return rows


def main() -> int:
    rows = run_checks()
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "passed", "detail"])
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Adversarial Threat Validity Checks",
        "",
        "| Check | Passed | Detail |",
        "|---|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['check']} | {row['passed']} | {row['detail']} |")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    passed = sum(bool(row["passed"]) for row in rows)
    print(f"Adversarial threat checks passed {passed}/{len(rows)}")
    print(f"Saved checks to {CSV_PATH}")
    print(f"Saved report to {REPORT_PATH}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
