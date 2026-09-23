#!/usr/bin/env python3
"""Advanced adversarial experiments for predictability-aware soft hopping.

This script is intentionally separate from the earlier phase-2 simulator.  It
stress-tests the structural weakness found in MCSH: hard exclusion removes
short-delay collisions but concentrates next-set probability in a smaller
candidate pool.  PASH uses soft probability shaping over a longer history to
trade short-delay avoidance against history-conditioned predictability.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from scipy.special import logsumexp
from tqdm import tqdm

from fair_grid_sim import (
    INCOMING,
    OUTPUT_BITS,
    TRANS_EXPECTED,
    TRANS_INPUT,
    TRANS_PREV,
    conv_encode_k7,
    qpsk_mod,
    qpsk_soft,
    seeded_rng,
    wilson_interval,
)
from innovation_sim import posterior_collision, viterbi_decode_weighted


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "advanced" / "paper"
STATS_RESULT_DIR = ROOT / "results" / "advanced" / "stats"
COMML_STATS_RESULT_DIR = ROOT / "results" / "comml" / "stats"
FIGURE_DIR = ROOT / "figures" / "paper"
REPORT = ROOT / "docs" / "experiments" / "advanced_experiment_results.md"
STATS_REPORT = ROOT / "docs" / "experiments" / "advanced_experiment_stats.md"
COMML_STATS_REPORT = ROOT / "docs" / "experiments" / "final_comml_experiment_results.md"
SMOKE_RESULT_DIR = ROOT / "tmp" / "smoke-advanced" / "results"
SMOKE_FIGURE_DIR = ROOT / "tmp" / "smoke-advanced" / "figures"
SMOKE_REPORT = ROOT / "tmp" / "smoke-advanced" / "advanced_experiment_results.md"
COMML_SMOKE_RESULT_DIR = ROOT / "tmp" / "smoke-comml" / "results"
COMML_SMOKE_FIGURE_DIR = ROOT / "tmp" / "smoke-comml" / "figures"
COMML_SMOKE_REPORT = ROOT / "tmp" / "smoke-comml" / "final_comml_experiment_results.md"
QPSK_BITS = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.uint8)
QPSK = qpsk_mod(QPSK_BITS.reshape(-1))
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260607


def bootstrap_ci(
    frame_errors: np.ndarray, n_bootstrap: int = BOOTSTRAP_REPLICATES, alpha: float = 0.05
) -> Tuple[float, float, float]:
    """Percentile bootstrap CI for BLER from per-frame binary outcomes (0/1)."""
    n = len(frame_errors)
    if n == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        means[i] = rng.choice(frame_errors, size=n, replace=True).mean()
    bler = float(frame_errors.mean())
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return bler, lo, hi


def zero_error_bound(n_total: int) -> float:
    """Rule-of-three upper bound for zero observed events (95% confidence)."""
    return 3.0 / max(n_total, 1)


def stats_sufficient(frame_errors: int, total_frames: int, target: int = 100) -> bool:
    """Check whether accumulated frame errors meet the statistical target."""
    return frame_errors >= target


@dataclass(frozen=True)
class AdvancedConfig:
    n_phys: int = 512
    n_active: int = 64
    n_sym: int = 32
    snr_db: float = 12.0
    jsr_db: float = 5.0
    max_delay: int = 12
    seed: int = 20260607


METHODS: Dict[str, Dict[str, float | int | str]] = {
    "random": {"kind": "random", "label": "Random"},
    "mcsh_l1": {"kind": "mcsh", "memory": 1, "label": "MCSH $L_h=1$"},
    "mcsh_l2": {"kind": "mcsh", "memory": 2, "label": "MCSH $L_h=2$"},
    "mcsh_l4": {"kind": "mcsh", "memory": 4, "label": "MCSH $L_h=4$"},
    "mcsh_l6": {"kind": "mcsh", "memory": 6, "label": "MCSH $L_h=6$"},
    "bcd": {"kind": "bcd", "label": "Block-Cyclic Det."},
    "lfsr": {"kind": "lfsr", "label": "LFSR Pseudo-Random"},
    "sbs": {"kind": "sbs", "shift": 3, "label": "Staggered Block-Shift"},
    "pash_a08": {
        "kind": "pash",
        "memory": 6,
        "alpha": 0.8,
        "floor": 0.25,
        "label": "PASH $\\alpha=0.8$",
    },
    "pash_a14": {
        "kind": "pash",
        "memory": 6,
        "alpha": 1.4,
        "floor": 0.20,
        "label": "PASH $\\alpha=1.4$",
    },
    "pash_c15": {
        "kind": "pash_cap",
        "memory": 6,
        "alpha": 1.4,
        "floor": 0.20,
        "cap": 0.15,
        "label": "PASH-cap $p_{\\max}=0.15$",
    },
    "pash_c14": {
        "kind": "pash_cap",
        "memory": 6,
        "alpha": 1.4,
        "floor": 0.20,
        "cap": 0.14,
        "label": "PASH-cap $p_{\\max}=0.14$",
    },
        "pash_linear": {
            "kind": "pash_linear",
            "memory": 6,
            "floor": 0.20,
            "cap": 0.15,
            "label": "PASH-linear",
        },
        "pash_nocap": {
            "kind": "pash",
            "memory": 6,
            "alpha": 1.4,
            "floor": 0.20,
            "label": "PASH no-cap",
        },
}

PATTERNS = ["random", "bcd", "lfsr", "sbs", "mcsh_l1", "mcsh_l2", "mcsh_l4", "mcsh_l6", "pash_a08", "pash_a14", "pash_c15", "pash_c14", "pash_linear", "pash_nocap"]
CODED_PATTERNS = ["random", "bcd", "lfsr", "sbs", "mcsh_l1", "mcsh_l2", "pash_a08", "pash_c15", "pash_c14", "pash_linear", "pash_nocap"]
THREATS = ["fixed_d1", "fixed_d3", "delay_uniform", "oracle_best_lag", "causal_adaptive_lag", "candidate_aware"]
RECEIVERS = ["none", "brw", "hard_tuned", "oracle", "mixllr"]
COMML_CODED_PATTERNS = ["random", "bcd", "lfsr", "mcsh_l2", "pash_c15", "pash_linear", "pash_nocap"]
COMML_THREATS = ["fixed_d1", "fixed_d3", "causal_adaptive_lag", "candidate_aware"]
COMML_RECEIVERS = ["mixllr"]


def recent_counts(history: Sequence[np.ndarray], memory: int, n_phys: int) -> np.ndarray:
    counts = np.zeros(n_phys, dtype=float)
    for item in history[-memory:]:
        counts[item] += 1.0
    return counts


def capped_inclusion_probs(weights: np.ndarray, n_active: int, cap: float = 1.0) -> np.ndarray:
    """Compute target inclusion probabilities with p_i <= cap and sum p_i = n_active."""
    weights = np.asarray(weights, dtype=float)
    probs = np.zeros_like(weights)
    remaining = np.arange(weights.size)
    budget = float(n_active)
    while remaining.size and budget > 1e-12:
        scale = budget / float(np.sum(weights[remaining]))
        tentative = scale * weights[remaining]
        capped = tentative >= cap
        if not np.any(capped):
            probs[remaining] = tentative
            break
        cap_idx = remaining[capped]
        probs[cap_idx] = cap
        budget -= cap * cap_idx.size
        remaining = remaining[~capped]
    return np.clip(probs, 0.0, 1.0)


def systematic_sample_from_inclusion_probs(
    probs: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Draw a fixed-size sample while preserving the supplied first-order marginals.

    Random permutation removes any physical-bin ordering preference. Conditional
    on that order, systematic probability-proportional-to-size sampling selects
    exactly sum(probs) distinct bins and includes bin k with probability probs[k].
    """
    probs = np.asarray(probs, dtype=float)
    sample_size = int(round(float(np.sum(probs))))
    if sample_size <= 0 or not np.isclose(np.sum(probs), sample_size, atol=1e-9):
        raise ValueError("Inclusion probabilities must sum to a positive integer")
    if np.any(probs < -1e-12) or np.any(probs > 1.0 + 1e-12):
        raise ValueError("Inclusion probabilities must lie in [0, 1]")

    order = rng.permutation(probs.size)
    cumulative = np.cumsum(probs[order])
    thresholds = rng.random() + np.arange(sample_size, dtype=float)
    selected_positions = np.searchsorted(cumulative, thresholds, side="right")
    chosen = order[selected_positions].astype(np.int32)
    if np.unique(chosen).size != sample_size:
        raise RuntimeError("Systematic sampler produced duplicate selections")
    return chosen


