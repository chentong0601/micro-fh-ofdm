#!/usr/bin/env python3
"""Create paper figures and an automatically traceable experiment report."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "redesign"
FIGURE_DIR = ROOT / "figures" / "paper"
DOC_PATH = ROOT / "docs" / "experiments" / "redesign_results.md"

LABELS = {
    "fixed_uncoded": "Fixed, uncoded",
    "hop_uncoded": "Hopping, uncoded",
    "fixed_k7": "Fixed + K7",
    "hop_k7": "Hopping + K7",
    "hop_k7_practical": "Hopping + K7 + practical erasure",
    "hop_k7_oracle": "Hopping + K7 + oracle erasure",
}

STYLES = {
    "fixed_uncoded": ("o", "#AAAAAA"),
    "hop_uncoded": ("s", "#0072B2"),
    "fixed_k7": ("o", "#AAAAAA"),
    "hop_k7": ("s", "#0072B2"),
    "hop_k7_practical": ("^", "#D55E00"),
    "hop_k7_oracle": ("D", "#009E73"),
}


def load_rows() -> List[Dict[str, object]]:
    with (RESULT_DIR / "summary.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def select(rows: List[Dict[str, object]], scenario: str, scheme: str) -> List[Dict[str, object]]:
    return sorted(
        [r for r in rows if r["scenario"] == scenario and r["scheme"] == scheme],
        key=lambda r: r["snr_db"],
    )


def plot_curves(ax, rows, scenario, schemes, title):
    for scheme in schemes:
        data = select(rows, scenario, scheme)
        x = np.array([r["snr_db"] for r in data])
        y = np.array([r["ber"] for r in data])
        low = np.array([r["ber_ci_low"] for r in data])
        high = np.array([r["ber_ci_high"] for r in data])
        marker, color = STYLES[scheme]
        lw = 2.0 if "fixed" in scheme else 1.8
        ls = "--" if "fixed" in scheme else "-"
        ax.semilogy(x, y, marker=marker, color=color, linewidth=lw, linestyle=ls,
                    markersize=5, label=LABELS[scheme], markeredgewidth=0.5,
                    markeredgecolor="white")
        ax.fill_between(x, np.maximum(low, 1e-7), high, color=color, alpha=0.10)
    ax.set_title(title)
    ax.set_xlabel("$E_s/N_0$ (dB)")
    ax.set_ylabel("BER")
    ax.grid(True, which="both", linestyle=":", linewidth=0.6)
    ax.set_ylim(1e-5, 0.7)


def create_figures(rows: List[Dict[str, object]]) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "legend.fontsize": 7,
        }
    )

    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.0), constrained_layout=True)
    plot_curves(
        axes[0],
        rows,
        "blind_pbj",
        ["fixed_uncoded", "hop_uncoded"],
        "(a) Blind PBJ: fairness check",
    )
    plot_curves(
        axes[1],
        rows,
        "sweep",
        ["fixed_k7", "hop_k7", "hop_k7_practical", "hop_k7_oracle"],
        "(b) Sweep jammer: matched coding",
    )
    plot_curves(
        axes[2],
        rows,
        "reactive",
        ["fixed_k7", "hop_k7", "hop_k7_practical", "hop_k7_oracle"],
        "(c) One-symbol-delayed reactive jammer",
    )
    for ax in axes:
        ax.legend(frameon=False)
    fig.savefig(FIGURE_DIR / "fig1_ber_common_grid.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "fig1_ber_common_grid.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.7), constrained_layout=True)
    scenarios = ["blind_pbj", "sweep", "reactive"]
    fixed_schemes = ["fixed_uncoded", "fixed_k7", "fixed_k7"]
    hop_schemes = ["hop_uncoded", "hop_k7", "hop_k7"]
    x = np.arange(len(scenarios))
    fixed_collision = [
        np.mean([r["collision_rate"] for r in select(rows, s, m)])
        for s, m in zip(scenarios, fixed_schemes)
    ]
    hop_collision = [
        np.mean([r["collision_rate"] for r in select(rows, s, m)])
        for s, m in zip(scenarios, hop_schemes)
    ]
    axes[0].bar(x - 0.18, fixed_collision, width=0.36, color="#555555", label="Fixed")
    axes[0].bar(x + 0.18, hop_collision, width=0.36, color="#0072B2", label="Hopping")
    axes[0].set_xticks(x, ["Blind PBJ", "Sweep", "Reactive"])
    axes[0].set_ylabel("Mean active-bin collision rate")
    axes[0].set_ylim(0, 1.05)
    axes[0].grid(True, axis="y", linestyle=":", linewidth=0.6)
    axes[0].legend(frameon=False)
    axes[0].set_title("(a) Collision mechanism")

    for scenario, marker, color in [
        ("sweep", "o", "#D55E00"),
        ("reactive", "s", "#0072B2"),
    ]:
        data = select(rows, scenario, "hop_k7_practical")
        axes[1].plot(
            [r["snr_db"] for r in data],
            [r["pd"] for r in data],
            marker=marker,
            color=color,
            label=f"{scenario}: $P_d$",
        )
        axes[1].plot(
            [r["snr_db"] for r in data],
            [r["pfa"] for r in data],
            marker=marker,
            color=color,
            linestyle="--",
            label=f"{scenario}: $P_{{fa}}$",
        )
    axes[1].set_xlabel("$E_s/N_0$ (dB)")
    axes[1].set_ylabel("Probability")
    axes[1].set_ylim(0, 1.05)
    axes[1].grid(True, linestyle=":", linewidth=0.6)
    axes[1].legend(frameon=False, ncol=2, fontsize=6)
    axes[1].set_title("(b) Practical detector: $P_d$ (solid), $P_{fa}$ (dashed)")
    axes[1].annotate("$P_d$ near-identical across\njammer types", xy=(12, 0.48), fontsize=6,
                     color="#555555", ha="center")
    fig.savefig(FIGURE_DIR / "fig2_collision_detector.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "fig2_collision_detector.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def nearest(rows, scenario, scheme, snr=12.0):
    return min(select(rows, scenario, scheme), key=lambda r: abs(r["snr_db"] - snr))


def write_report(rows: List[Dict[str, object]]) -> None:
    blind_fixed = nearest(rows, "blind_pbj", "fixed_uncoded")
    blind_hop = nearest(rows, "blind_pbj", "hop_uncoded")
    sweep_fixed = nearest(rows, "sweep", "fixed_k7")
    sweep_hop = nearest(rows, "sweep", "hop_k7")
    sweep_practical = nearest(rows, "sweep", "hop_k7_practical")
    sweep_oracle = nearest(rows, "sweep", "hop_k7_oracle")
    reactive_fixed = nearest(rows, "reactive", "fixed_k7")
    reactive_hop = nearest(rows, "reactive", "hop_k7")
    reactive_practical = nearest(rows, "reactive", "hop_k7_practical")
    reactive_oracle = nearest(rows, "reactive", "hop_k7_oracle")

    def ratio(a, b):
        return a["ber"] / max(b["ber"], 1e-15)

    text = f"""# 重设计实验结果

