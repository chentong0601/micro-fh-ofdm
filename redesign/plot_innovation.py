#!/usr/bin/env python3
"""Generate figures and a traceable report for the phase-2 method."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "innovation"
FIGURE_DIR = ROOT / "figures" / "paper"
REPORT = ROOT / "docs" / "experiments" / "phase2_results.md"

LABELS = {
    "random_k7": "Random + K7",
    "random_brw": "Random + BRW",
    "mc1_k7": "MCSH $L_h=1$",
    "mc2_k7": "MCSH $L_h=2$",
    "mc4_k7": "MCSH $L_h=4$",
    "mc6_k7": "MCSH $L_h=6$",
    "mc2_hard": "MCSH + hard erasure",
    "mc2_brw": "MCSH + BRW",
    "mc2_oracle": "MCSH + oracle",
}

STYLES = {
    "random_k7": ("o", "#222222", "--"),
    "random_brw": ("s", "#666666", ":"),
    "mc1_k7": ("v", "#CC79A7", "-"),
    "mc2_k7": ("s", "#0072B2", "-"),
    "mc4_k7": ("^", "#D55E00", "--"),
    "mc6_k7": ("P", "#56B4E9", "-."),
    "mc2_hard": ("^", "#E69F00", "--"),
    "mc2_brw": ("D", "#009E73", "-"),
    "mc2_oracle": ("X", "#CC3311", ":"),
}


def load_rows() -> List[Dict[str, object]]:
    with (RESULT_DIR / "summary.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def select(
    rows: List[Dict[str, object]],
    experiment: str,
    scenario: str | None = None,
    scheme: str | None = None,
) -> List[Dict[str, object]]:
    data = [
        row
        for row in rows
        if row["experiment"] == experiment
        and (scenario is None or row["scenario"] == scenario)
        and (scheme is None or row["scheme"] == scheme)
    ]
    return sorted(data, key=lambda row: float(row["x_value"]))


def nearest(
    rows: List[Dict[str, object]],
    experiment: str,
    scenario: str,
    scheme: str,
    x: float,
) -> Dict[str, object]:
    return min(
        select(rows, experiment, scenario, scheme),
        key=lambda row: abs(float(row["x_value"]) - x),
    )


def setup() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "legend.fontsize": 7,
            "lines.linewidth": 1.4,
        }
    )


def concept_figure():
    rng = np.random.default_rng(20260607)
    n, s, m_count, memory = 32, 4, 8, 2
    random_sets = np.vstack([rng.choice(n, s, replace=False) for _ in range(m_count)])
    memory_sets = np.empty((m_count, s), dtype=int)
    for m in range(m_count):
        recent = memory_sets[max(0, m - memory) : m].reshape(-1) if m else np.array([], int)
        counts = np.bincount(recent, minlength=n)
        memory_sets[m] = np.lexsort((rng.random(n), counts))[:s]

    fig = plt.figure(figsize=(7.1, 3.0), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, width_ratios=[1, 1, 1.15])
    for row, (sets, title) in enumerate(
        [(random_sets, "Random set hopping"), (memory_sets, "MCSH, $L_h=2$")]
    ):
        ax = fig.add_subplot(grid[row, :2])
        image = np.zeros((m_count, n))
        for m in range(m_count):
            image[m, sets[m]] = 1
            if m:
                image[m, np.intersect1d(sets[m], sets[m - 1])] = 2
        ax.imshow(image, aspect="auto", interpolation="nearest", cmap=plt.get_cmap("viridis", 3), vmin=0, vmax=2)
        ax.set_title(title)
        ax.set_ylabel("Symbol $m$")
        ax.set_yticks([0, 3, 7], [1, 4, 8])
        if row:
            ax.set_xlabel("Physical subcarrier")
        else:
            ax.set_xticklabels([])
    ax = fig.add_subplot(grid[:, 2])
    ax.axis("off")
    ax.text(0.5, 0.93, "BRW receiver", ha="center", va="center", fontsize=10, weight="bold")
    boxes = [
        (0.5, 0.76, "Equalize active bins"),
        (0.5, 0.55, "Clean/jammed\nmixture likelihoods"),
        (0.5, 0.34, "Posterior collision\nprobability $q_{k,m}$"),
        (0.5, 0.13, "Reliability-weighted\nViterbi metric"),
    ]
    for x, y, text in boxes:
        ax.text(
            x,
            y,
            text,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "#E8F3F8", "edgecolor": "#0072B2"},
        )
    for y0, y1 in [(0.69, 0.62), (0.48, 0.41), (0.27, 0.20)]:
        ax.annotate("", xy=(0.5, y1), xytext=(0.5, y0), arrowprops={"arrowstyle": "->", "color": "#444444"})
    fig.savefig(FIGURE_DIR / "fig2_method_concept.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "fig2_method_concept.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_ber(ax, rows, experiment, scenario, schemes, title, xlabel):
    for scheme in schemes:
        data = select(rows, experiment, scenario, scheme)
        x = np.array([float(row["x_value"]) for row in data])
        y = np.maximum([float(row["ber"]) for row in data], 1e-6)
        low = np.maximum([float(row["ber_ci_low"]) for row in data], 1e-6)
        high = np.maximum([float(row["ber_ci_high"]) for row in data], 1e-6)
        marker, color, linestyle = STYLES[scheme]
        ax.semilogy(x, y, marker=marker, color=color, linestyle=linestyle, label=LABELS[scheme])
        ax.fill_between(x, low, high, color=color, alpha=0.08)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 0.8)
    ax.grid(True, which="both", linestyle=":", linewidth=0.55)


def core_figure(rows):
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 5.0), constrained_layout=True)
    schemes = ["random_k7", "random_brw", "mc2_k7", "mc2_brw", "mc2_oracle"]
    for ax, scenario, title in zip(
        axes.flat,
        ["sweep", "reactive_d1", "reactive_d2", "reactive_union2"],
        [
            "(a) Sweep jammer",
            "(b) One-slot follower",
            "(c) Two-slot follower",
            "(d) Union-of-two follower",
        ],
    ):
        plot_ber(ax, rows, "core_ber", scenario, schemes, title, "$E_s/N_0$ (dB)")
    axes[0, 0].legend(frameon=False, ncol=2)
    fig.savefig(FIGURE_DIR / "fig3_core_method.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "fig3_core_method.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def delay_load_figure(rows):
    fig, axes = plt.subplots(1, 3, figsize=(10.3, 3.0), constrained_layout=True)
    schemes = ["random_k7", "mc1_k7", "mc2_k7", "mc4_k7", "mc6_k7"]
    # Staggered marker sizes to reveal overlapping points
    msizes = {"random_k7": 4, "mc1_k7": 5, "mc2_k7": 5, "mc4_k7": 5, "mc6_k7": 6}
    for scheme in schemes:
        data = select(rows, "delay_ablation", scheme=scheme)
        x = [float(row["x_value"]) for row in data]
        marker, color, linestyle = STYLES[scheme]
        ms = msizes.get(scheme, 4)
        axes[0].plot(x, [row["collision_rate"] for row in data],
                     marker=marker, color=color, linestyle=linestyle,
                     markersize=ms, linewidth=1.5, label=LABELS[scheme],
                     markeredgewidth=0.3, markeredgecolor="white")
        axes[1].semilogy(x, np.maximum([row["ber"] for row in data], 1e-6),
                         marker=marker, color=color, linestyle=linestyle,
                         markersize=ms, linewidth=1.5, label=LABELS[scheme],
                         markeredgewidth=0.3, markeredgecolor="white")
    # Vertical reference lines at MCSH memory boundaries
    for lh, ls in [(1, "--"), (2, "-."), (4, ":")]:
        axes[0].axvline(lh + 0.5, color="#888888", linestyle=ls, linewidth=0.7, alpha=0.5)
        axes[1].axvline(lh + 0.5, color="#888888", linestyle=ls, linewidth=0.7, alpha=0.5)
    axes[0].set_title("(a) Collision vs. follower delay  (dashed lines = $L_h$ boundaries)", fontsize=8)
    axes[0].set_xlabel("Actual follower delay $d$")
    axes[0].set_ylabel("Frame-average collision rate")
    axes[1].set_title("(b) BER vs. follower delay", fontsize=8)
    axes[1].set_xlabel("Actual follower delay $d$")
    axes[1].set_ylabel("BER")
    axes[1].set_ylim(1e-4, 5e-2)
    for scheme in ["random_k7", "mc2_k7"]:
        data = select(rows, "load_boundary", "reactive_union2", scheme)
        marker, color, linestyle = STYLES[scheme]
        axes[2].plot(
            [row["n_active"] / row["n_phys"] for row in data],
            [row["collision_rate"] for row in data],
            marker=marker, color=color, linestyle=linestyle,
            markersize=6, linewidth=1.8, label=LABELS[scheme],
            markeredgewidth=0.3, markeredgecolor="white",
        )
    axes[2].axvline(1 / 3, color="#CC3311", linestyle=":", linewidth=1.2, label="$(L_h{+}1)S{=}N$")
    axes[2].set_title("(c) Feasibility boundary, $L_h=2$", fontsize=8)
    axes[2].set_xlabel("Active load $S/N$")
    axes[2].set_ylabel("Union-follower collision rate")
    for ax in axes:
        ax.grid(True, which="both", linestyle=":", linewidth=0.55)
    axes[0].legend(frameon=False, ncol=2, fontsize=6.5)
    axes[2].legend(frameon=False, fontsize=7)
    fig.savefig(FIGURE_DIR / "fig4_delay_load.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "fig4_delay_load.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def robustness_figure(rows):
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 5.0), constrained_layout=True)
    for scheme in ["random_k7", "random_brw", "mc2_k7", "mc2_brw"]:
        data = select(rows, "jsr_robustness", "reactive_d1", scheme)
        marker, color, linestyle = STYLES[scheme]
        axes[0, 0].semilogy(
            [row["x_value"] for row in data],
            np.maximum([row["ber"] for row in data], 1e-6),
            marker=marker,
            color=color,
            linestyle=linestyle,
            label=LABELS[scheme],
        )
    axes[0, 0].set_title("(a) One-slot follower vs. JSR")
    axes[0, 0].set_xlabel("JSR (dB)")
    axes[0, 0].set_ylabel("BER")
    channels = ["AWGN", "Ped-A", "Veh-A"]
    x = np.arange(3)
    width = 0.19
    for idx, scheme in enumerate(["random_k7", "random_brw", "mc2_k7", "mc2_brw"]):
        data = select(rows, "channel_robustness", "reactive_d1", scheme)
        axes[0, 1].bar(
            x + (idx - 1.5) * width,
            np.maximum([row["ber"] for row in data], 1e-6),
            width=width,
            color=STYLES[scheme][1],
            label=LABELS[scheme],
        )
    axes[0, 1].set_yscale("log")
    axes[0, 1].set_xticks(x, channels)
    axes[0, 1].set_title("(b) Frequency-selective fading")
    axes[0, 1].set_ylabel("BER")
    for scheme in ["mc2_k7", "mc2_brw"]:
        data = select(rows, "csi_robustness", "reactive_d1", scheme)
        xvals = [-40 if row["x_value"] < -100 else row["x_value"] for row in data]
        marker, color, linestyle = STYLES[scheme]
        axes[1, 0].semilogy(xvals, np.maximum([row["ber"] for row in data], 1e-6), marker=marker, color=color, linestyle=linestyle, label=LABELS[scheme])
    axes[1, 0].set_xticks([-40, -30, -20, -10], ["Perfect", "-30", "-20", "-10"])
    axes[1, 0].set_title("(c) Veh-A CSI error")
    axes[1, 0].set_xlabel("CSI NMSE (dB)")
    axes[1, 0].set_ylabel("BER")
    for scheme in ["mc2_k7", "mc2_brw"]:
        data = select(rows, "sync_robustness", "reactive_d1", scheme)
        marker, color, linestyle = STYLES[scheme]
        axes[1, 1].semilogy(
            100 * np.asarray([row["x_value"] for row in data]),
            np.maximum([row["ber"] for row in data], 1e-6),
            marker=marker,
            color=color,
            linestyle=linestyle,
            label=LABELS[scheme],
        )
    axes[1, 1].set_title("(d) Hopping-pattern desynchronization")
    axes[1, 1].set_xlabel("Erroneous symbol patterns (%)")
    axes[1, 1].set_ylabel("BER")
    for ax in axes.flat:
        ax.grid(True, which="both", linestyle=":", linewidth=0.55)
    axes[0, 0].legend(frameon=False, ncol=2)
    axes[0, 1].legend(frameon=False, ncol=2)
    axes[1, 0].legend(frameon=False)
    axes[1, 1].legend(frameon=False)
    fig.savefig(FIGURE_DIR / "fig5_robustness.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "fig5_robustness.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def receiver_limits_figure(rows):
    fig, axes = plt.subplots(1, 3, figsize=(10.3, 3.0), constrained_layout=True)
    for scheme in ["mc2_k7", "mc2_hard", "mc2_brw", "mc2_oracle"]:
        data = select(rows, "core_ber", "sweep", scheme)
        marker, color, linestyle = STYLES[scheme]
        axes[0].semilogy([row["x_value"] for row in data], np.maximum([row["ber"] for row in data], 1e-6), marker=marker, color=color, linestyle=linestyle, label=LABELS[scheme])
    axes[0].set_title("(a) Receiver ablation under sweep")
    axes[0].set_xlabel("$E_s/N_0$ (dB)")
    axes[0].set_ylabel("BER")
    mismatch = select(rows, "brw_mismatch", "sweep", "mc2_brw")
    axes[1].semilogy(
        [row["x_value"] for row in mismatch],
        np.maximum([row["ber"] for row in mismatch], 1e-6),
        marker="D",
        color=STYLES["mc2_brw"][1],
    )
    axes[1].set_title("(b) BRW jammer-variance mismatch")
    axes[1].set_xlabel("Estimated-minus-true JSR (dB)")
    axes[1].set_ylabel("BER")
    zero = select(rows, "zero_delay_limit", "reactive_d0")
    axes[2].bar(
        np.arange(len(zero)),
        [row["ber"] for row in zero],
        color=[STYLES[row["scheme"]][1] for row in zero],
    )
    axes[2].set_xticks(np.arange(len(zero)), [LABELS[row["scheme"]].replace(" + ", "\n+") for row in zero])
    axes[2].set_title("(c) Zero-delay reactive limit")
    axes[2].set_ylabel("BER")
    axes[2].set_ylim(0, 0.55)
    for ax in axes:
        ax.grid(True, which="both", linestyle=":", linewidth=0.55)
    axes[0].legend(frameon=False)
    fig.savefig(FIGURE_DIR / "fig6_receiver_limits.pdf", bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "fig6_receiver_limits.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_report(rows):
    r = lambda e, s, m, x: nearest(rows, e, s, m, x)
    d1_random = r("core_ber", "reactive_d1", "random_k7", 12)
    d1_mc = r("core_ber", "reactive_d1", "mc2_k7", 12)
    d1_brw = r("core_ber", "reactive_d1", "mc2_brw", 12)
    sweep_mc = r("core_ber", "sweep", "mc2_k7", 12)
    sweep_hard = r("core_ber", "sweep", "mc2_hard", 12)
    sweep_brw = r("core_ber", "sweep", "mc2_brw", 12)
    veha = select(rows, "channel_robustness", "reactive_d1", "mc2_brw")[-1]
    sync = r("sync_robustness", "reactive_d1", "mc2_brw", 0.05)
    zero = select(rows, "zero_delay_limit", "reactive_d0", "mc2_brw")[0]
    text = f"""# 第二阶段创新实验结果