def method_weights(
    method: str, history: Sequence[np.ndarray], cfg: AdvancedConfig
) -> Tuple[np.ndarray, np.ndarray]:
    spec = METHODS[method]
    kind = spec["kind"]
    if kind == "random":
        weights = np.ones(cfg.n_phys)
        probs = np.full(cfg.n_phys, cfg.n_active / cfg.n_phys)
        return weights, probs

    if kind == "bcd":
        # Block-Cyclic Deterministic: P = N/S orthogonal basis sets.
        P = cfg.n_phys // cfg.n_active  # 8 for 512/64
        sym_idx = len(history)
        offset = sym_idx % P
        probs = np.zeros(cfg.n_phys)
        chosen = np.array([offset + i * P for i in range(cfg.n_active)], dtype=np.int32)
        probs[chosen] = 1.0
        weights = probs.copy()
        weights[weights == 0] = 1e-12
        return weights, probs

    if kind == "lfsr":
        # LFSR-based pseudorandom FH: classical m-sequence hopping.
        # Uses Fibonacci LFSR (x^9 + x^5 + 1, period 511) to generate
        # pseudorandom bin indices.  This is the canonical FH implementation
        # used in MIL-STD-188 and similar tactical systems — it is
        # deterministic, stateless, and requires no per-symbol history.
        # For S=64, the LFSR is advanced S times per symbol, skipping
        # duplicate bins, to produce a pseudorandom active set scattered
        # across the full band.
        P = cfg.n_phys // cfg.n_active  # 8, not directly used
        sym_idx = len(history)
        # Initialize and advance LFSR to current symbol
        lfsr_state = (cfg.seed + sym_idx * 127) & 0x1FF
        if lfsr_state == 0:
            lfsr_state = 1
        # Use LFSR state to seed a deterministic permutation per symbol
        # Multiple LFSR iterations mix the state before generating the set
        for _ in range(8):
            bit = ((lfsr_state >> 8) ^ (lfsr_state >> 4)) & 1
            lfsr_state = ((lfsr_state << 1) | bit) & 0x1FF
        # Generate S pseudorandom bin indices from LFSR state
        rng_lfsr = np.random.RandomState((lfsr_state * 2654435761 + sym_idx) & 0x7FFFFFFF)
        perm = rng_lfsr.permutation(cfg.n_phys)
        chosen = perm[:cfg.n_active].astype(np.int32)
        probs = np.zeros(cfg.n_phys)
        probs[chosen] = 1.0
        weights = probs.copy()
        weights[weights == 0] = 1e-12
        return weights, probs

    if kind == "sbs":
        # Staggered Block-Shift: K overlapping blocks, cyclic rotation with
        # intra-block randomisation.  Block width = 2*S, shift coprime to K.
        K = cfg.n_phys // cfg.n_active  # 8
        shift = int(spec.get("shift", 3))
        sym_idx = len(history)
        block = (sym_idx * shift) % K
        start = block * cfg.n_active
        # Block covers [start, start + 2*S) with wrap-around
        eligible = np.arange(start, start + 2 * cfg.n_active) % cfg.n_phys
        eligible = np.unique(eligible)
        probs = np.zeros(cfg.n_phys)
        # Uniform probability within the eligible block
        p_val = min(1.0, cfg.n_active / len(eligible))
        probs[eligible] = p_val
        weights = probs.copy()
        weights[weights == 0] = 1e-12
        return weights, probs

    memory = int(spec["memory"])
    counts = recent_counts(history, memory, cfg.n_phys)
    if kind == "mcsh":
        probs = np.zeros(cfg.n_phys)
        remaining = cfg.n_active
        for value in np.unique(counts):
            group = np.flatnonzero(counts == value)
            if group.size <= remaining:
                probs[group] = 1.0
                remaining -= group.size
            else:
                probs[group] = remaining / group.size
                remaining = 0
                break
        weights = probs.copy()
        weights[weights == 0] = 1e-12
        return weights, probs

    if kind == "pash_linear":
        floor = float(spec["floor"])
        memory = int(spec["memory"])
        weights = floor + np.maximum(0.0, 1.0 - counts / memory)
        probs = capped_inclusion_probs(weights, cfg.n_active, float(spec.get("cap", 1.0)))
        return weights, probs

    alpha = float(spec["alpha"])
    floor = float(spec["floor"])
    weights = floor + np.exp(-alpha * counts)
    probs = capped_inclusion_probs(weights, cfg.n_active, float(spec.get("cap", 1.0)))
    if kind == "pash_cap":
        weights = probs.copy()
    return weights, probs


def sample_method(
    method: str, history: Sequence[np.ndarray], cfg: AdvancedConfig, rng: np.random.Generator
) -> Tuple[np.ndarray, np.ndarray]:
    weights, probs = method_weights(method, history, cfg)
    spec = METHODS[method]
    if spec["kind"] in {"bcd", "lfsr"}:
        chosen = np.flatnonzero(probs >= 0.999).astype(np.int32)
        return chosen, probs
    if spec["kind"] == "sbs":
        # Block-shift: weighted sampling within the eligible block
        p = weights / np.sum(weights)
        return rng.choice(cfg.n_phys, cfg.n_active, replace=False, p=p).astype(np.int32), probs
    if spec["kind"] == "mcsh":
        chosen: List[int] = []
        counts = recent_counts(history, int(spec["memory"]), cfg.n_phys)
        for value in np.unique(counts):
            group = np.flatnonzero(counts == value)
            need = cfg.n_active - len(chosen)
            if group.size <= need:
                chosen.extend(group.tolist())
            else:
                chosen.extend(rng.choice(group, need, replace=False).tolist())
                break
        return np.asarray(chosen, dtype=np.int32), probs
    if spec["kind"] in {"pash", "pash_cap", "pash_linear"}:
        return systematic_sample_from_inclusion_probs(probs, rng), probs
    p = weights / np.sum(weights)
    return rng.choice(cfg.n_phys, cfg.n_active, replace=False, p=p).astype(np.int32), probs


