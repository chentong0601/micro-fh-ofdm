#!/usr/bin/env python3
"""Fair common-grid evaluation for sparse subcarrier hopping.

The legacy MATLAB prototype uses different FFT sizes and sampling models for
fixed OFDM and FH-OFDM. This simulator deliberately places both schemes on the
same physical frequency grid. It focuses on collision dispersion and matched
rate coding rather than claiming an intrinsic spreading gain.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "redesign"
FIGURE_DIR = ROOT / "figures" / "redesign"


@dataclass(frozen=True)
class SimConfig:
    n_phys: int = 512
    n_active: int = 64
    n_sym: int = 8
    jsr_db: float = 5.0
    pbj_rho: float = 0.25
    sweep_rho: float = 0.125
    sweep_step: int = 24
    detector_k: float = 5.0
    seed: int = 20260607
    n_frames_blind: int = 2000
    n_frames_coded: int = 300


SCHEMES = {
    "fixed_uncoded": ("fixed", False, "none"),
    "hop_uncoded": ("hop", False, "none"),
    "fixed_k7": ("fixed", True, "none"),
    "hop_k7": ("hop", True, "none"),
    "hop_k7_practical": ("hop", True, "practical"),
    "hop_k7_oracle": ("hop", True, "oracle"),
}

SCENARIO_SCHEMES = {
    "blind_pbj": ["fixed_uncoded", "hop_uncoded"],
    "sweep": ["fixed_k7", "hop_k7", "hop_k7_practical", "hop_k7_oracle"],
    "reactive": ["fixed_k7", "hop_k7", "hop_k7_practical", "hop_k7_oracle"],
}


def seeded_rng(*items: object) -> np.random.Generator:
    raw = "|".join(str(x) for x in items).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(raw).digest()[:8], "little")
    return np.random.default_rng(seed)


def qpsk_mod(bits: np.ndarray) -> np.ndarray:
    pairs = bits.reshape(-1, 2).astype(float)
    return ((1 - 2 * pairs[:, 0]) + 1j * (1 - 2 * pairs[:, 1])) / math.sqrt(2)


def qpsk_soft(symbols: np.ndarray) -> np.ndarray:
    soft = np.empty(symbols.size * 2, dtype=float)
    soft[0::2] = math.sqrt(2) * symbols.real
    soft[1::2] = math.sqrt(2) * symbols.imag
    return soft


def qpsk_hard(symbols: np.ndarray) -> np.ndarray:
    bits = np.empty(symbols.size * 2, dtype=np.uint8)
    bits[0::2] = symbols.real < 0
    bits[1::2] = symbols.imag < 0
    return bits


def build_trellis() -> Tuple[np.ndarray, np.ndarray]:
    generators = np.array(
        [[1, 1, 1, 1, 0, 0, 1], [1, 0, 1, 1, 0, 1, 1]], dtype=np.uint8
    )
    next_state = np.zeros((64, 2), dtype=np.uint8)
    outputs = np.zeros((64, 2, 2), dtype=np.uint8)
    for state in range(64):
        memory = np.array([(state >> i) & 1 for i in range(6)], dtype=np.uint8)
        for bit in (0, 1):
            word = np.concatenate(([bit], memory))
            outputs[state, bit] = (generators @ word) % 2
            next_state[state, bit] = ((state << 1) & 0b111110) | bit
    return next_state, outputs


NEXT_STATE, OUTPUT_BITS = build_trellis()
TRANS_PREV = np.repeat(np.arange(64, dtype=np.uint8), 2)
TRANS_INPUT = np.tile(np.arange(2, dtype=np.uint8), 64)
TRANS_NEXT = NEXT_STATE.reshape(-1)
TRANS_EXPECTED = 1.0 - 2.0 * OUTPUT_BITS.reshape(-1, 2).astype(float)
INCOMING = np.vstack([np.flatnonzero(TRANS_NEXT == state) for state in range(64)])


def conv_encode_k7(info_bits: np.ndarray) -> np.ndarray:
    bits = np.concatenate([info_bits.astype(np.uint8), np.zeros(6, dtype=np.uint8)])
    state = 0
    out = np.empty(bits.size * 2, dtype=np.uint8)
    for idx, bit in enumerate(bits):
        out[2 * idx : 2 * idx + 2] = OUTPUT_BITS[state, bit]
        state = int(NEXT_STATE[state, bit])
    assert state == 0
    return out


def viterbi_decode_k7(soft_values: np.ndarray) -> np.ndarray:
    """Terminated soft Viterbi decoder; zero-valued soft inputs are erasures."""
    observations = soft_values.reshape(-1, 2)
    n_steps = observations.shape[0]
    inf = 1e30
    metrics = np.full(64, inf)
    metrics[0] = 0.0
    prev_state = np.zeros((n_steps, 64), dtype=np.uint8)
    prev_input = np.zeros((n_steps, 64), dtype=np.uint8)

    for t, obs in enumerate(observations):
        branch = np.sum((TRANS_EXPECTED - obs) ** 2, axis=1)
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


def fixed_pattern(cfg: SimConfig) -> np.ndarray:
    start = (cfg.n_phys - cfg.n_active) // 2
    bins = np.arange(start, start + cfg.n_active)
    return np.tile(bins, (cfg.n_sym, 1))


def hopping_pattern(cfg: SimConfig, rng: np.random.Generator) -> np.ndarray:
    return np.vstack(
        [rng.choice(cfg.n_phys, cfg.n_active, replace=False) for _ in range(cfg.n_sym)]
    )


def cyclic_block(start: int, width: int, n_phys: int) -> np.ndarray:
    return (start + np.arange(width)) % n_phys


def jammer_bins(
    scenario: str,
    cfg: SimConfig,
    pattern: np.ndarray,
    rng: np.random.Generator,
) -> List[np.ndarray]:
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
    if scenario == "reactive":
        first = rng.choice(cfg.n_phys, cfg.n_active, replace=False)
        return [first] + [pattern[m - 1].copy() for m in range(1, cfg.n_sym)]
    raise ValueError(f"Unknown scenario: {scenario}")


def robust_detector(symbols: np.ndarray, cfg: SimConfig) -> np.ndarray:
    """Per-symbol robust energy detector over known active bins."""
    powers = np.abs(symbols) ** 2
    masks = np.zeros_like(powers, dtype=bool)
    for m in range(cfg.n_sym):
        med = float(np.median(powers[m]))
        mad = float(np.median(np.abs(powers[m] - med)))
        sigma = max(1.4826 * mad, 1e-6)
        masks[m] = powers[m] > med + cfg.detector_k * sigma
    return masks


def transmit_frame(
    scenario: str,
    scheme: str,
    snr_db: float,
    cfg: SimConfig,
    frame_index: int,
) -> Dict[str, int]:
    pattern_kind, coded, erasure_kind = SCHEMES[scheme]
    comparison_group = "coded" if coded else "uncoded"
    pattern_group = f"{pattern_kind}_{comparison_group}"
    rng = seeded_rng(cfg.seed, "signal", scenario, comparison_group, snr_db, frame_index)
    pattern_rng = seeded_rng(cfg.seed, "pattern", scenario, pattern_group, frame_index)
    jammer_rng = seeded_rng(cfg.seed, "jammer", scenario, frame_index)
    pattern = fixed_pattern(cfg) if pattern_kind == "fixed" else hopping_pattern(cfg, pattern_rng)

    n_qpsk = cfg.n_active * cfg.n_sym
    if coded:
        n_info = n_qpsk - 6
        info = rng.integers(0, 2, n_info, dtype=np.uint8)
        tx_bits = conv_encode_k7(info)
    else:
        info = rng.integers(0, 2, 2 * n_qpsk, dtype=np.uint8)
        tx_bits = info

    tx_symbols = qpsk_mod(tx_bits).reshape(cfg.n_sym, cfg.n_active)
    jam_sets = jammer_bins(scenario, cfg, pattern, jammer_rng)
    noise_var = 10 ** (-snr_db / 10.0)
    jsr = 10 ** (cfg.jsr_db / 10.0)
    rx_symbols = np.empty_like(tx_symbols)
    collision_mask = np.zeros((cfg.n_sym, cfg.n_active), dtype=bool)

    for m in range(cfg.n_sym):
        jam_set = np.zeros(cfg.n_phys, dtype=bool)
        jam_set[jam_sets[m]] = True
        collisions = jam_set[pattern[m]]
        collision_mask[m] = collisions

        noise = math.sqrt(noise_var / 2) * (
            rng.standard_normal(cfg.n_active) + 1j * rng.standard_normal(cfg.n_active)
        )
        # The jammer has total average energy N_active*JSR per physical symbol.
        jam_var = cfg.n_active * jsr / max(len(jam_sets[m]), 1)
        jam = np.zeros(cfg.n_active, dtype=complex)
        n_collisions = int(np.sum(collisions))
        if n_collisions:
            jam[collisions] = math.sqrt(jam_var / 2) * (
                rng.standard_normal(n_collisions) + 1j * rng.standard_normal(n_collisions)
            )
        rx_symbols[m] = tx_symbols[m] + noise + jam

    practical_mask = robust_detector(rx_symbols, cfg)
    if coded:
        soft = qpsk_soft(rx_symbols.reshape(-1))
        if erasure_kind == "oracle":
            bit_mask = np.repeat(collision_mask.reshape(-1), 2)
            soft[bit_mask] = 0.0
        elif erasure_kind == "practical":
            bit_mask = np.repeat(practical_mask.reshape(-1), 2)
            soft[bit_mask] = 0.0
        decoded = viterbi_decode_k7(soft)
    else:
        decoded = qpsk_hard(rx_symbols.reshape(-1))

    errors = int(np.sum(decoded != info))
    true_collision = collision_mask
    detected = practical_mask
    tp = int(np.sum(detected & true_collision))
    fp = int(np.sum(detected & ~true_collision))
    positives = int(np.sum(true_collision))
    negatives = int(np.sum(~true_collision))
    per_symbol_collision = np.mean(true_collision, axis=1)
    return {
        "bit_errors": errors,
        "total_bits": int(info.size),
        "frame_errors": int(errors > 0),
        "total_frames": 1,
        "collisions": positives,
        "active_symbols": int(true_collision.size),
        "detected_collisions": tp,
        "false_alarms": fp,
        "positive_symbols": positives,
        "negative_symbols": negatives,
        "collision_variance_sum": float(np.var(per_symbol_collision)),
        "max_symbol_collision_sum": float(np.max(per_symbol_collision)),
    }


def wilson_interval(errors: int, total: int, z: float = 1.95996398454) -> Tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    if errors == 0:
        return 0.0, z * z / (total + z * z)
    if errors == total:
        return total / (total + z * z), 1.0
    p = errors / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def aggregate_point(
    scenario: str, scheme: str, snr_db: float, cfg: SimConfig
) -> Dict[str, object]:
    totals = {
        "bit_errors": 0,
        "total_bits": 0,
        "frame_errors": 0,
        "total_frames": 0,
        "collisions": 0,
        "active_symbols": 0,
        "detected_collisions": 0,
        "false_alarms": 0,
        "positive_symbols": 0,
        "negative_symbols": 0,
        "collision_variance_sum": 0.0,
        "max_symbol_collision_sum": 0.0,
    }
    frame_limit = cfg.n_frames_blind if scenario == "blind_pbj" else cfg.n_frames_coded
    for frame in range(frame_limit):
        result = transmit_frame(scenario, scheme, snr_db, cfg, frame)
        for key in totals:
            totals[key] += result[key]

    ber = totals["bit_errors"] / totals["total_bits"]
    low, high = wilson_interval(totals["bit_errors"], totals["total_bits"])
    collision_rate = totals["collisions"] / totals["active_symbols"]
    pd = (
        totals["detected_collisions"] / totals["positive_symbols"]
        if totals["positive_symbols"]
        else 0.0
    )
    pfa = (
        totals["false_alarms"] / totals["negative_symbols"]
        if totals["negative_symbols"]
        else 0.0
    )
    return {
        "scenario": scenario,
        "scheme": scheme,
        "snr_db": snr_db,
        **totals,
        "ber": ber,
        "ber_ci_low": low,
        "ber_ci_high": high,
        "collision_rate": collision_rate,
        "collision_variance": totals["collision_variance_sum"] / totals["total_frames"],
        "max_symbol_collision": totals["max_symbol_collision_sum"] / totals["total_frames"],
        "pd": pd,
        "pfa": pfa,
    }


def run_experiment(cfg: SimConfig, snr_values: Iterable[float]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for scenario, schemes in SCENARIO_SCHEMES.items():
        for scheme in schemes:
            for snr_db in snr_values:
                print(f"{scenario:10s} {scheme:18s} SNR={snr_db:4.1f} dB", flush=True)
                row = aggregate_point(scenario, scheme, snr_db, cfg)
                rows.append(row)
                print(
                    f"  BER={row['ber']:.3e} [{row['ber_ci_low']:.3e}, "
                    f"{row['ber_ci_high']:.3e}], frames={row['total_frames']}, "
                    f"collision={row['collision_rate']:.3f}, "
                    f"Pd={row['pd']:.3f}, Pfa={row['pfa']:.3f}"
                )
    return rows


def save_results(
    rows: List[Dict[str, object]],
    cfg: SimConfig,
    snr_values: List[float],
    result_dir: Path,
) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    with (result_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump({**asdict(cfg), "snr_values": snr_values}, handle, indent=2)
    with (result_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
    with (result_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["smoke", "paper"], default="paper")
    parser.add_argument("--result-dir", type=Path)
    args = parser.parse_args()
    if args.profile == "smoke":
        cfg = SimConfig(n_frames_blind=8, n_frames_coded=8)
        snr_values = [8.0]
        result_dir = args.result_dir or ROOT / "tmp" / "smoke-results"
    else:
        cfg = SimConfig()
        snr_values = [4.0, 8.0, 12.0, 16.0]
        result_dir = args.result_dir or RESULT_DIR
    rows = run_experiment(cfg, snr_values)
    save_results(rows, cfg, snr_values, result_dir)
    print(f"Saved results to {result_dir}")


if __name__ == "__main__":
    main()