本报告由 `redesign/plot_innovation.py` 从 `results/innovation/summary.json`
自动生成。正式实验包含 {len(rows)} 个参数点。

## 主要结果

- 一拍跟随干扰、12 dB、5 dB JSR：随机跳变碰撞率为
  `{d1_random['collision_rate']:.3f}`，MCSH `L_h=2` 为
  `{d1_mc['collision_rate']:.3f}`。对应 BER 从 `{d1_random['ber']:.3e}`
  降至 `{d1_mc['ber']:.3e}`；加入 BRW 后为 `{d1_brw['ber']:.3e}`，
  零误码点应解释为其 95% 置信上界 `{d1_brw['ber_ci_high']:.3e}`。
- 扫频场景中 MCSH 本身不降低平均碰撞率；12 dB 时无加权、hard erasure
  与 BRW 的 BER 分别为 `{sweep_mc['ber']:.3e}`、
  `{sweep_hard['ber']:.3e}` 和 `{sweep_brw['ber']:.3e}`。这把接收机创新
  与跳变图案创新分开验证。
- Veh-A + 一拍跟随下，MCSH+BRW BER 为 `{veha['ber']:.3e}`。
- 5% 图案失步时，MCSH+BRW BER 恶化至 `{sync['ber']:.3e}`，说明同步是
  部署瓶颈。