def generate_sequence(
    method: str, cfg: AdvancedConfig, rng: np.random.Generator
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    history: List[np.ndarray] = []
    pattern = np.empty((cfg.n_sym, cfg.n_active), dtype=np.int32)
    probs = np.empty((cfg.n_sym, cfg.n_phys), dtype=float)
    candidate_collision = np.zeros(cfg.n_sym)
    for m in range(cfg.n_sym):
        chosen, pred = sample_method(method, history, cfg, rng)
        jammer = np.argsort(pred)[-cfg.n_active :]
        pattern[m] = chosen
        probs[m] = pred
        candidate_collision[m] = len(np.intersect1d(chosen, jammer)) / cfg.n_active
        history.append(chosen)
    return pattern, probs, candidate_collision


def lag_collision(pattern: np.ndarray, lag: int, n_active: int) -> float:
    if lag >= pattern.shape[0]:
        return 0.0
    return float(
        np.mean(
            [
                len(np.intersect1d(pattern[m], pattern[m - lag])) / n_active
                for m in range(lag, pattern.shape[0])
            ]
        )
    )


def structural_experiment(profile: str, cfg: AdvancedConfig) -> List[Dict[str, object]]:
    max_lag = 12
    seeds = range(5 if profile == "smoke" else 30)
    n_sym = 1000 if profile == "smoke" else 5000
    scfg = AdvancedConfig(**{**asdict(cfg), "n_sym": n_sym})
    rows: List[Dict[str, object]] = []
    method_pbar = tqdm(PATTERNS, desc="Structural", unit="method")
    for method in method_pbar:
        method_pbar.set_postfix_str(METHODS[method]["label"][:30])
        lag_runs = []
        candidate_runs = []
        usage_cvs = []
        max_probs = []
        top_mass = []
        seed_iter = tqdm(seeds, desc=f"  {method}", leave=False, unit="seed")
        for seed in seed_iter:
            rng = seeded_rng(cfg.seed, "structural", method, seed)
            pattern, probs, candidate_collision = generate_sequence(method, scfg, rng)
            lag_runs.append(
                [lag_collision(pattern, lag, scfg.n_active) for lag in range(1, max_lag + 1)]
            )
            candidate_runs.append(float(np.mean(candidate_collision)))
            counts = np.bincount(pattern.reshape(-1), minlength=scfg.n_phys)
            usage_cvs.append(float(counts.std() / counts.mean()))
            max_probs.append(float(np.mean(np.max(probs, axis=1))))
            top_mass.append(
                float(
                    np.mean(
                        [np.sum(np.sort(row)[-scfg.n_active :]) / scfg.n_active for row in probs]
                    )
                )
            )
        values = np.asarray(lag_runs)
        mean_lags = values.mean(axis=0)
        short_mean = float(np.mean(mean_lags[:2]))
        worst_idx = int(np.argmax(mean_lags))
        rows.append(
            {
                "method": method,
                "label": METHODS[method]["label"],
                "short_delay_collision": short_mean,
                "worst_lag": worst_idx + 1,
                "worst_lag_collision": float(mean_lags[worst_idx]),
                "candidate_collision": float(np.mean(candidate_runs)),
                "usage_cv": float(np.mean(usage_cvs)),
                "max_inclusion_prob": float(np.mean(max_probs)),
                "top_s_mass_fraction": float(np.mean(top_mass)),
                **{f"lag_{lag}": float(mean_lags[lag - 1]) for lag in range(1, max_lag + 1)},
            }
        )
    return rows


@dataclass
class CausalLagState:
    """Explicit state for a feedback-aided causal adaptive-lag jammer.

    Lag selection receives only the slot index and past state. Collision
    feedback is observed strictly after the jammer action has been selected.
    """

    estimates: np.ndarray
    counts: np.ndarray
    epsilon: float = 0.10
    alpha: float = 0.20
    feedback_delay: int = 0
    feedback_error_prob: float = 0.0
    baseline: float = 0.125
    clock: int = 0
    pending_feedback: Optional[List[Tuple[int, int, float]]] = None

    @classmethod
    def create(
        cls,
        cfg: AdvancedConfig,
        feedback_delay: int = 0,
        feedback_error_prob: float = 0.0,
    ) -> "CausalLagState":
        baseline = cfg.n_active / cfg.n_phys
        return cls(
            estimates=np.full(cfg.max_delay + 1, baseline, dtype=float),
            counts=np.zeros(cfg.max_delay + 1, dtype=np.int64),
            feedback_delay=feedback_delay,
            feedback_error_prob=feedback_error_prob,
            baseline=baseline,
            pending_feedback=[],
        )

    def apply_due_feedback(self) -> None:
        """Apply reports available before the current slot action."""
        if self.pending_feedback is None:
            self.pending_feedback = []
        remaining: List[Tuple[int, int, float]] = []
        for due, lag, collision_rate in self.pending_feedback:
            if due <= self.clock:
                self.estimates[lag] = (
                    (1.0 - self.alpha) * self.estimates[lag] + self.alpha * collision_rate
                )
            else:
                remaining.append((due, lag, collision_rate))
        self.pending_feedback = remaining

    def select_lag(self, symbol_index: int, cfg: AdvancedConfig, rng: np.random.Generator) -> int:
        """Select a lag without access to the current transmitted set."""
        self.apply_due_feedback()
        max_d = min(cfg.max_delay, symbol_index)
        if max_d < 1:
            return 0
        if rng.random() < self.epsilon:
            lag = int(rng.integers(1, max_d + 1))
        else:
            lag = int(np.argmax(self.estimates[1 : max_d + 1]) + 1)
        self.counts[lag] += 1
        return lag

    def observe(self, lag: int, collision_rate: float, rng: np.random.Generator) -> None:
        """Queue a potentially corrupted post-slot report for future use."""
        if lag <= 0:
            self.clock += 1
            return
        observed = collision_rate
        if self.feedback_error_prob > 0 and rng.random() < self.feedback_error_prob:
            observed = self.baseline
        if self.pending_feedback is None:
            self.pending_feedback = []
        due = self.clock + self.feedback_delay + 1
        self.pending_feedback.append((due, lag, observed))
        self.clock += 1


def jammer_sets(
    threat: str,
    pattern: np.ndarray,
    probs: np.ndarray,
    cfg: AdvancedConfig,
    rng: np.random.Generator,
    causal_state: Optional[CausalLagState] = None,
    causal_feedback_rng: Optional[np.random.Generator] = None,
) -> List[np.ndarray]:
    sets: List[np.ndarray] = []
    for m in range(cfg.n_sym):
        if threat == "candidate_aware":
            sets.append(np.argsort(probs[m])[-cfg.n_active :].astype(np.int32))
        elif threat == "fixed_d1":
            sets.append(
                pattern[m - 1].copy()
                if m >= 1
                else rng.choice(cfg.n_phys, cfg.n_active, replace=False).astype(np.int32)
            )
        elif threat == "fixed_d3":
            sets.append(
                pattern[m - 3].copy()
                if m >= 3
                else rng.choice(cfg.n_phys, cfg.n_active, replace=False).astype(np.int32)
            )
        elif threat == "delay_uniform":
            delay = int(rng.integers(1, cfg.max_delay + 1))
            sets.append(
                pattern[m - delay].copy()
                if m >= delay
                else rng.choice(cfg.n_phys, cfg.n_active, replace=False).astype(np.int32)
            )
        elif threat == "oracle_best_lag":
            # Clairvoyant upper bound: uses current true set pattern[m] to
            # select the lag that maximizes collision.  Not realisable.
            if m == 0:
                sets.append(rng.choice(cfg.n_phys, cfg.n_active, replace=False).astype(np.int32))
            else:
                delays = range(1, min(cfg.max_delay, m) + 1)
                best = max(
                    delays,
                    key=lambda d: len(np.intersect1d(pattern[m], pattern[m - d])),
                )
                sets.append(pattern[m - best].copy())
        elif threat == "causal_adaptive_lag":
            if causal_state is None:
                raise ValueError("causal_adaptive_lag requires an explicit CausalLagState")
            d = causal_state.select_lag(m, cfg, rng)
            if d == 0:
                chosen = rng.choice(cfg.n_phys, cfg.n_active, replace=False).astype(np.int32)
            else:
                chosen = pattern[m - d].copy()
            sets.append(chosen)
            n_hit = len(np.intersect1d(chosen, pattern[m]))
            causal_state.observe(d, n_hit / cfg.n_active, causal_feedback_rng or rng)
        else:
            raise ValueError(f"Unknown threat: {threat}")
    return sets


def viterbi_decode_llr(llrs: np.ndarray) -> np.ndarray:
    observations = llrs.reshape(-1, 2)
    n_steps = observations.shape[0]
    metrics = np.full(64, 1e30)
    metrics[0] = 0.0
    prev_state = np.zeros((n_steps, 64), dtype=np.uint8)
    prev_input = np.zeros((n_steps, 64), dtype=np.uint8)
    coded_bits = OUTPUT_BITS.reshape(-1, 2)
    signs = 1.0 - 2.0 * coded_bits.astype(float)
    for t, llr_pair in enumerate(observations):
        branch = -0.5 * np.sum(signs * llr_pair[None, :], axis=1)
        candidates = metrics[TRANS_PREV] + branch
        incoming_candidates = candidates[INCOMING]
        choice = np.argmin(incoming_candidates, axis=1)
        selected = INCOMING[np.arange(64), choice]
        metrics = candidates[selected]
        prev_state[t] = TRANS_PREV[selected]
        prev_input[t] = TRANS_INPUT[selected]
    state = 0
    decoded = np.zeros(n_steps, dtype=np.uint8)
    for t in range(n_steps - 1, -1, -1):
        decoded[t] = prev_input[t, state]
        state = int(prev_state[t, state])
    return decoded[:-6]


def mixture_llrs(samples: np.ndarray, v0: np.ndarray, v1: np.ndarray, prior: np.ndarray) -> np.ndarray:
    dist = np.abs(samples[..., None] - QPSK) ** 2
    log_clean = np.log1p(-prior[..., None]) - np.log(v0[..., None]) - dist / v0[..., None]
    log_jam = np.log(prior[..., None]) - np.log(v1[..., None]) - dist / v1[..., None]
    mix = np.logaddexp(log_clean, log_jam)
    llrs = np.empty(samples.size * 2)
    flat = mix.reshape(-1, 4)
    for bit in (0, 1):
        zero = QPSK_BITS[:, bit] == 0
        one = ~zero
        llrs[bit::2] = logsumexp(flat[:, zero], axis=1) - logsumexp(flat[:, one], axis=1)
    return llrs


def transmit_frame(
    method: str,
    threat: str,
    receiver: str,
    cfg: AdvancedConfig,
    frame: int,
    pattern: Optional[np.ndarray] = None,
    jam_sets: Optional[List[np.ndarray]] = None,
) -> Dict[str, float]:
    rng = seeded_rng(cfg.seed, "advanced", method, threat, receiver, frame)
    if pattern is None or jam_sets is None:
        pattern_rng = seeded_rng(cfg.seed, "advanced-pattern", method, frame)
        jammer_rng = seeded_rng(cfg.seed, "advanced-jammer", method, threat, frame)
        pattern, probs, _ = generate_sequence(method, cfg, pattern_rng)
        state = CausalLagState.create(cfg) if threat == "causal_adaptive_lag" else None
        jam_sets = jammer_sets(threat, pattern, probs, cfg, jammer_rng, state)

    n_qpsk = cfg.n_active * cfg.n_sym
    info = rng.integers(0, 2, n_qpsk - 6, dtype=np.uint8)
    tx = qpsk_mod(conv_encode_k7(info)).reshape(cfg.n_sym, cfg.n_active)
    noise_var = 10 ** (-cfg.snr_db / 10.0)
    jsr = 10 ** (cfg.jsr_db / 10.0)
    rx = tx + math.sqrt(noise_var / 2) * (
        rng.standard_normal(tx.shape) + 1j * rng.standard_normal(tx.shape)
    )
    collision = np.zeros((cfg.n_sym, cfg.n_active), dtype=bool)
    jam_var = np.zeros(cfg.n_sym)
    for m, jam_bins in enumerate(jam_sets):
        mask = np.isin(pattern[m], jam_bins)
        collision[m] = mask
        var = cfg.n_active * jsr / max(len(jam_bins), 1)
        jam_var[m] = var
        n_hit = int(mask.sum())
        if n_hit:
            rx[m, mask] += math.sqrt(var / 2) * (
                rng.standard_normal(n_hit) + 1j * rng.standard_normal(n_hit)
            )

    v0 = np.full_like(rx.real, noise_var, dtype=float)
    width = np.asarray([len(j) for j in jam_sets], dtype=float)
    prior = np.repeat(np.clip(width / cfg.n_phys, 1e-4, 0.95)[:, None], cfg.n_active, axis=1)
    v1 = v0 + np.repeat(jam_var[:, None], cfg.n_active, axis=1)
    posterior = posterior_collision(rx, v0, v1, prior)

    if receiver == "mixllr":
        decoded = viterbi_decode_llr(mixture_llrs(rx, v0, v1, prior))
    else:
        soft = qpsk_soft(rx.reshape(-1))
        base_weights = np.repeat(1.0 / noise_var, soft.size)
        if receiver == "brw":
            effective = (1 - posterior) * v0 + posterior * v1
            weights = np.repeat(1.0 / np.maximum(effective.reshape(-1), 1e-8), 2)
        elif receiver == "hard_tuned":
            # Threshold chosen via independent smoke sweep: optimal ~0.30
            weights = base_weights.copy()
            weights[np.repeat((posterior > 0.30).reshape(-1), 2)] = 0.0
        elif receiver == "oracle":
            # Genie-aided: perfect collision knowledge for erasure
            weights = base_weights.copy()
            weights[np.repeat(collision.reshape(-1), 2)] = 0.0
        elif receiver == "none":
            weights = base_weights
        else:
            raise ValueError(f"Unknown receiver: {receiver}")
        decoded = viterbi_decode_weighted(soft, weights)

    errors = int(np.sum(decoded != info))
    return {
        "bit_errors": errors,
        "total_bits": int(info.size),
        "frame_errors": int(errors > 0),
        "total_frames": 1,
        "collisions": int(collision.sum()),
        "active_symbols": int(collision.size),
        "mean_posterior": float(np.mean(posterior)),
    }


def coded_experiment(profile: str, cfg: AdvancedConfig) -> List[Dict[str, object]]:
    comml_profile = profile in {"comml-smoke", "comml-stats"}
    methods = COMML_CODED_PATTERNS if comml_profile else CODED_PATTERNS
    threats = COMML_THREATS if comml_profile else THREATS
    receivers = COMML_RECEIVERS if comml_profile else RECEIVERS
    if profile in {"smoke", "comml-smoke"}:
        min_frames = max_frames = 20
    elif profile == "comml-stats":
        min_frames, max_frames = 2000, 5000
    elif profile == "stats":
        min_frames = max_frames = 2000
    else:
        min_frames = max_frames = 500
    rows: List[Dict[str, object]] = []
    total = len(methods) * len(threats) * len(receivers)
    idx = 0
    for method in methods:
        for threat in threats:
            causal_state = CausalLagState.create(cfg) if threat == "causal_adaptive_lag" else None
            receiver_totals: Dict[str, Dict[str, float]] = {}
            receiver_errors: Dict[str, List[int]] = {}
            receiver_started: Dict[str, float] = {}
            receiver_done: Dict[str, bool] = {}
            for receiver in receivers:
                receiver_totals[receiver] = {
                    "bit_errors": 0,
                    "total_bits": 0,
                    "frame_errors": 0,
                    "total_frames": 0,
                    "collisions": 0,
                    "active_symbols": 0,
                    "mean_posterior": 0.0,
                }
                receiver_errors[receiver] = []
                receiver_started[receiver] = time.perf_counter()
                receiver_done[receiver] = False

            for frame in range(max_frames):
                pattern_rng = seeded_rng(cfg.seed, "advanced-pattern", method, frame)
                jammer_rng = seeded_rng(cfg.seed, "advanced-jammer", method, threat, frame)
                pattern, probs, _ = generate_sequence(method, cfg, pattern_rng)
                jam_sets = jammer_sets(threat, pattern, probs, cfg, jammer_rng, causal_state)
                for receiver in receivers:
                    if receiver_done[receiver]:
                        continue
                    result = transmit_frame(
                        method, threat, receiver, cfg, frame, pattern=pattern, jam_sets=jam_sets
                    )
                    for key in receiver_totals[receiver]:
                        receiver_totals[receiver][key] += result[key]
                    receiver_errors[receiver].append(int(result["frame_errors"]))
                    if (
                        profile == "comml-stats"
                        and frame + 1 >= min_frames
                        and stats_sufficient(
                            int(receiver_totals[receiver]["frame_errors"]), frame + 1
                        )
                    ):
                        receiver_done[receiver] = True
                if all(receiver_done.values()):
                    break

            for receiver in receivers:
                idx += 1
                totals = receiver_totals[receiver]
                per_frame_errors = receiver_errors[receiver]
                elapsed = time.perf_counter() - receiver_started[receiver]
                ber = totals["bit_errors"] / totals["total_bits"]
                bler = totals["frame_errors"] / totals["total_frames"]
                ber_low, ber_high = wilson_interval(int(totals["bit_errors"]), int(totals["total_bits"]))
                bler_low, bler_high = wilson_interval(
                    int(totals["frame_errors"]), int(totals["total_frames"])
                )
                frame_arr = np.asarray(per_frame_errors, dtype=np.int32)
                bler_boot_mean, bler_boot_low, bler_boot_high = bootstrap_ci(frame_arr)
                sufficient = stats_sufficient(int(totals["frame_errors"]), int(totals["total_frames"]))
                zero_error = int(totals["frame_errors"]) == 0
                bler_upper_bound = zero_error_bound(int(totals["total_frames"])) if zero_error else bler_high
                row = {
                    "method": method,
                    "method_label": METHODS[method]["label"],
                    "threat": threat,
                    "receiver": receiver,
                    **totals,
                    "ber": ber,
                    "ber_ci_low": ber_low,
                    "ber_ci_high": ber_high,
                    "bler": bler,
                    "bler_ci_low": bler_low,
                    "bler_ci_high": bler_high,
                    "bler_boot_low": bler_boot_low,
                    "bler_boot_high": bler_boot_high,
                    "bler_upper_bound": bler_upper_bound,
                    "zero_error": zero_error,
                    "stats_sufficient": sufficient,
                    "stopped_early": int(totals["total_frames"]) < max_frames,
                    "collision_rate": totals["collisions"] / totals["active_symbols"],
                    "mean_posterior": totals["mean_posterior"] / totals["total_frames"],
                    "causal_lag_counts": (
                        json.dumps(causal_state.counts[1:].tolist())
                        if causal_state is not None else ""
                    ),
                    "causal_lag_estimates": (
                        json.dumps([round(value, 8) for value in causal_state.estimates[1:].tolist()])
                        if causal_state is not None else ""
                    ),
                    "elapsed_s": elapsed,
                }
                rows.append(row)
                sufficient_flag = "+" if sufficient else ("Z" if zero_error else "-")
                print(
                    f"[{idx:02d}/{total}] {method:9s} {threat:15s} {receiver:6s} "
                    f"BLER={bler:.3f} BER={ber:.3e} coll={row['collision_rate']:.3f} "
                    f"fe={int(totals['frame_errors'])}/{int(totals['total_frames'])} {sufficient_flag}",
                    flush=True,
                )
    return rows


def save_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_metadata() -> Dict[str, object]:
    """Return auditable source-control metadata without requiring a clean tree."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def write_manifest(result_dir: Path, profile: str, cfg: AdvancedConfig,
                   seeds: list, n_frames: object, output_files: list[str]) -> None:
    """Write run_manifest.json per v2 execution plan 3.2."""
    manifest = {
        "profile": profile,
        "finished_at": datetime.datetime.now().isoformat(),
        "command": " ".join(sys.argv),
        "python_version": sys.version,
        "platform": platform.platform(),
        "git": git_metadata(),
        "config": asdict(cfg),
        "seeds": seeds,
        "n_frames": n_frames,
        "causal_attack": {
            "state_lifecycle": "continuous per method-threat run",
            "action_information": "past lag scores and past post-slot collision feedback only",
            "feedback": "exact normalized collision count observed after each slot",
            "receiver_fairness": "one jammer trajectory generated per frame and shared by receivers",
            "epsilon": 0.10,
            "ema_alpha": 0.20,
        },
        "source_files": {},
        "output_files": {},
    }
    for source in ["redesign/advanced_experiment.py", "redesign/fair_grid_sim.py",
                   "redesign/innovation_sim.py"]:
        source_path = ROOT / source
        if source_path.exists():
            manifest["source_files"][source] = {"sha256": file_sha256(source_path)}
    for fname in output_files:
        fpath = result_dir / fname
        if fpath.exists():
            manifest["output_files"][fname] = {
                "sha256": file_sha256(fpath),
                "size_bytes": fpath.stat().st_size,
            }
    (result_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")


def write_comml_report(
    structural: List[Dict[str, object]],
    coded: List[Dict[str, object]],
    cfg: AdvancedConfig,
    report_path: Path,
) -> None:
    """Write the focused Communications Letters experiment report."""
    lines = [
        "# Communications Letters 核心实验结果",
        "",
        f"配置：N={cfg.n_phys}, S={cfg.n_active}, M={cfg.n_sym}, "
        f"SNR={cfg.snr_db} dB, JSR={cfg.jsr_db} dB。",
        "",
        "Causal adaptive jammer 使用跨帧连续显式状态；每个时隙先基于历史选择 lag，"
        "再在时隙结束后观察精确归一化碰撞反馈。每个方法-威胁组合只生成一条攻击轨迹。",
        "",
        "## Mixture-LLR BLER",
        "",
        "| 方法 | 威胁 | BLER [bootstrap 95% CI] | 帧错误/总帧 | 碰撞率 | 达到目标 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in coded:
        lines.append(
            f"| {row['method_label']} | {row['threat']} | {row['bler']:.4f} "
            f"[{row['bler_boot_low']:.4f}, {row['bler_boot_high']:.4f}] | "
            f"{int(row['frame_errors'])}/{int(row['total_frames'])} | "
            f"{row['collision_rate']:.4f} | {'YES' if row['stats_sufficient'] else 'NO'} |"
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- Random 是 candidate-aware 场景不可省略的核心比较对象。",
            "- MCSH-L2 是已知短时延 follower 的强基线。",
            "- PASH-cap 的主张是跨威胁折中，不是所有场景最优。",
            "- causal adaptive 结果依赖较强的精确 post-slot collision feedback 假设。",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_csv(path: Path) -> List[Dict[str, object]]:
    """Load CSV and convert numeric strings to float/int. Booleans are inferred from context."""
    rows = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            converted: Dict[str, object] = {}
            for key, val in row.items():
                if val == "True":
                    converted[key] = True
                elif val == "False":
                    converted[key] = False
                else:
                    try:
                        converted[key] = float(val)
                    except (ValueError, TypeError):
                        converted[key] = val
            # frame_errors and total_frames should be int
            for int_key in ("frame_errors", "total_frames", "bit_errors", "total_bits",
                           "collisions", "active_symbols", "worst_lag"):
                if int_key in converted and isinstance(converted[int_key], float):
                    converted[int_key] = int(converted[int_key])
            rows.append(converted)
    return rows


# Methods shown in each subplot (fewer = cleaner, chosen to convey the narrative)
SPECTRUM_METHODS = ["random", "bcd", "mcsh_l1", "mcsh_l2", "mcsh_l4", "mcsh_l6", "pash_c15"]
CODED_PLOT_METHODS = ["random", "bcd", "mcsh_l2", "pash_c15", "pash_c14"]   # 5 methods in (c)
ABLATION_METHODS = ["random", "bcd", "mcsh_l1", "mcsh_l2", "pash_c15", "pash_c14"]  # 6 methods in (d)


def plot_results(
    structural: List[Dict[str, object]],
    coded: List[Dict[str, object]],
    figure_dir: Path,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    # Taller figure to give (c)/(d) breathing room
    fig, axes = plt.subplots(2, 2, figsize=(8.6, 7.8))
    plt.subplots_adjust(left=0.06, right=0.98, top=0.95, bottom=0.06, hspace=0.38, wspace=0.22)

    cfg_text = "$N{=}512,\\,S{=}64,\\,M{=}32,\\,\\mathrm{SNR}{=}12\\,\\mathrm{dB},\\,\\mathrm{JSR}{=}5\\,\\mathrm{dB}$"
    fig.text(0.5, 0.01, cfg_text, ha="center", fontsize=7, color="#555555")

    colors = {
        "random": "#222222", "bcd": "#8B4513", "sbs": "#E3720E",
        "mcsh_l1": "#56B4E9", "mcsh_l2": "#0072B2", "mcsh_l4": "#009E73", "mcsh_l6": "#D55E00",
        "pash_a08": "#CC79A7", "pash_a14": "#984EA3",
        "pash_c15": "#F0E442", "pash_c14": "#E69F00",
    }
    short = {
        "random": "Rand", "bcd": "BCD", "sbs": "SBS",
        "mcsh_l1": "M1", "mcsh_l2": "M2", "mcsh_l4": "M4", "mcsh_l6": "M6",
        "pash_a08": "P.8", "pash_a14": "P1.4",
        "pash_c15": "Pc15", "pash_c14": "Pc14",
    }

    # ── (a) Delay-collision spectrum ──────────────────────────────────
    # Line-style mapping to help distinguish overlapping curves
    lag_styles = {
        "random": ("o", "-", 1.5), "bcd": ("s", "--", 1.5),
        "mcsh_l1": ("^", "-", 1.5), "mcsh_l2": ("D", "-", 1.5),
        "mcsh_l4": ("h", "--", 1.5), "mcsh_l6": ("p", "-", 1.5),
        "pash_c15": ("*", "--", 2.0),
    }
    for row in structural:
        if row["method"] not in SPECTRUM_METHODS:
            continue
        m, ls, lw = lag_styles.get(row["method"], ("o", "-", 1.2))
        lags = np.arange(1, 13)
        axes[0, 0].plot(lags, [row[f"lag_{lag}"] for lag in lags],
                        marker=m, markersize=4.5, linestyle=ls, linewidth=lw,
                        color=colors[row["method"]],
                        label=METHODS[row["method"]]["label"],
                        markeredgewidth=0.3, markeredgecolor="white")
    axes[0, 0].axhline(64 / 512, color="black", linestyle=":", linewidth=0.8, label="$S/N$")
    axes[0, 0].set_title("(a) Delay-collision spectrum  —  dashed = probabilistic, solid = reactive", fontsize=9)
    axes[0, 0].set_xlabel("Follower delay $d$")
    axes[0, 0].set_ylabel("Collision rate")
    axes[0, 0].grid(True, linestyle=":", linewidth=0.55)
    axes[0, 0].legend(frameon=False, fontsize=6, ncol=2, loc="upper right")

    # ── (b) Risk-predictability tradeoff ───────────────────────────────
    for row in structural:
        risk = max(row["worst_lag_collision"], row["candidate_collision"])
        axes[0, 1].scatter(row["short_delay_collision"], risk,
                           s=90, color=colors[row["method"]],
                           label=row["label"], edgecolors="white", linewidth=0.3)
        axes[0, 1].annotate(short[row["method"]],
                            (row["short_delay_collision"], risk),
                            xytext=(3, 3), textcoords="offset points", fontsize=7)
    axes[0, 1].axhline(64 / 512, color="black", linestyle=":", linewidth=0.8)
    axes[0, 1].axvline(64 / 512, color="black", linestyle=":", linewidth=0.8)
    axes[0, 1].set_title("(b) Risk-predictability tradeoff", fontsize=9)
    axes[0, 1].set_xlabel("Mean collision for $d=1,2$")
    axes[0, 1].set_ylabel("Max(worst lag, candidate-aware)")
    axes[0, 1].grid(True, linestyle=":", linewidth=0.55)

    # ── (c) Coded stress test (5 methods, mixture-LLR) ─────────────────
    threats = ["fixed_d1", "fixed_d3", "delay_uniform", "oracle_best_lag", "causal_adaptive_lag", "candidate_aware"]
    threat_labels = ["$d{=}1$", "$d{=}3$", "rand.\ndelay", "oracle\nbest", "causal\nadapt", "cand.\naware"]
    x = np.arange(len(threats))
    width = 0.16
    mix = [row for row in coded if row["receiver"] == "mixllr"]
    n_coded = len(CODED_PLOT_METHODS)
    all_bar_tops: List[float] = []
    for i, method in enumerate(CODED_PLOT_METHODS):
        vals, lows, highs, fe_counts, is_zero_list = [], [], [], [], []
        for threat in threats:
            row = next(r for r in mix if r["method"] == method and r["threat"] == threat)
            is_zero = row.get("zero_error", False)
            bler_val = row.get("bler_upper_bound", row["bler"]) if is_zero else row["bler"]
            vals.append(bler_val)
            lo = row.get("bler_boot_low", row["bler_ci_low"])
            hi = row.get("bler_boot_high", row["bler_ci_high"])
            lows.append(max(bler_val - lo, 0))
            highs.append(max(hi - bler_val, 0))
            fe_counts.append(int(row["frame_errors"]))
            is_zero_list.append(is_zero)
            all_bar_tops.append(bler_val + highs[-1])
        offset = (i - (n_coded - 1) / 2) * width
        axes[1, 0].bar(x + offset, vals, width=width, color=colors[method],
                       label=METHODS[method]["label"], edgecolor="white", linewidth=0.3)
        for j in range(len(threats)):
            if is_zero_list[j]:
                axes[1, 0].bar(x[j] + offset, vals[j], width=width,
                               color="none", edgecolor="#AA0000", hatch="//", linewidth=1.0)
        axes[1, 0].errorbar(x + offset, vals, yerr=[lows, highs],
                            fmt="none", ecolor="black", capsize=2, linewidth=0.7)
        # Place annotations: inside tall bars (black text), above short ones
        for j in range(len(threats)):
            label = "▲" + str(fe_counts[j]) if is_zero_list[j] else str(fe_counts[j])
            bar_h = vals[j]
            if bar_h > 0.40:
                # Inside-bar — black text, small font; safe for light-colored bars
                axes[1, 0].text(x[j] + offset, bar_h * 0.5, label, fontsize=4.5,
                                ha="center", va="center", color="#222222")
            else:
                axes[1, 0].annotate(label, (x[j] + offset, bar_h),
                                    xytext=(0, 4), textcoords="offset points",
                                    fontsize=5, ha="center", va="bottom",
                                    color="#AA0000" if is_zero_list[j] else "#444444",
                                    annotation_clip=False)
    ymax_c = max(all_bar_tops) * 1.18 if all_bar_tops else 1.0
    axes[1, 0].set_ylim(0, max(ymax_c, 0.05))
    axes[1, 0].set_xticks(x, threat_labels)
    axes[1, 0].set_ylabel("BLER")
    axes[1, 0].set_title("(c) Coded stress test (mixture-LLR)", fontsize=9)
    axes[1, 0].grid(True, axis="y", linestyle=":", linewidth=0.55)
    axes[1, 0].legend(frameon=False, fontsize=5.5, ncol=3, loc="upper right")

    # ── (d) Receiver ablation (3 methods × 5 receivers) ────────────────
    candidate = [row for row in coded
                 if row["threat"] == "candidate_aware" and row["method"] in ABLATION_METHODS]
    receiver_colors = {"none": "#999999", "brw": "#E69F00", "hard_tuned": "#CC3311",
                       "oracle": "#33BB33", "mixllr": "#56B4E9"}
    x2 = np.arange(len(ABLATION_METHODS))
    n_recv = len(RECEIVERS)
    width2 = 0.15
    all_bar_tops_d: List[float] = []
    for ridx, receiver in enumerate(RECEIVERS):
        values, lows, highs, fe_counts, is_zero_list = [], [], [], [], []
        for method in ABLATION_METHODS:
            row = next(x for x in candidate if x["method"] == method and x["receiver"] == receiver)
            is_zero = row.get("zero_error", False)
            bler_val = row.get("bler_upper_bound", row["bler"]) if is_zero else row["bler"]
            values.append(bler_val)
            lo = row.get("bler_boot_low", row["bler_ci_low"])
            hi = row.get("bler_boot_high", row["bler_ci_high"])
            lows.append(max(bler_val - lo, 0))
            highs.append(max(hi - bler_val, 0))
            fe_counts.append(int(row["frame_errors"]))
            is_zero_list.append(is_zero)
            all_bar_tops_d.append(bler_val + highs[-1])
        xpos = x2 + (ridx - (n_recv - 1) / 2) * width2
        axes[1, 1].bar(xpos, values, width=width2, color=receiver_colors[receiver],
                       label=receiver, edgecolor="white", linewidth=0.3)
        for j in range(len(ABLATION_METHODS)):
            if is_zero_list[j]:
                axes[1, 1].bar(xpos[j], values[j], width=width2,
                               color="none", edgecolor="#AA0000", hatch="//", linewidth=1.0)
        axes[1, 1].errorbar(xpos, values, yerr=[lows, highs],
                            fmt="none", ecolor="black", capsize=2, linewidth=0.8)
        for j in range(len(ABLATION_METHODS)):
            label = "▲" + str(fe_counts[j]) if is_zero_list[j] else str(fe_counts[j])
            bar_h = values[j]
            if bar_h > 0.40:
                axes[1, 1].text(xpos[j], bar_h * 0.5, label, fontsize=4.5,
                                ha="center", va="center", color="#222222")
            else:
                axes[1, 1].annotate(label, (xpos[j], bar_h),
                                    xytext=(0, 4), textcoords="offset points",
                                    fontsize=5, ha="center", va="bottom",
                                    color="#AA0000" if is_zero_list[j] else "#444444",
                                    annotation_clip=False)
    ymax_d = max(all_bar_tops_d) * 1.18 if all_bar_tops_d else 1.0
    axes[1, 1].set_ylim(0, max(ymax_d, 0.05))
    axes[1, 1].set_xticks(x2, ["Rand", "BCD", "MCSH\n$L_h{=}1$", "MCSH\n$L_h{=}2$", "PASH\n0.15", "PASH\n0.14"])
    axes[1, 1].set_ylabel("BLER")
    axes[1, 1].set_title("(d) Receiver ablation (candidate-aware)", fontsize=9)
    axes[1, 1].grid(True, axis="y", linestyle=":", linewidth=0.55)
    # Compact horizontal legend below title
    axes[1, 1].legend(frameon=False, fontsize=6, ncol=3, loc="upper right")

    fig.savefig(figure_dir / "fig7_adversarial_pash.pdf", bbox_inches="tight")
    fig.savefig(figure_dir / "fig7_adversarial_pash.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_report(
    structural: List[Dict[str, object]],
    coded: List[Dict[str, object]],
    cfg: AdvancedConfig,
    report_path: Path,
) -> None:
    best_pash = min(
        [row for row in structural if row["method"].startswith("pash")],
        key=lambda row: max(row["worst_lag_collision"], row["candidate_collision"]),
    )
    mcsh2 = next(row for row in structural if row["method"] == "mcsh_l2")
    mcsh6 = next(row for row in structural if row["method"] == "mcsh_l6")
    pash_mix = [
        row
        for row in coded
        if row["method"] == best_pash["method"] and row["receiver"] == "mixllr"
    ]
    mcsh_mix = [row for row in coded if row["method"] == "mcsh_l2" and row["receiver"] == "mixllr"]
    pash_c14_mix = [row for row in coded if row["method"] == "pash_c14" and row["receiver"] == "mixllr"]
    pash_c15_mix = [row for row in coded if row["method"] == "pash_c15" and row["receiver"] == "mixllr"]
    lines = [
        "# 高水平实验增强结果：PASH 与强干扰机",
        "",
        f"配置: N={cfg.n_phys}, S={cfg.n_active}, M={cfg.n_sym}, "
        f"Es/N0={cfg.snr_db} dB, JSR={cfg.jsr_db} dB. 编码实验以 BLER 为主指标。",
        "",
        "## 结构性结果",
        "",
        "| 方法 | d=1,2 平均碰撞 | 最坏时延碰撞 | 候选池感知碰撞 | 使用频率 CV |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in structural:
        lines.append(
            f"| {row['label']} | {row['short_delay_collision']:.3f} | "
            f"{row['worst_lag_collision']:.3f} (d={row['worst_lag']}) | "
            f"{row['candidate_collision']:.3f} | {row['usage_cv']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"MCSH L_h=2 的最坏结构风险为 {max(mcsh2['worst_lag_collision'], mcsh2['candidate_collision']):.3f}; "
            f"MCSH L_h=6 上升到 {max(mcsh6['worst_lag_collision'], mcsh6['candidate_collision']):.3f}。",
            f"最佳 PASH 变体 {best_pash['label']} 将该风险控制在 "
            f"{max(best_pash['worst_lag_collision'], best_pash['candidate_collision']):.3f}, "
            "代价是短时延碰撞不再为零。",
            "",
            "## 编码强对抗结果（mixture-LLR）",
            "",
            "| 威胁 | MCSH Lh=2 BLER [boot CI] | 最佳 PASH BLER [boot CI] | MCSH 碰撞 | PASH 碰撞 | MCSH fe | PASH fe |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for threat in THREATS:
        mrow = next(row for row in mcsh_mix if row["threat"] == threat)
        prow = next(row for row in pash_mix if row["threat"] == threat)
        m_ci = f"[{mrow.get('bler_boot_low', mrow['bler_ci_low']):.3f},{mrow.get('bler_boot_high', mrow['bler_ci_high']):.3f}]"
        p_ci = f"[{prow.get('bler_boot_low', prow['bler_ci_low']):.3f},{prow.get('bler_boot_high', prow['bler_ci_high']):.3f}]"
        m_fe = int(mrow["frame_errors"])
        p_fe = int(prow["frame_errors"])
        m_suf = "*" if not mrow.get("stats_sufficient", m_fe >= 100) else ""
        p_suf = "*" if not prow.get("stats_sufficient", p_fe >= 100) else ""
        lines.append(
            f"| {threat} | {mrow['bler']:.3f} {m_ci} | {prow['bler']:.3f} {p_ci} | "
            f"{mrow['collision_rate']:.3f} | {prow['collision_rate']:.3f} | "
            f"{m_fe}{m_suf}/{int(mrow['total_frames'])} | {p_fe}{p_suf}/{int(prow['total_frames'])} |"
        )
    lines.extend(
        [
            "",
            "* 标记表示帧错误数未达到 100 的统计目标。boot CI = bootstrap 95% 置信区间。",
            "",
            "## PASH-cap 参数对比：pash_c14 vs pash_c15",
            "",
            "此节为参数选择决策提供直接编码证据。",
            "",
            "| 威胁 | pash_c14 BLER [boot CI] | pash_c15 BLER [boot CI] | c14 fe | c15 fe | CI 重叠 | BLER 差异方向 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for threat in THREATS:
        r14 = next(row for row in pash_c14_mix if row["threat"] == threat)
        r15 = next(row for row in pash_c15_mix if row["threat"] == threat)
        c14_lo = r14.get("bler_boot_low", r14["bler_ci_low"])
        c14_hi = r14.get("bler_boot_high", r14["bler_ci_high"])
        c15_lo = r15.get("bler_boot_low", r15["bler_ci_low"])
        c15_hi = r15.get("bler_boot_high", r15["bler_ci_high"])
        c14_ci = f"[{c14_lo:.3f},{c14_hi:.3f}]"
        c15_ci = f"[{c15_lo:.3f},{c15_hi:.3f}]"
        diff = r14["bler"] - r15["bler"]
        direction = "c14 lower" if diff < -0.005 else ("c15 lower" if diff > 0.005 else "no significant diff")
        overlap = "YES" if (c14_lo <= c15_hi and c15_lo <= c14_hi) else "NO"
        c14_fe = int(r14["frame_errors"])
        c15_fe = int(r15["frame_errors"])
        lines.append(
            f"| {threat} | {r14['bler']:.3f} {c14_ci} | {r15['bler']:.3f} {c15_ci} | "
            f"{c14_fe}/{int(r14['total_frames'])} | {c15_fe}/{int(r15['total_frames'])} | {overlap} | {direction} |"
        )
    lines.extend(
        [
            "",
            "### 参数决策判据",
            "",
            "1. 若 pash_c14 的 candidate-aware BLER 不高于 pash_c15, 或差异在置信区间内, "
            "则 pash_c14 是强对抗优先点。",
            "2. 若 pash_c14 的 best-lag BLER 不高于 pash_c15, 则 pash_c14 在"
            "最坏情况滞后下更有优势。",
            "3. 若 fixed_d1 下 pash_c14 明显退化, 论文必须说明 cap=0.14 是强对抗优先点, "
            "而 cap=0.15 是短时延保护更保守点。",
            "4. 若 pash_c14 coded 结果全面差于 pash_c15, 则保留 pash_c15, "
            "把参数扫掠作为参数选择诊断, 不替换论文主图。",
            "",
            "## 论文改写建议",
            "",
            "- 将主贡献从硬排斥 MCSH 改成短时延规避-条件可预测性的可调折中。",
            "- MCSH 保留为强短时延基线; PASH 作为面向未知/智能延迟干扰机的新方法。",
            "- 图 figures/paper/fig7_adversarial_pash.pdf 应替换原零延迟柱状图, "
            "因为它直接展示了审稿人最关心的 adversarial stress test。",
            "- 后续若要冲击更高水平, 还需把 PASH 的概率优化形式从启发式指数权重"
            "提升为带最坏候选池约束的凸优化或可证明近似算法。",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(profile: str, plot_only: bool = False, snr_db: float | None = None, jsr_db: float | None = None) -> None:
    cfg = AdvancedConfig()
    if snr_db is not None or jsr_db is not None:
        cfg = AdvancedConfig(
            snr_db=snr_db if snr_db is not None else 12.0,
            jsr_db=jsr_db if jsr_db is not None else 5.0,
        )
    if profile == "smoke":
        result_dir = SMOKE_RESULT_DIR
        figure_dir = SMOKE_FIGURE_DIR
        report_path = SMOKE_REPORT
    elif profile == "comml-smoke":
        result_dir = COMML_SMOKE_RESULT_DIR
        figure_dir = COMML_SMOKE_FIGURE_DIR
        report_path = COMML_SMOKE_REPORT
    elif profile == "comml-stats":
        result_dir = COMML_STATS_RESULT_DIR
        suffix = ""
        if snr_db is not None and snr_db != 12.0:
            suffix += f"_{int(snr_db)}dB"
        if jsr_db is not None and jsr_db != 5.0:
            suffix += f"_jsr{int(jsr_db)}dB"
        if suffix:
            result_dir = Path(str(COMML_STATS_RESULT_DIR) + suffix)
        figure_dir = FIGURE_DIR
        report_path = COMML_STATS_REPORT
        if suffix:
            report_path = Path(str(COMML_STATS_REPORT).replace(".md", f"{suffix}.md"))
    elif profile == "stats":
        result_dir = STATS_RESULT_DIR
        figure_dir = FIGURE_DIR
        report_path = STATS_REPORT
    else:
        result_dir = RESULT_DIR
        figure_dir = FIGURE_DIR
        report_path = REPORT

    if plot_only:
        structural = load_csv(result_dir / "structural_summary.csv")
        coded = load_csv(result_dir / "coded_summary.csv")
        print(f"Loaded {len(structural)} structural + {len(coded)} coded rows from {result_dir}")
    else:
        result_dir.mkdir(parents=True, exist_ok=True)
        if profile == "comml-smoke":
            structural = structural_experiment("smoke", cfg)
        elif profile == "comml-stats":
            structural = structural_experiment("paper", cfg)
        else:
            structural = structural_experiment(profile, cfg)
        coded = coded_experiment(profile, cfg)
        save_csv(result_dir / "structural_summary.csv", structural)
        save_csv(result_dir / "coded_summary.csv", coded)
        (result_dir / "config.json").write_text(
            json.dumps(
                {
                    "profile": profile,
                    "config": asdict(cfg),
                    "methods": METHODS,
                    "coded_methods": COMML_CODED_PATTERNS if profile.startswith("comml-") else CODED_PATTERNS,
                    "threats": COMML_THREATS if profile.startswith("comml-") else THREATS,
                    "receivers": COMML_RECEIVERS if profile.startswith("comml-") else RECEIVERS,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        seeds = list(range(5 if profile in {"smoke", "comml-smoke"} else 30))
        frames = {
            "smoke": 20,
            "comml-smoke": 20,
            "stats": 2000,
            "comml-stats": {"min": 2000, "max": 5000, "target_frame_errors": 100},
        }.get(profile, 500)
        write_manifest(result_dir, profile, cfg, seeds, frames,
                       ["structural_summary.csv", "coded_summary.csv", "config.json"])
    if profile.startswith("comml-"):
        write_comml_report(structural, coded, cfg, report_path)
    else:
        plot_results(structural, coded, figure_dir)
        write_report(structural, coded, cfg, report_path)
    print(f"Saved advanced results to {result_dir}")
    print(f"Saved advanced figure to {figure_dir}")
    print(f"Saved advanced report to {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=["smoke", "paper", "stats", "comml-smoke", "comml-stats"],
        default="paper",
    )
    parser.add_argument("--plot-only", action="store_true", help="Skip experiment, replot from existing CSV data")
    parser.add_argument("--snr", type=float, default=None, help="Override SNR (dB), e.g. --snr 9.0")
    parser.add_argument("--jsr", type=float, default=None, help="Override JSR (dB), e.g. --jsr 10.0")
    args = parser.parse_args()
    run(args.profile, plot_only=args.plot_only, snr_db=args.snr, jsr_db=args.jsr)


if __name__ == "__main__":
    main()
