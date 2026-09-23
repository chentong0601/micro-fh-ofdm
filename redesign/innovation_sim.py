#!/usr/bin/env python3
"""Extended evaluation for memory-constrained sparse hopping and BRW decoding."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from scipy.special import expit, logsumexp

from fair_grid_sim import (
    INCOMING,
    TRANS_EXPECTED,
    TRANS_INPUT,
    TRANS_PREV,
    conv_encode_k7,
    qpsk_mod,
    qpsk_soft,
    seeded_rng,
    wilson_interval,
)


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "innovation"
QPSK = qpsk_mod(np.array([0, 0, 0, 1, 1, 0, 1, 1], dtype=np.uint8))


@dataclass(frozen=True)
class ExtendedConfig:
    n_phys: int = 512
    n_active: int = 64
    n_sym: int = 8
    snr_db: float = 12.0
    jsr_db: float = 5.0
    pbj_rho: float = 0.25
    sweep_rho: float = 0.125
    sweep_step: int = 24
    channel: str = "awgn"
    csi_nmse_db: float = -300.0
    sync_error_prob: float = 0.0
    jammer_est_error_db: float = 0.0
    seed: int = 20260607


@dataclass(frozen=True)
class PointSpec:
    experiment: str
    scenario: str
    scheme: str
    x_name: str
    x_value: float
    frames: int
    cfg: ExtendedConfig


SCHEMES: Dict[str, Tuple[str, int, str]] = {
    "random_k7": ("random", 0, "none"),
    "random_hard": ("random", 0, "hard"),
    "random_brw": ("random", 0, "brw"),
    "random_oracle": ("random", 0, "oracle"),
    "mc1_k7": ("memory", 1, "none"),
    "mc2_k7": ("memory", 2, "none"),
    "mc4_k7": ("memory", 4, "none"),
    "mc6_k7": ("memory", 6, "none"),
    "mc2_hard": ("memory", 2, "hard"),
    "mc2_brw": ("memory", 2, "brw"),
    "mc2_oracle": ("memory", 2, "oracle"),
}


def random_pattern(cfg: ExtendedConfig, rng: np.random.Generator) -> np.ndarray:
    return np.vstack(
        [rng.choice(cfg.n_phys, cfg.n_active, replace=False) for _ in range(cfg.n_sym)]
    )


def memory_pattern(
    cfg: ExtendedConfig, rng: np.random.Generator, memory: int
) -> np.ndarray:
    """Greedy minimum-reuse set hopping with randomized tie breaking."""
    pattern = np.empty((cfg.n_sym, cfg.n_active), dtype=np.int32)
    for m in range(cfg.n_sym):
        recent = pattern[max(0, m - memory) : m].reshape(-1) if m else np.array([])
        counts = np.bincount(recent.astype(int), minlength=cfg.n_phys)
        tie = rng.random(cfg.n_phys)
        order = np.lexsort((tie, counts))
        pattern[m] = order[: cfg.n_active]
    return pattern


def make_pattern(
    cfg: ExtendedConfig, scheme: str, rng: np.random.Generator
) -> np.ndarray:
    kind, memory, _ = SCHEMES[scheme]
    if kind == "random":
        return random_pattern(cfg, rng)
    return memory_pattern(cfg, rng, memory)


def cyclic_block(start: int, width: int, n_phys: int) -> np.ndarray:
    return (start + np.arange(width)) % n_phys


def reactive_delay(scenario: str) -> int:
    return int(scenario.removeprefix("reactive_d"))


def jammer_sets(
    scenario: str,
    cfg: ExtendedConfig,
    pattern: np.ndarray,
    rng: np.random.Generator,
) -> List[np.ndarray]:
    if scenario == "none":
        return [np.array([], dtype=int) for _ in range(cfg.n_sym)]
    if scenario == "blind_pbj":
        width = max(1, round(cfg.pbj_rho * cfg.n_phys))
        return [
            cyclic_block(int(rng.integers(cfg.n_phys)), width, cfg.n_phys)
            for _ in range(cfg.n_sym)
        ]
    if scenario == "sweep":
        width = max(1, round(cfg.sweep_rho * cfg.n_phys))
        start = int(rng.integers(cfg.n_phys))
        return [
            cyclic_block(start + m * cfg.sweep_step, width, cfg.n_phys)
            for m in range(cfg.n_sym)
        ]
    if scenario.startswith("reactive_d"):
        delay = reactive_delay(scenario)
        sets = []
        for m in range(cfg.n_sym):
            if m < delay:
                sets.append(rng.choice(cfg.n_phys, cfg.n_active, replace=False))
            else:
                sets.append(pattern[m - delay].copy())
        return sets
    if scenario.startswith("reactive_union"):
        memory = int(scenario.removeprefix("reactive_union"))
        sets = []
        for m in range(cfg.n_sym):
            if m == 0:
                sets.append(rng.choice(cfg.n_phys, cfg.n_active, replace=False))
            else:
                sets.append(np.unique(pattern[max(0, m - memory) : m].reshape(-1)))
        return sets
    raise ValueError(f"Unknown scenario: {scenario}")


def channel_response(cfg: ExtendedConfig, rng: np.random.Generator) -> np.ndarray:
    profiles = {
        "awgn": ([0], [0]),
        "peda": ([0, 1, 2, 5], [0, -3.6, -7.2, -10.8]),
        "veha": ([0, 2, 4, 7, 10, 13], [0, -1, -9, -10, -15, -20]),
    }
    delays, powers_db = profiles[cfg.channel]
    if cfg.channel == "awgn":
        return np.ones(cfg.n_phys, dtype=complex)
    powers = 10 ** (np.asarray(powers_db) / 10.0)
    powers /= np.sum(powers)
    taps = np.zeros(max(delays) + 1, dtype=complex)
    taps[np.asarray(delays)] = np.sqrt(powers / 2) * (
        rng.standard_normal(len(delays)) + 1j * rng.standard_normal(len(delays))
    )
    response = np.fft.fft(taps, cfg.n_phys)
    response /= math.sqrt(float(np.mean(np.abs(response) ** 2)))
    return response


def estimate_channel(
    response: np.ndarray, cfg: ExtendedConfig, rng: np.random.Generator
) -> np.ndarray:
    if cfg.csi_nmse_db <= -200:
        return response.copy()
    nmse = 10 ** (cfg.csi_nmse_db / 10.0)
    error = math.sqrt(nmse / 2) * (
        rng.standard_normal(response.size) + 1j * rng.standard_normal(response.size)
    )
    return response + error


def marginal_log_likelihood(
    samples: np.ndarray, variances: np.ndarray
) -> np.ndarray:
    distances = np.abs(samples[..., None] - QPSK) ** 2
    return logsumexp(-distances / variances[..., None], axis=-1) - np.log(variances)


def posterior_collision(
    samples: np.ndarray,
    v0: np.ndarray,
    v1: np.ndarray,
    prior: np.ndarray,
) -> np.ndarray:
    log0 = marginal_log_likelihood(samples, v0) + np.log1p(-prior)
    log1 = marginal_log_likelihood(samples, v1) + np.log(prior)
    return expit(log1 - log0)


def viterbi_decode_weighted(soft_values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    observations = soft_values.reshape(-1, 2)
    bit_weights = weights.reshape(-1, 2)
    n_steps = observations.shape[0]
    metrics = np.full(64, 1e30)
    metrics[0] = 0.0
    prev_state = np.zeros((n_steps, 64), dtype=np.uint8)
    prev_input = np.zeros((n_steps, 64), dtype=np.uint8)
    for t, (obs, weight) in enumerate(zip(observations, bit_weights)):
        branch = np.sum(weight * (TRANS_EXPECTED - obs) ** 2, axis=1)
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


def receiver_pattern(
    pattern: np.ndarray, cfg: ExtendedConfig, rng: np.random.Generator
) -> Tuple[np.ndarray, int]:
    rx_pattern = pattern.copy()
    errors = 0
    for m in range(cfg.n_sym):
        if rng.random() < cfg.sync_error_prob:
            shift = int(rng.integers(1, cfg.n_phys))
            rx_pattern[m] = (rx_pattern[m] + shift) % cfg.n_phys
            errors += 1
    return rx_pattern, errors


def expected_width(scenario: str, cfg: ExtendedConfig) -> int:
    if scenario == "none":
        return 1
    if scenario == "blind_pbj":
        return max(1, round(cfg.pbj_rho * cfg.n_phys))
    if scenario == "sweep":
        return max(1, round(cfg.sweep_rho * cfg.n_phys))
    if scenario.startswith("reactive_union"):
        return min(
            cfg.n_phys,
            int(scenario.removeprefix("reactive_union")) * cfg.n_active,
        )
    return cfg.n_active


def transmit_frame(
    scenario: str,
    scheme: str,
    cfg: ExtendedConfig,
    frame_index: int,
) -> Dict[str, float]:
    _, memory, decoder = SCHEMES[scheme]
    signal_rng = seeded_rng(cfg.seed, "signal", scenario, cfg.snr_db, cfg.jsr_db, frame_index)
    pattern_rng = seeded_rng(cfg.seed, "pattern", scenario, frame_index)
    jammer_rng = seeded_rng(cfg.seed, "jammer", scenario, frame_index)
    channel_rng = seeded_rng(cfg.seed, "channel", cfg.channel, frame_index)
    sync_rng = seeded_rng(cfg.seed, "sync", scenario, cfg.sync_error_prob, frame_index)

    pattern = make_pattern(cfg, scheme, pattern_rng)
    n_qpsk = cfg.n_active * cfg.n_sym
    info = signal_rng.integers(0, 2, n_qpsk - 6, dtype=np.uint8)
    tx_symbols = qpsk_mod(conv_encode_k7(info)).reshape(cfg.n_sym, cfg.n_active)
    tx_grid = np.zeros((cfg.n_sym, cfg.n_phys), dtype=complex)
    for m in range(cfg.n_sym):
        tx_grid[m, pattern[m]] = tx_symbols[m]

    h = channel_response(cfg, channel_rng)
    h_est = estimate_channel(h, cfg, channel_rng)
    noise_var = 10 ** (-cfg.snr_db / 10.0)
    noise = math.sqrt(noise_var / 2) * (
        signal_rng.standard_normal(tx_grid.shape)
        + 1j * signal_rng.standard_normal(tx_grid.shape)
    )
    rx_grid = tx_grid * h[None, :] + noise

    jam_sets = jammer_sets(scenario, cfg, pattern, jammer_rng)
    jsr = 10 ** (cfg.jsr_db / 10.0)
    tx_collision = np.zeros((cfg.n_sym, cfg.n_active), dtype=bool)
    full_jam_mask = np.zeros_like(tx_grid, dtype=bool)
    jam_variances = np.zeros(cfg.n_sym)
    for m, jam_bins in enumerate(jam_sets):
        full_jam_mask[m, jam_bins] = True
        tx_collision[m] = full_jam_mask[m, pattern[m]]
        jam_var = cfg.n_active * jsr / max(len(jam_bins), 1)
        jam_variances[m] = jam_var
        rx_grid[m, jam_bins] += math.sqrt(jam_var / 2) * (
            jammer_rng.standard_normal(len(jam_bins))
            + 1j * jammer_rng.standard_normal(len(jam_bins))
        )

    rx_pattern, sync_errors = receiver_pattern(pattern, cfg, sync_rng)
    extracted = np.empty((cfg.n_sym, cfg.n_active), dtype=complex)
    h_used = np.empty_like(extracted)
    rx_collision = np.zeros_like(tx_collision)
    for m in range(cfg.n_sym):
        extracted[m] = rx_grid[m, rx_pattern[m]]
        h_used[m] = h_est[rx_pattern[m]]
        rx_collision[m] = full_jam_mask[m, rx_pattern[m]]
    equalized = extracted / (h_used + 1e-9)

    v0 = noise_var / np.maximum(np.abs(h_used) ** 2, 1e-8)
    width_est = expected_width(scenario, cfg)
    jsr_est = jsr * 10 ** (cfg.jammer_est_error_db / 10.0)
    jam_var_est = cfg.n_active * jsr_est / max(width_est, 1)
    v1 = v0 + jam_var_est / np.maximum(np.abs(h_used) ** 2, 1e-8)
    prior = np.full_like(v0, min(max(width_est / cfg.n_phys, 1e-4), 0.95))
    posterior = posterior_collision(equalized, v0, v1, prior)

    soft = qpsk_soft(equalized.reshape(-1))
    base_weights = np.repeat(1.0 / np.maximum(v0.reshape(-1), 1e-8), 2)
    if decoder == "brw":
        effective_var = (1 - posterior) * v0 + posterior * v1
        weights = np.repeat(1.0 / np.maximum(effective_var.reshape(-1), 1e-8), 2)
    elif decoder == "hard":
        weights = base_weights.copy()
        weights[np.repeat((posterior > 0.5).reshape(-1), 2)] = 0.0
    elif decoder == "oracle":
        weights = base_weights.copy()
        weights[np.repeat(rx_collision.reshape(-1), 2)] = 0.0
    else:
        weights = base_weights
    decoded = viterbi_decode_weighted(soft, weights)

    errors = int(np.sum(decoded != info))
    detected = posterior > 0.5
    positives = int(np.sum(rx_collision))
    negatives = int(np.sum(~rx_collision))
    tp = int(np.sum(detected & rx_collision))
    fp = int(np.sum(detected & ~rx_collision))
    per_symbol_collision = np.mean(tx_collision, axis=1)
    if cfg.n_sym > 1:
        adjacent_overlap = np.mean(
            [
                len(np.intersect1d(pattern[m], pattern[m - 1])) / cfg.n_active
                for m in range(1, cfg.n_sym)
            ]
        )
    else:
        adjacent_overlap = 0.0
    return {
        "bit_errors": errors,
        "total_bits": int(info.size),
        "frame_errors": int(errors > 0),
        "total_frames": 1,
        "collisions": int(np.sum(tx_collision)),
        "active_symbols": int(tx_collision.size),
        "collision_variance_sum": float(np.var(per_symbol_collision)),
        "max_symbol_collision_sum": float(np.max(per_symbol_collision)),
        "adjacent_overlap_sum": float(adjacent_overlap),
        "detected_collisions": tp,
        "false_alarms": fp,
        "positive_symbols": positives,
        "negative_symbols": negatives,
        "posterior_collision_sum": float(np.sum(posterior)),
        "sync_error_symbols": sync_errors,
    }


def aggregate_point(spec: PointSpec) -> Dict[str, object]:
    totals: Dict[str, float] = {
        "bit_errors": 0,
        "total_bits": 0,
        "frame_errors": 0,
        "total_frames": 0,
        "collisions": 0,
        "active_symbols": 0,
        "collision_variance_sum": 0.0,
        "max_symbol_collision_sum": 0.0,
        "adjacent_overlap_sum": 0.0,
        "detected_collisions": 0,
        "false_alarms": 0,
        "positive_symbols": 0,
        "negative_symbols": 0,
        "posterior_collision_sum": 0.0,
        "sync_error_symbols": 0,
    }
    started = time.perf_counter()
    for frame in range(spec.frames):
        result = transmit_frame(spec.scenario, spec.scheme, spec.cfg, frame)
        for key in totals:
            totals[key] += result[key]
    elapsed = time.perf_counter() - started
    ber = totals["bit_errors"] / totals["total_bits"]
    low, high = wilson_interval(int(totals["bit_errors"]), int(totals["total_bits"]))
    positives = totals["positive_symbols"]
    negatives = totals["negative_symbols"]
    frames = totals["total_frames"]
    return {
        "experiment": spec.experiment,
        "scenario": spec.scenario,
        "scheme": spec.scheme,
        "x_name": spec.x_name,
        "x_value": spec.x_value,
        "n_phys": spec.cfg.n_phys,
        "n_active": spec.cfg.n_active,
        "snr_db": spec.cfg.snr_db,
        "jsr_db": spec.cfg.jsr_db,
        "channel": spec.cfg.channel,
        "csi_nmse_db": spec.cfg.csi_nmse_db,
        "sync_error_prob": spec.cfg.sync_error_prob,
        "jammer_est_error_db": spec.cfg.jammer_est_error_db,
        **totals,
        "ber": ber,
        "ber_ci_low": low,
        "ber_ci_high": high,
        "fer": totals["frame_errors"] / frames,
        "collision_rate": totals["collisions"] / totals["active_symbols"],
        "collision_variance": totals["collision_variance_sum"] / frames,
        "max_symbol_collision": totals["max_symbol_collision_sum"] / frames,
        "adjacent_overlap": totals["adjacent_overlap_sum"] / frames,
        "pd": totals["detected_collisions"] / positives if positives else 0.0,
        "pfa": totals["false_alarms"] / negatives if negatives else 0.0,
        "mean_posterior": totals["posterior_collision_sum"] / totals["active_symbols"],
        "elapsed_s": elapsed,
        "ms_per_frame": 1000 * elapsed / frames,
    }


def spec(
    experiment: str,
    scenario: str,
    scheme: str,
    x_name: str,
    x_value: float,
    frames: int,
    base: ExtendedConfig,
    **updates: object,
) -> PointSpec:
    return PointSpec(
        experiment,
        scenario,
        scheme,
        x_name,
        x_value,
        frames,
        replace(base, **updates),
    )


def build_specs(profile: str) -> List[PointSpec]:
    base = ExtendedConfig()
    if profile == "smoke":
        return [
            spec("smoke", "reactive_d1", scheme, "scheme", i, 4, base)
            for i, scheme in enumerate(["random_k7", "mc2_k7", "mc2_brw", "mc2_oracle"])
        ]

    core_frames = 300
    robust_frames = 200
    specs: List[PointSpec] = []
    for scheme in ["random_k7", "mc2_k7"]:
        for snr in [0.0, 4.0, 8.0, 12.0]:
            specs.append(spec("no_jam", "none", scheme, "snr_db", snr, core_frames, base, snr_db=snr))

    core_scenarios = ["blind_pbj", "sweep", "reactive_d1", "reactive_d2", "reactive_union2"]
    core_schemes = [
        "random_k7",
        "random_brw",
        "mc2_k7",
        "mc2_hard",
        "mc2_brw",
        "mc2_oracle",
    ]
    for scenario in core_scenarios:
        for scheme in core_schemes:
            for snr in [4.0, 8.0, 12.0, 16.0]:
                specs.append(spec("core_ber", scenario, scheme, "snr_db", snr, core_frames, base, snr_db=snr))

    for delay in range(1, 7):
        for scheme in ["random_k7", "mc1_k7", "mc2_k7", "mc4_k7", "mc6_k7"]:
            specs.append(
                spec("delay_ablation", f"reactive_d{delay}", scheme, "delay", delay, robust_frames, base)
            )

    for scheme in ["random_k7", "random_brw", "mc2_k7", "mc2_brw"]:
        specs.append(spec("zero_delay_limit", "reactive_d0", scheme, "scheme", 0, robust_frames, base))

    for scenario in ["sweep", "reactive_d1"]:
        for jsr in [-5.0, 0.0, 5.0, 10.0, 15.0]:
            for scheme in ["random_k7", "random_brw", "mc2_k7", "mc2_brw"]:
                specs.append(spec("jsr_robustness", scenario, scheme, "jsr_db", jsr, robust_frames, base, jsr_db=jsr))

    for channel in ["awgn", "peda", "veha"]:
        for scheme in ["random_k7", "random_brw", "mc2_k7", "mc2_brw"]:
            specs.append(spec("channel_robustness", "reactive_d1", scheme, "channel_index", ["awgn", "peda", "veha"].index(channel), robust_frames, base, channel=channel))

    for nmse in [-300.0, -30.0, -20.0, -10.0]:
        for scheme in ["mc2_k7", "mc2_brw"]:
            specs.append(spec("csi_robustness", "reactive_d1", scheme, "csi_nmse_db", nmse, robust_frames, base, channel="veha", csi_nmse_db=nmse))

    for sync_prob in [0.0, 0.005, 0.01, 0.02, 0.05]:
        for scheme in ["mc2_k7", "mc2_brw"]:
            specs.append(spec("sync_robustness", "reactive_d1", scheme, "sync_error_prob", sync_prob, robust_frames, base, sync_error_prob=sync_prob))

    for mismatch in [-9.0, -6.0, -3.0, 0.0, 3.0, 6.0, 9.0]:
        specs.append(spec("brw_mismatch", "sweep", "mc2_brw", "jammer_est_error_db", mismatch, robust_frames, base, jammer_est_error_db=mismatch))

    for active in [32, 64, 96, 128, 160, 192]:
        for scheme in ["random_k7", "mc2_k7"]:
            specs.append(spec("load_boundary", "reactive_union2", scheme, "n_active", active, robust_frames, base, n_active=active))
    return specs


def run(specs: Sequence[PointSpec]) -> List[Dict[str, object]]:
    rows = []
    total = len(specs)
    for idx, point in enumerate(specs, start=1):
        print(
            f"[{idx:03d}/{total:03d}] {point.experiment:18s} {point.scenario:16s} "
            f"{point.scheme:12s} {point.x_name}={point.x_value}",
            flush=True,
        )
        row = aggregate_point(point)
        rows.append(row)
        print(
            f"  BER={row['ber']:.3e}, collision={row['collision_rate']:.3f}, "
            f"overlap={row['adjacent_overlap']:.3f}, Pd={row['pd']:.3f}, "
            f"{row['ms_per_frame']:.1f} ms/frame",
            flush=True,
        )
    return rows


def save(rows: List[Dict[str, object]], profile: str, result_dir: Path) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "config.json").write_text(
        json.dumps({"profile": profile, "base": asdict(ExtendedConfig())}, indent=2),
        encoding="utf-8",
    )
    (result_dir / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (result_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["smoke", "paper"], default="paper")
    parser.add_argument("--result-dir", type=Path)
    args = parser.parse_args()
    result_dir = args.result_dir or (
        ROOT / "tmp" / "innovation-smoke" if args.profile == "smoke" else RESULT_DIR
    )
    specs = build_specs(args.profile)
    rows = run(specs)
    save(rows, args.profile, result_dir)
    print(f"Saved {len(rows)} points to {result_dir}")


if __name__ == "__main__":
    main()