本报告由 `redesign/plot_results.py` 从 `results/redesign/summary.json` 自动生成。
所有主比较均使用共同 512 子载波物理栅格、64 个激活子载波、相同平均功率与
匹配的 K=7 编码口径。下列截面取 $E_s/N_0=12$ dB。

## 关键结果

| 场景/方案 | BER | 95% CI | 碰撞率 | 帧内碰撞方差 | Pd | Pfa |
|---|---:|---:|---:|---:|---:|---:|
| Blind PBJ, fixed uncoded | {blind_fixed['ber']:.3e} | [{blind_fixed['ber_ci_low']:.3e}, {blind_fixed['ber_ci_high']:.3e}] | {blind_fixed['collision_rate']:.3f} | {blind_fixed['collision_variance']:.3f} | - | - |
| Blind PBJ, hopping uncoded | {blind_hop['ber']:.3e} | [{blind_hop['ber_ci_low']:.3e}, {blind_hop['ber_ci_high']:.3e}] | {blind_hop['collision_rate']:.3f} | {blind_hop['collision_variance']:.3f} | - | - |
| Sweep, fixed + K7 | {sweep_fixed['ber']:.3e} | [{sweep_fixed['ber_ci_low']:.3e}, {sweep_fixed['ber_ci_high']:.3e}] | {sweep_fixed['collision_rate']:.3f} | {sweep_fixed['collision_variance']:.3f} | - | - |
| Sweep, hopping + K7 | {sweep_hop['ber']:.3e} | [{sweep_hop['ber_ci_low']:.3e}, {sweep_hop['ber_ci_high']:.3e}] | {sweep_hop['collision_rate']:.3f} | {sweep_hop['collision_variance']:.3f} | - | - |
| Sweep, hopping + practical erasure | {sweep_practical['ber']:.3e} | [{sweep_practical['ber_ci_low']:.3e}, {sweep_practical['ber_ci_high']:.3e}] | {sweep_practical['collision_rate']:.3f} | {sweep_practical['collision_variance']:.3f} | {sweep_practical['pd']:.3f} | {sweep_practical['pfa']:.3f} |
| Sweep, hopping + oracle erasure | {sweep_oracle['ber']:.3e} | [{sweep_oracle['ber_ci_low']:.3e}, {sweep_oracle['ber_ci_high']:.3e}] | {sweep_oracle['collision_rate']:.3f} | {sweep_oracle['collision_variance']:.3f} | - | - |
| Reactive, fixed + K7 | {reactive_fixed['ber']:.3e} | [{reactive_fixed['ber_ci_low']:.3e}, {reactive_fixed['ber_ci_high']:.3e}] | {reactive_fixed['collision_rate']:.3f} | {reactive_fixed['collision_variance']:.3f} | - | - |
| Reactive, hopping + K7 | {reactive_hop['ber']:.3e} | [{reactive_hop['ber_ci_low']:.3e}, {reactive_hop['ber_ci_high']:.3e}] | {reactive_hop['collision_rate']:.3f} | {reactive_hop['collision_variance']:.3f} | - | - |
| Reactive, hopping + practical erasure | {reactive_practical['ber']:.3e} | [{reactive_practical['ber_ci_low']:.3e}, {reactive_practical['ber_ci_high']:.3e}] | {reactive_practical['collision_rate']:.3f} | {reactive_practical['collision_variance']:.3f} | {reactive_practical['pd']:.3f} | {reactive_practical['pfa']:.3f} |
| Reactive, hopping + oracle erasure | {reactive_oracle['ber']:.3e} | [{reactive_oracle['ber_ci_low']:.3e}, {reactive_oracle['ber_ci_high']:.3e}] | {reactive_oracle['collision_rate']:.3f} | {reactive_oracle['collision_variance']:.3f} | - | - |

