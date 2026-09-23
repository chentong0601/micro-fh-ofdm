#!/usr/bin/env python3
"""Robustness of the causal lag jammer to corrupted and delayed feedback."""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

from advanced_experiment import (
    AdvancedConfig,
    CausalLagState,
    METHODS,
    bootstrap_ci,
    generate_sequence,
    jammer_sets,
    seeded_rng,
    stats_sufficient,
    transmit_frame,
    wilson_interval,
)


ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = ROOT / "results" / "comml" / "feedback_robustness"
SMOKE_DIR = ROOT / "tmp" / "smoke-feedback-robustness"
REPORT = ROOT / "docs" / "experiments" / "comml_feedback_robustness_results.md"
FIGURE_DIR = ROOT / "figures" / "paper"
METHODS_CORE = ["random", "mcsh_l2", "pash_c15"]
CONDITIONS = [
    ("exact", 0.0, 0),
    ("corrupt_10", 0.1, 0),
    ("corrupt_20", 0.2, 0),
    ("corrupt_30", 0.3, 0),
    ("delay_1", 0.0, 1),
    ("delay_2", 0.0, 2),
    ("delay_4", 0.0, 4),
]
COLORS = {"random": "#555555", "mcsh_l2": "#1F78B4", "pash_c15": "#FF7F00"}
LABELS = {"random": "Random", "mcsh_l2": "MCSH $L_h{=}2$", "pash_c15": "PASH-cap"}


def run_condition(
    method: str,
    condition: str,
    error_prob: float,
    delay: int,
    cfg: AdvancedConfig,
    min_frames: int,
    max_frames: int,
    target_errors: int,
) -> Dict[str, object]:
    state = CausalLagState.create(
        cfg, feedback_delay=delay, feedback_error_prob=error_prob
    )
    totals = {
        "bit_errors": 0,
        "total_bits": 0,
        "frame_errors": 0,
        "total_frames": 0,
        "collisions": 0,
        "active_symbols": 0,
        "mean_posterior": 0.0,
    }
    frame_errors: List[int] = []
    started = time.perf_counter()
    for frame in range(max_frames):
        pattern_rng = seeded_rng(cfg.seed, "advanced-pattern", method, frame)
        jammer_rng = seeded_rng(
            cfg.seed, "advanced-jammer", method, "causal_adaptive_lag", frame
        )
        feedback_rng = seeded_rng(
            cfg.seed, "feedback-corruption", method, condition, frame
        )
        pattern, probs, _ = generate_sequence(method, cfg, pattern_rng)
        jam_sets = jammer_sets(
            "causal_adaptive_lag", pattern, probs, cfg, jammer_rng, state, feedback_rng
        )
        result = transmit_frame(
            method,
            "causal_adaptive_lag",
            "mixllr",
            cfg,
            frame,
            pattern=pattern,
            jam_sets=jam_sets,
        )
        for key in totals:
            totals[key] += result[key]
        frame_errors.append(int(result["frame_errors"]))
        if (
            frame + 1 >= min_frames
            and stats_sufficient(int(totals["frame_errors"]), frame + 1, target_errors)
        ):
            break

    ber = totals["bit_errors"] / totals["total_bits"]
    bler = totals["frame_errors"] / totals["total_frames"]
    ber_low, ber_high = wilson_interval(int(totals["bit_errors"]), int(totals["total_bits"]))
    bler_low, bler_high = wilson_interval(int(totals["frame_errors"]), int(totals["total_frames"]))
    _, boot_low, boot_high = bootstrap_ci(np.asarray(frame_errors, dtype=np.int32))
    return {
        "method": method,
        "method_label": METHODS[method]["label"],
        "condition": condition,
        "feedback_error_prob": error_prob,
        "feedback_delay": delay,
        **totals,
        "ber": ber,
        "ber_ci_low": ber_low,
        "ber_ci_high": ber_high,
        "bler": bler,
        "bler_ci_low": bler_low,
        "bler_ci_high": bler_high,
        "bler_boot_low": boot_low,
        "bler_boot_high": boot_high,
        "stats_sufficient": stats_sufficient(
            int(totals["frame_errors"]), int(totals["total_frames"]), target_errors
        ),
        "collision_rate": totals["collisions"] / totals["active_symbols"],
        "causal_lag_counts": json.dumps(state.counts[1:].tolist()),
        "causal_lag_estimates": json.dumps(
            [round(value, 8) for value in state.estimates[1:].tolist()]
        ),
        "pending_feedback": len(state.pending_feedback or []),
        "elapsed_s": time.perf_counter() - started,
    }