- 零延迟反应式干扰下，MCSH+BRW BER 为 `{zero['ber']:.3f}`，方法不能规避
  无感知延迟的全命中攻击。

## 可支持的创新结论

1. MCSH 在 `(L_h+1)S<=N` 时可消除设计记忆内的稳态跟随碰撞。
2. BRW 比二值 hard erasure 更稳定，且对 JSR 估计失配具有一定容忍度。
3. 两个模块贡献可分离：MCSH 主要改变延迟跟随碰撞，BRW 主要改善残余碰撞
   和扫频干扰的译码。

## 必须保留的边界

- 当实际跟随延迟超过设计记忆时，MCSH 可能不优于随机跳变。
- 当 `(L_h+1)S>N` 时，零碰撞构造不再可行。
- 零延迟反应式干扰、图案失步和严重 CSI 误差均会显著削弱收益。
- BRW 使用噪声和干扰方差估计，不能描述为完全无先验接收机。
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")


def main() -> None:
    setup()
    rows = load_rows()
    concept_figure()
    core_figure(rows)
    delay_load_figure(rows)
    robustness_figure(rows)
    receiver_limits_figure(rows)
    write_report(rows)
    print(f"Saved figures to {FIGURE_DIR}")
    print(f"Saved report to {REPORT}")


if __name__ == "__main__":
    main()