## 解释

1. 盲 PBJ 下固定与跳变方案的未编码 BER 比值为
   `{ratio(blind_fixed, blind_hop):.2f}x`。两者的小幅差异与实测碰撞率
   `{blind_fixed['collision_rate']:.3f}` 和 `{blind_hop['collision_rate']:.3f}`
   的差异同向，未显示出跳变带来的系统性平均未编码增益。
2. 扫频干扰下，匹配编码后跳变相对固定方案的 BER 比值为
   `{ratio(sweep_fixed, sweep_hop):.2f}x`。固定方案帧内碰撞方差为
   `{sweep_fixed['collision_variance']:.3f}`，跳变方案为
   `{sweep_hop['collision_variance']:.3f}`；收益来自碰撞去突发化，而非额外功率。
3. 反应式干扰下，固定方案平均碰撞率为 `{reactive_fixed['collision_rate']:.3f}`，
   跳变方案为 `{reactive_hop['collision_rate']:.3f}`；匹配编码 BER 比值为
   `{ratio(reactive_fixed, reactive_hop):.2f}x`。
4. practical 与 oracle 的差距量化了检测器仍可改进的空间。只有当 practical
   擦除相对无擦除产生净收益时，才应在论文中把它作为贡献。

## 迭代结论

- 旧稿中的“固定 9.03 dB 处理增益”和“152 倍总增益”不进入新稿。
- 新稿以盲 PBJ 公平性负结果、扫频碰撞去突发化和延迟反应式干扰规避为主线。
- 混沌序列仅作为可选图案发生器讨论，不宣称密码学安全性。
"""
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    rows = load_rows()
    create_figures(rows)
    write_report(rows)
    print(f"Saved figures to {FIGURE_DIR}")
    print(f"Saved report to {DOC_PATH}")


if __name__ == "__main__":
    main()