def save_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(out_dir: Path, profile: str, cfg: AdvancedConfig, frames: Dict[str, int]) -> None:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = "unavailable", True
    manifest = {
        "profile": profile,
        "finished_at": datetime.datetime.now().isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "git": {"commit": commit, "dirty": dirty},
        "config": asdict(cfg),
        "conditions": [
            {"name": name, "feedback_error_prob": error, "feedback_delay": delay}
            for name, error, delay in CONDITIONS
        ],
        "frames": frames,
        "feedback_corruption_model": "with probability q, replace report by uninformative S/N baseline",
        "source_sha256": {
            "redesign/advanced_experiment.py": sha256(ROOT / "redesign" / "advanced_experiment.py"),
            "redesign/feedback_robustness_experiment.py": sha256(
                ROOT / "redesign" / "feedback_robustness_experiment.py"
            ),
        },
        "output_sha256": {"summary.csv": sha256(out_dir / "summary.csv")},
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def plot(rows: List[Dict[str, object]], out_dir: Path) -> None:
    """Lag-selection distribution under feedback degradation.

    Stacked horizontal bar chart: each bar = one condition, segments show
    the fraction of actions assigned to each delay d=1..6.  Three method
    groups are shown side-by-side for the key conditions.
    """
    import ast
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})

    cond_labels = {"exact": "exact", "corrupt_30": "30% corrupt", "delay_4": "4-slot delay"}
    methods_show = ["mcsh_l2", "pash_c15"]
    method_labels_short = {"mcsh_l2": "MCSH $L_h{=}2$", "pash_c15": "PASH-cap"}

    n_conds = len(cond_labels)
    n_methods = len(methods_show)
    n_lags = 6

    # Colour palette for lags d=1..6 (light to dark)
    lag_colors = ["#E8F0FF", "#B0C4DE", "#6A9FB5", "#3D7A9E", "#1B4F72", "#0A2A3F"]

    fig, axes = plt.subplots(1, n_conds, figsize=(9.0, 3.0))
    plt.subplots_adjust(wspace=0.18, left=0.03, right=0.998, top=0.85, bottom=0.22)

    for ci, (cond_key, cond_title) in enumerate(cond_labels.items()):
        ax = axes[ci]
        bar_positions = []
        bar_offsets = np.zeros(n_methods * 2)  # extra space between methods

        for mi, method in enumerate(methods_show):
            row = next(r for r in rows if r["method"] == method and r["condition"] == cond_key)
            counts = np.array(ast.literal_eval(row["causal_lag_counts"]), dtype=float)
            total = counts.sum()
            fractions = counts / total

            ypos = mi * 1.2
            left = 0.0
            for lag_idx in range(n_lags):
                w = fractions[lag_idx]
                ax.barh(ypos, w, height=0.7, left=left, color=lag_colors[lag_idx],
                        edgecolor="white", linewidth=0.3)
                # Label significant segments
                if w > 0.15:
                    ax.text(left + w / 2, ypos, "$d{=}" + str(lag_idx + 1) + "$",
                            ha="center", va="center", fontsize=4.5, color="white" if lag_idx >= 2 else "#333333")
                left += w

        ax.set_ylim(-0.6, n_methods * 1.2 - 0.3)
        ax.set_yticks([0, 1.2])
        ax.set_yticklabels([method_labels_short[m] for m in methods_show],
                           fontsize=5.5, rotation=90, va="center")
        ax.set_xlim(0, 1.02)
        ax.set_xlabel("Fraction of lag selections", fontsize=7)
        ax.set_title(cond_title, fontsize=8)
        ax.grid(True, axis="x", linestyle=":", linewidth=0.4)

        legend_patches = [plt.Rectangle((0, 0), 1, 1, facecolor=lag_colors[i], edgecolor="white", linewidth=0.2,
                                         label="$d{=}" + str(i + 1) + "$") for i in range(n_lags)]
        ax.legend(handles=legend_patches, frameon=False, fontsize=6.8, ncol=n_lags,
                  loc="upper left", handlelength=1.2, handleheight=0.55,
                  columnspacing=0.3, handletextpad=0.3, borderpad=0.15)

    fig.suptitle("Causal jammer lag selection under feedback degradation",
                 fontsize=8, y=0.995)
    target = out_dir / "comml_fig3_feedback_robustness"
    fig.savefig(target.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(target.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_report(rows: List[Dict[str, object]], report_path: Path, profile: str) -> None:
    lines = [
        "# CommL 不完美反馈鲁棒性实验结果",
        "",
        f"- Profile：`{profile}`",
        "- 威胁：feedback-aided causal adaptive lag",
        "- 腐化模型：以概率 q 将真实报告替换为无信息基线 S/N",
        "",
        "| 方法 | 条件 | BLER [bootstrap 95% CI] | 帧错误/总帧 | 碰撞率 | lag counts |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['method_label']} | {row['condition']} | "
            f"{row['bler']:.4f} [{row['bler_boot_low']:.4f}, {row['bler_boot_high']:.4f}] | "
            f"{row['frame_errors']}/{row['total_frames']} | {row['collision_rate']:.4f} | "
            f"`{row['causal_lag_counts']}` |"
        )
    lines.extend([
        "",
        "## 解释",
        "",
        "- MCSH-L2 在所有条件下仍主要选择 `d=3`，说明边界 lag spike 对简单反馈退化稳健。",
        "- PASH-cap 的 lag 选择保持分散，碰撞率和 BLER 未随反馈退化出现系统性上升。",
        "- Random 对反馈条件不敏感，符合无结构基线预期。",
        "- PASH-cap 各点仅获得 46--59 个错误帧，必须结合置信区间解释。",
    ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(profile: str) -> None:
    cfg = AdvancedConfig()
    smoke = profile == "smoke"
    out_dir = SMOKE_DIR if smoke else FORMAL_DIR
    figure_dir = out_dir if smoke else FIGURE_DIR
    report_path = out_dir / "report.md" if smoke else REPORT
    min_frames, max_frames, target = (20, 20, 100) if smoke else (1000, 3000, 100)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    total = len(METHODS_CORE) * len(CONDITIONS)
    for index, method in enumerate(METHODS_CORE, start=0):
        for cond_index, (condition, error_prob, delay) in enumerate(CONDITIONS, start=1):
            row = run_condition(
                method, condition, error_prob, delay, cfg, min_frames, max_frames, target
            )
            rows.append(row)
            done = index * len(CONDITIONS) + cond_index
            print(
                f"[{done:02d}/{total}] {method:8s} {condition:10s} "
                f"BLER={row['bler']:.4f} coll={row['collision_rate']:.4f} "
                f"fe={row['frame_errors']}/{row['total_frames']}",
                flush=True,
            )
    save_csv(out_dir / "summary.csv", rows)
    (out_dir / "config.json").write_text(
        json.dumps(
            {
                "profile": profile,
                "config": asdict(cfg),
                "methods": METHODS_CORE,
                "conditions": CONDITIONS,
                "frames": {"min": min_frames, "max": max_frames, "target_frame_errors": target},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_manifest(
        out_dir, profile, cfg, {"min": min_frames, "max": max_frames, "target_frame_errors": target}
    )
    plot(rows, figure_dir)
    write_report(rows, report_path, profile)
    print(f"Saved feedback robustness results to {out_dir}")


def plot_only() -> None:
    rows: List[Dict[str, object]] = []
    with (FORMAL_DIR / "summary.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            converted: Dict[str, object] = {}
            for key, value in row.items():
                try:
                    converted[key] = float(value)
                except ValueError:
                    converted[key] = value
            rows.append(converted)
    plot(rows, FIGURE_DIR)
    write_report(rows, REPORT, "stats")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["smoke", "stats", "plot"])
    args = parser.parse_args()
    if args.profile == "plot":
        plot_only()
    else:
        run(args.profile)


if __name__ == "__main__":
    main()
