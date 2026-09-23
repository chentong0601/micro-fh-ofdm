#!/usr/bin/env python3
"""Continuation run: extend PASH-cap + causal_adaptive_lag to 100 frame errors.

The base comml-stats run stopped at 5000 frames with 90 errors. This script
continues the same seed/configuration with a higher frame limit.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "redesign"))

from advanced_experiment import (
    AdvancedConfig,
    METHODS,
    bootstrap_ci,
    generate_sequence,
    jammer_sets,
    seeded_rng,
    transmit_frame,
    wilson_interval,
    CausalLagState,
    COMML_RECEIVERS,
)


def run_continuation(max_frames: int = 8000) -> None:
    cfg = AdvancedConfig(snr_db=12.0)
    method = "pash_c15"
    threat = "causal_adaptive_lag"
    receiver = "mixllr"

    print(f"Continuation: {method} + {threat} + {receiver}, max_frames={max_frames}, SNR={cfg.snr_db} dB")

    causal_state = CausalLagState.create(cfg)
    totals = {
        "bit_errors": 0,
        "total_bits": 0,
        "frame_errors": 0,
        "total_frames": 0,
        "collisions": 0,
        "active_symbols": 0,
        "mean_posterior": 0.0,
    }
    frame_errors_list = []
    last_frame = 0

    t0 = time.perf_counter()
    for frame in range(max_frames):
        pattern_rng = seeded_rng(cfg.seed, "advanced-pattern", method, frame)
        jammer_rng = seeded_rng(cfg.seed, "advanced-jammer", method, threat, frame)
        pattern, probs, _ = generate_sequence(method, cfg, pattern_rng)
        jam_sets = jammer_sets(threat, pattern, probs, cfg, jammer_rng, causal_state)

        result = transmit_frame(
            method, threat, receiver, cfg, frame, pattern=pattern, jam_sets=jam_sets
        )
        for key in totals:
            totals[key] += result[key]
        frame_errors_list.append(int(result["frame_errors"]))
        last_frame = frame + 1

        if frame >= 1999 and totals["frame_errors"] >= 100:
            print(f"  Target reached at frame {last_frame}: {totals['frame_errors']} errors")
            break

        if (frame + 1) % 500 == 0:
            bler = totals["frame_errors"] / totals["total_frames"]
            print(f"  frame {frame+1}: fe={totals['frame_errors']}, BLER={bler:.4f}")

    elapsed = time.perf_counter() - t0

    # Compute final statistics
    ber = totals["bit_errors"] / totals["total_bits"]
    bler = totals["frame_errors"] / totals["total_frames"]
    ber_low, ber_high = wilson_interval(int(totals["bit_errors"]), int(totals["total_bits"]))
    bler_low, bler_high = wilson_interval(int(totals["frame_errors"]), int(totals["total_frames"]))
    frame_arr = np.asarray(frame_errors_list, dtype=np.int32)
    _, bler_boot_low, bler_boot_high = bootstrap_ci(frame_arr)
    coll_rate = totals["collisions"] / totals["active_symbols"]
    sufficient = totals["frame_errors"] >= 100

    print(f"\n=== Results (SNR={cfg.snr_db} dB) ===")
    print(f"  Frames:          {last_frame}")
    print(f"  Frame errors:    {totals['frame_errors']}")
    print(f"  BLER:            {bler:.4f}")
    print(f"  BLER boot 95% CI: [{bler_boot_low:.4f}, {bler_boot_high:.4f}]")
    print(f"  BER:             {ber:.4e}")
    print(f"  Collision rate:  {coll_rate:.4f}")
    print(f"  Stats sufficient: {sufficient}")
    print(f"  Elapsed:         {elapsed:.1f}s")
    print(f"  Lag counts:      {causal_state.counts[1:].tolist()}")
    print(f"  Lag estimates:   {[round(v, 6) for v in causal_state.estimates[1:].tolist()]}")


if __name__ == "__main__":
    run_continuation()
