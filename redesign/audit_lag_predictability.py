#!/usr/bin/env python3
"""Audit delayed-collision spikes and history-conditioned predictability."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from innovation_sim import ExtendedConfig, memory_pattern, random_pattern


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "lag_predictability_audit"
FIGURE_DIR = ROOT / "figures" / "diagnostics"
REPORT = ROOT / "docs" / "experiments" / "lag_predictability_diagnostic.md"


def lag_collision(pattern: np.ndarray, lag: int, active: int) -> float:
    return float(
        np.mean(
            [
                len(np.intersect1d(pattern[m], pattern[m - lag])) / active
                for m in range(lag, pattern.shape[0])
            ]
        )
    )


def main() -> None:
    cfg = replace(ExtendedConfig(), n_sym=4000)
    memories = [0, 1, 2, 4, 6]
    max_lag = 12
    seeds = range(20)
    rows = []

    for memory in memories:
        lag_runs = []
        usage_cvs = []
        for seed in seeds:
            rng = np.random.default_rng(seed)
            pattern = (
                random_pattern(cfg, rng)
                if memory == 0
                else memory_pattern(cfg, rng, memory)
            )
            lag_runs.append(
                [lag_collision(pattern, lag, cfg.n_active) for lag in range(1, max_lag + 1)]
            )
            counts = np.bincount(pattern.reshape(-1), minlength=cfg.n_phys)
            usage_cvs.append(float(counts.std() / counts.mean()))

        values = np.asarray(lag_runs)
        for lag in range(1, max_lag + 1):
            rows.append(
                {
                    "scheme": "random" if memory == 0 else f"mcsh_l{memory}",
                    "memory": memory,
                    "lag": lag,
                    "collision_mean": float(values[:, lag - 1].mean()),
                    "collision_std_across_seeds": float(values[:, lag - 1].std(ddof=1)),
                    "usage_cv_mean": float(np.mean(usage_cvs)),
                }
            )

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    with (RESULT_DIR / "lag_spectrum.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    by_memory = {}
    for memory in memories:
        subset = [row for row in rows if row["memory"] == memory]
        peak = max(subset, key=lambda row: row["collision_mean"])
        candidate = (
            cfg.n_active / cfg.n_phys
            if memory == 0
            else cfg.n_active / (cfg.n_phys - memory * cfg.n_active)
        )
        by_memory[memory] = {
            "peak_lag": peak["lag"],
            "peak_collision": peak["collision_mean"],
            "candidate_collision": candidate,
            "usage_cv": peak["usage_cv_mean"],
        }

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.8), constrained_layout=True)
    for memory in memories:
        subset = [row for row in rows if row["memory"] == memory]
        label = "Random" if memory == 0 else f"MCSH $L_h={memory}$"
        axes[0].plot(
            [row["lag"] for row in subset],
            [row["collision_mean"] for row in subset],
            marker="o",
            label=label,
        )
    axes[0].axhline(cfg.n_active / cfg.n_phys, color="black", linestyle=":", label="$S/N$")
    axes[0].set_xlabel("Follower delay $d$")
    axes[0].set_ylabel("Long-run collision rate")
    axes[0].set_title("(a) Delay-collision spectrum")
    axes[0].grid(True, linestyle=":", linewidth=0.55)
    axes[0].legend(frameon=False, ncol=2, fontsize=7)

    labels = ["Random", "$L_h=1$", "$L_h=2$", "$L_h=4$", "$L_h=6$"]
    x = np.arange(len(memories))
    axes[1].bar(
        x - 0.18,
        [by_memory[m]["peak_collision"] for m in memories],
        width=0.36,
        label="Worst observed delay",
    )
    axes[1].bar(
        x + 0.18,
        [by_memory[m]["candidate_collision"] for m in memories],
        width=0.36,
        label="Candidate-aware jammer",
    )
    axes[1].axhline(cfg.n_active / cfg.n_phys, color="black", linestyle=":", label="$S/N$")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Expected collision rate")
    axes[1].set_title("(b) Structural exposure")
    axes[1].grid(True, axis="y", linestyle=":", linewidth=0.55)
    axes[1].legend(frameon=False, fontsize=7)
    fig.savefig(FIGURE_DIR / "lag_predictability_diagnostic.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "lag_predictability_diagnostic.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    lines = [
        "# MCSH 时延碰撞谱与候选池暴露诊断",
        "",
        "该诊断使用 20 个独立种子、每个种子 4000 个连续符号。随机跳频基准",
        f"`S/N={cfg.n_active/cfg.n_phys:.3f}`。",
        "",
        "| 方法 | 最大时延碰撞 | 尖峰时延 | 候选池感知攻击期望碰撞 | 使用频率 CV |",
        "|---|---:|---:|---:|---:|",
    ]
    for memory in memories:
        name = "Random" if memory == 0 else f"MCSH L_h={memory}"
        value = by_memory[memory]
        lines.append(
            f"| {name} | {value['peak_collision']:.3f} | {value['peak_lag']} | "
            f"{value['candidate_collision']:.3f} | {value['usage_cv']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- MCSH 将前 `L_h` 个时延的碰撞压到零，但在 `L_h+1` 附近形成明显尖峰。",
            "- 记忆越长，候选池越小，history-aware jammer 的可利用概率质量越集中。",
            "- 当前 MCSH 适合已知固定延迟，但不适合直接宣称对未知智能 follower 稳健。",
            "- 新方法应联合优化短时延碰撞与条件可预测性，而不是仅做 hard exclusion。",
            "",
            "数据：`results/lag_predictability_audit/lag_spectrum.csv`。",
            "图：`figures/diagnostics/lag_predictability_diagnostic.pdf`。",
        ]
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved audit results to {RESULT_DIR}")
    print(f"Saved audit figure to {FIGURE_DIR}")
    print(f"Saved report to {REPORT}")


if __name__ == "__main__":
    main()
