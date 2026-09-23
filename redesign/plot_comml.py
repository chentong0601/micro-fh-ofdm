#!/usr/bin/env python3
"""CommL submission figures — independent of advanced_experiment.py.

Reads from focused Communications Letters stats and generates two submission figures:
  Fig. 1 — Structural exposure: (a) lag spectrum, (b) risk tradeoff
  Fig. 2 — Compact coded BLER and causal-jammer feedback robustness
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Sequence

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42})

ROOT = Path(__file__).resolve().parents[1]
STATS_DIR = ROOT / "results" / "comml" / "stats"
FEEDBACK_DIR = ROOT / "results" / "comml" / "feedback_robustness"
FIGURE_DIR = ROOT / "figures" / "paper"


@dataclass(frozen=True)
class FigureStyle:
    """Rendering options.

    Defaults reproduce the figures exactly as submitted (DejaVu Sans, PDF+PNG
    into ``figures/paper/``). The camera-ready profile switches to Arial and
    adds EPS, as required by the IEEE production checklist.
    """

    font_family: str = "DejaVu Sans"
    formats: Sequence[str] = field(default_factory=lambda: ("pdf", "png"))
    dpi: int = 300
    math_fontset: str = "dejavusans"

    @property
    def primary(self) -> str:
        """Vector format used for the paper include."""
        return "pdf" if "pdf" in self.formats else self.formats[0]


DEFAULT_STYLE = FigureStyle()

# IEEE production accepts Symbol / Helvetica / Arial / Times New Roman.
# Arial is chosen over Helvetica on macOS because the system Helvetica is a
# TrueType *collection* (.ttc) that fontTools cannot subset cleanly, which
# both emits warnings and leaks Type 3 glyphs into the EPS. Arial ships as
# plain .ttf files and is metrically near-identical to Helvetica.
CAMERA_READY_FONT = "Arial"

CAMERA_READY_STYLE = FigureStyle(
    font_family=CAMERA_READY_FONT,
    formats=("pdf", "eps"),
    math_fontset="custom",
)


def apply_style(style: FigureStyle) -> None:
    """Push a FigureStyle into matplotlib's rcParams.

    ``mathtext.fontset`` matters as much as ``font.family`` here: every
    ``$...$`` label is rendered by mathtext, which defaults to its own
    bundled DejaVu set and would otherwise ignore the text font entirely.
    """
    plt.rcParams.update(
        {"font.family": style.font_family, "font.size": 8,
         "mathtext.fontset": style.math_fontset}
    )
    if style.math_fontset == "custom":
        plt.rcParams.update(
            {
                "mathtext.rm": style.font_family,
                "mathtext.it": f"{style.font_family}:italic",
                "mathtext.bf": f"{style.font_family}:bold",
                "mathtext.sf": style.font_family,
            }
        )


def save_figure(fig, stem: str, pad: float, out_dir: Path, style: FigureStyle) -> None:
    """Write one figure in every configured format."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in style.formats:
        kwargs = {"bbox_inches": "tight", "pad_inches": pad}
        if fmt in ("png", "jpg", "tif"):
            kwargs["dpi"] = style.dpi
        fig.savefig(out_dir / f"{stem}.{fmt}", **kwargs)
    rendered = ",".join(style.formats)
    print(f"Saved {stem}.{{{rendered}}} -> {out_dir}")

# ── colour / label maps ────────────────────────────────────────────────

COLORS = {
    "random": "#555555", "bcd": "#8B4513", "lfsr": "#2E8B57", "sbs": "#B15928",
    "mcsh_l1": "#5B9BD5", "mcsh_l2": "#1F78B4",
    "mcsh_l4": "#33A02C", "mcsh_l6": "#E31A1C",
    "pash_a08": "#FB9A99", "pash_a14": "#CAB2D6",
    "pash_c15": "#FF7F00", "pash_c14": "#FDBF6F",
    "pash_linear": "#6A3D9A", "pash_nocap": "#B15928",
}

LABELS = {
    "random": "Random", "bcd": "BCD (cyclic)", "lfsr": "LFSR (pseudorandom)",
    "sbs": "SBS (adapted)",
    "mcsh_l1": "MCSH $L_h{=}1$", "mcsh_l2": "MCSH $L_h{=}2$",
    "mcsh_l4": "MCSH $L_h{=}4$", "mcsh_l6": "MCSH $L_h{=}6$",
    "pash_a08": "PASH $\\alpha{=}0.8$", "pash_a14": "PASH $\\alpha{=}1.4$",
    "pash_c15": "PASH-cap $p_{\\max}{=}0.15$", "pash_c14": "PASH-cap $p_{\\max}{=}0.14$",
    "pash_linear": "PASH-linear", "pash_nocap": "PASH no-cap",
}

SHORT = {
    "random": "Rand", "bcd": "BCD", "lfsr": "LFSR", "sbs": "SBS",
    "mcsh_l1": "M1", "mcsh_l2": "M2", "mcsh_l4": "M4", "mcsh_l6": "M6",
    "pash_a08": "P.8", "pash_a14": "P1.4", "pash_c15": "Pc15", "pash_c14": "Pc14",
    "pash_linear": "PLin", "pash_nocap": "PNoC",
}

# ── data loading ────────────────────────────────────────────────────────

def load_csv(path: Path) -> List[Dict[str, object]]:
    rows = []
    with path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            r: Dict[str, object] = {}
            for k, v in row.items():
                if v in ("True", "False"):
                    r[k] = v == "True"
                else:
                    try:
                        r[k] = float(v)
                    except (ValueError, TypeError):
                        r[k] = v
            for ik in ("frame_errors", "total_frames", "bit_errors", "total_bits",
                       "collisions", "active_symbols", "worst_lag"):
                if ik in r and isinstance(r[ik], float):
                    r[ik] = int(r[ik])
            rows.append(r)
    return rows

# ── Fig. 1: structural exposure ────────────────────────────────────────

def plot_fig1(
    rows: List[Dict[str, object]],
    out_dir: Path = FIGURE_DIR,
    style: FigureStyle = DEFAULT_STYLE,
) -> None:
    apply_style(style)
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.0, 2.8))
    plt.subplots_adjust(wspace=0.38, left=0.08, right=0.97, top=0.88, bottom=0.17)

    # Panel (a): only methods needed for the core mechanism claim.
    spectrum_methods = ["random", "bcd", "lfsr", "mcsh_l2", "mcsh_l6", "pash_c15"]
    markers = {"random": "o", "bcd": "s", "lfsr": "d", "mcsh_l1": "^", "mcsh_l2": "D",
               "mcsh_l4": "v", "mcsh_l6": "p",
               "pash_c15": "s", "pash_c14": "*"}
    linestyles = {"random": "-", "bcd": "--", "lfsr": ":",
                  "mcsh_l1": "-", "mcsh_l2": "-", "mcsh_l4": "-", "mcsh_l6": "-",
                  "pash_c15": "--", "pash_c14": "-."}
    linewidths = {"random": 1.2, "bcd": 1.2, "lfsr": 1.2,
                  "mcsh_l1": 1.0, "mcsh_l2": 1.4, "mcsh_l4": 1.0, "mcsh_l6": 1.4,
                  "pash_c15": 1.6, "pash_c14": 1.2}
    for method in spectrum_methods:
        row = next(r for r in rows if r["method"] == method)
        lags = np.arange(1, 13)
        vals = [row[f"lag_{lg}"] for lg in lags]
        ax_a.plot(lags, vals, marker=markers.get(method, "o"), markersize=3.5,
                  linestyle=linestyles.get(method, "-"), linewidth=linewidths.get(method, 1.2),
                  color=COLORS[method], label=LABELS[method],
                  markeredgewidth=0.3, markeredgecolor="white")
    ax_a.axhline(64/512, color="#888888", linestyle=":", linewidth=0.8)
    ax_a.set_xlabel("Follower delay $d$")
    ax_a.set_ylabel("Collision rate")
    ax_a.grid(True, linestyle=":", linewidth=0.5)
    ax_a.legend(frameon=False, fontsize=5.5, ncol=1, loc="upper left")
    # Subfigure label
    ax_a.text(0.5, -0.28, "(a)", transform=ax_a.transAxes, fontsize=9, ha="center", va="top")

    # Panel (b): risk tradeoff — full design space
    tradeoff_methods = ["random", "bcd", "lfsr", "mcsh_l2", "mcsh_l6", "pash_c15"]
    annotation_offsets = {
        "random": (-8, 5), "bcd": (8, -8), "lfsr": (5, -7),
        "mcsh_l2": (5, -12), "mcsh_l6": (6, 6),
        "pash_c15": (6, 6),
    }
    for row in rows:
        if row["method"] not in tradeoff_methods:
            continue
        risk = max(row["worst_lag_collision"], row["candidate_collision"])
        is_pash = row["method"].startswith("pash")
        marker = "s" if is_pash else "o"
        sz = 55 if is_pash else 45
        ax_b.scatter(row["short_delay_collision"], risk, s=sz,
                     marker=marker,
                     color=COLORS.get(row["method"], "#999999"),
                     edgecolors="white", linewidth=0.3,
                     zorder=5 if is_pash else 3,
                     label=LABELS.get(row["method"], row["method"]))
        ax_b.annotate(
            SHORT.get(row["method"], row["method"]),
            (row["short_delay_collision"], risk),
            xytext=annotation_offsets.get(row["method"], (5, 3)),
            textcoords="offset points",
            fontsize=5.5, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.7),
        )

    # MCSH family connecting line (monotonic tradeoff)
    mcsh_order = ["mcsh_l2", "mcsh_l6", "bcd"]
    mcsh_x, mcsh_y = [], []
    for m in mcsh_order:
        row = next(r for r in rows if r["method"] == m)
        mcsh_x.append(row["short_delay_collision"])
        mcsh_y.append(max(row["worst_lag_collision"], row["candidate_collision"]))
    ax_b.plot(mcsh_x, mcsh_y, color="#999999", linestyle="--", linewidth=0.8, alpha=0.6, zorder=1)

    # Direction hints
    ax_b.annotate("← better short-delay", xy=(0.55, 0.10), xycoords="axes fraction",
                   fontsize=5, color="#1F78B4", ha="center", style="italic",
                   bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#1F78B4", alpha=0.7, linewidth=0.5))
    ax_b.annotate("↓ lower risk", xy=(0.96, 0.20), xycoords="axes fraction",
                   fontsize=5, color="#FF7F00", ha="right", style="italic",
                   bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#FF7F00", alpha=0.7, linewidth=0.5))

    ax_b.axhline(64/512, color="#888888", linestyle=":", linewidth=0.6)
    ax_b.axvline(64/512, color="#888888", linestyle=":", linewidth=0.6)
    ax_b.set_xlabel("Mean collision for $d{=}1,2$")
    ax_b.set_ylabel("Max(worst-lag, candidate-aware)")
    ax_b.set_xticks([0.00, 0.04, 0.08, 0.12])
    ax_b.legend(frameon=False, fontsize=4.5, ncol=1, loc="upper right")
    ax_b.text(0.5, -0.28, "(b)", transform=ax_b.transAxes, fontsize=9, ha="center", va="top")
    ax_b.grid(True, linestyle=":", linewidth=0.5)

    save_figure(fig, "comml_fig1_structural", 0.05, out_dir, style)
    plt.close(fig)

# ── Fig. 2: compact coded BLER + feedback robustness ───────────────────

def plot_fig2(
    coded_rows: List[Dict[str, object]],
    feedback_rows: List[Dict[str, object]],
    out_dir: Path = FIGURE_DIR,
    style: FigureStyle = DEFAULT_STYLE,
) -> None:
    apply_style(style)
    fig, (ax, ax_hm) = plt.subplots(
        1, 2, figsize=(7.1, 2.65), gridspec_kw={"width_ratios": [1.45, 1.0]}
    )
    plt.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.34, wspace=0.50)

    methods = ["random", "bcd", "lfsr", "mcsh_l2", "pash_c15"]
    method_labels = ["Random", "BCD (cyclic)", "LFSR (pseudorand.)",
                     "MCSH $L_h{=}2$", "PASH-cap $p_{\\max}{=}0.15$"]
    threats = ["fixed_d1", "fixed_d3", "candidate_aware", "causal_adaptive_lag"]
    threat_labels = ["$d{=}1$", "$d{=}3$", "candidate", "causal"]

    x = np.arange(len(threats))
    width = 0.16
    n_methods = len(methods)
    mix = [r for r in coded_rows if r["receiver"] == "mixllr"]

    for i, method in enumerate(methods):
        vals, lows, highs, fe_counts, is_zeros = [], [], [], [], []
        for threat in threats:
            row = next(r for r in mix if r["method"] == method and r["threat"] == threat)
            is_zero = row.get("zero_error", False)
            bler_v = row.get("bler_upper_bound", row["bler"]) if is_zero else row["bler"]
            vals.append(bler_v)
            lo = row.get("bler_boot_low", row["bler_ci_low"])
            hi = row.get("bler_boot_high", row["bler_ci_high"])
            lows.append(max(bler_v - lo, 0))
            highs.append(max(hi - bler_v, 0))
            fe_counts.append(int(row["frame_errors"]))
            is_zeros.append(is_zero)
        offset = (i - (n_methods - 1) / 2) * width
        ax.bar(x + offset, vals, width=width, color=COLORS[method],
               label=method_labels[i], edgecolor="white", linewidth=0.3)
        for j in range(len(threats)):
            if is_zeros[j]:
                ax.bar(x[j] + offset, vals[j], width=width,
                       color="none", edgecolor="#AA0000", hatch="//", linewidth=1.0)
        ax.errorbar(x + offset, vals, yerr=[lows, highs],
                    fmt="none", ecolor="black", capsize=2, linewidth=0.7)
        for j in range(len(threats)):
            label = "▲" + str(fe_counts[j]) if is_zeros[j] else str(fe_counts[j])
            bv = vals[j]
            ax.annotate(label, (x[j] + offset, max(bv, 1e-4)), xytext=(0, 3),
                        textcoords="offset points", fontsize=4.5,
                        ha="center", va="bottom", color="#AA0000" if is_zeros[j] else "#444444",
                        annotation_clip=False)

    ax.set_yscale("log")
    ax.set_ylim(5e-4, 1.5)
    ax.set_xticks(x, threat_labels)
    ax.set_ylabel("BLER")
    ax.set_title("Coded BLER", fontsize=8)
    ax.grid(True, axis="y", linestyle=":", linewidth=0.5)
    ax.legend(frameon=False, fontsize=5.0, ncol=5, loc="lower center",
              bbox_to_anchor=(0.5, -0.32), columnspacing=0.5)
    ax.text(0.5, -0.46, "(a)", transform=ax.transAxes, fontsize=9, ha="center", va="top")

    conditions = ["exact", "corrupt_30", "delay_4"]
    methods_hm = ["mcsh_l2", "pash_c15"]
    heatmap = []
    row_labels = []
    condition_labels = {"exact": "exact", "corrupt_30": "30% corrupt", "delay_4": "4-slot delay"}
    method_short = {"mcsh_l2": "MCSH", "pash_c15": "PASH-cap"}
    for condition in conditions:
        for method in methods_hm:
            row = next(
                r for r in feedback_rows
                if r["condition"] == condition and r["method"] == method
            )
            counts = np.asarray(json.loads(str(row["causal_lag_counts"])), dtype=float)
            heatmap.append(counts / counts.sum())
            row_labels.append(f"{condition_labels[condition]} / {method_short[method]}")
    matrix = np.asarray(heatmap)
    image = ax_hm.imshow(matrix, cmap="Blues", vmin=0.0, vmax=0.85, aspect="auto")
    # Annotate every cell with its percentage
    for row_index, row in enumerate(matrix):
        for col_index in range(len(row)):
            val = row[col_index]
            if val > 0.005:  # Label all cells with meaningful content
                ax_hm.text(
                    col_index, row_index, f"{val:.0%}",
                    ha="center", va="center", fontsize=5.0,
                    color="white" if val > 0.45 else "#222222",
                )
    # White grid lines around every cell
    ax_hm.set_xticks(np.arange(13) - 0.5, minor=True)
    ax_hm.set_yticks(np.arange(len(row_labels) + 1) - 0.5, minor=True)
    ax_hm.grid(which="minor", color="white", linewidth=1.2, zorder=3)
    ax_hm.set_xticks(np.arange(0, 12, 2), [f"$d={d}$" for d in range(1, 13, 2)], fontsize=5.5)
    ax_hm.set_yticks(np.arange(len(row_labels)), row_labels, fontsize=5.7)
    ax_hm.set_title("Causal-jammer lag selections", fontsize=8)
    ax_hm.text(0.5, -0.28, "(b)", transform=ax_hm.transAxes, fontsize=9, ha="center", va="top")
    ax_hm.tick_params(which="both", length=0)
    for spine in ax_hm.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("black")
        spine.set_zorder(4)
    colorbar = fig.colorbar(image, ax=ax_hm, fraction=0.045, pad=0.03)
    colorbar.ax.tick_params(labelsize=5, length=2)
    colorbar.set_label("Selection fraction", fontsize=6)

    save_figure(fig, "comml_fig2_compact", 0.04, out_dir, style)
    plt.close(fig)

# ── main ────────────────────────────────────────────────────────────────

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=FIGURE_DIR,
        help="destination directory for generated figures (default: figures/paper/)",
    )
    parser.add_argument(
        "--camera-ready",
        action="store_true",
        help="IEEE production profile: Helvetica fonts plus EPS output",
    )
    parser.add_argument(
        "--font-family",
        default=None,
        help="override the matplotlib font family",
    )
    parser.add_argument(
        "--formats",
        default=None,
        help="comma-separated output formats, e.g. 'pdf,eps'",
    )
    return parser.parse_args(argv)


def resolve_style(args: argparse.Namespace) -> FigureStyle:
    style = CAMERA_READY_STYLE if args.camera_ready else DEFAULT_STYLE
    overrides = {}
    if args.font_family is not None:
        overrides["font_family"] = args.font_family
        overrides["math_fontset"] = "custom"
    if args.formats is not None:
        parsed = tuple(f.strip() for f in args.formats.split(",") if f.strip())
        if parsed:
            overrides["formats"] = parsed
    return replace(style, **overrides) if overrides else style


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    style = resolve_style(args)
    structural = load_csv(STATS_DIR / "structural_summary.csv")
    coded = load_csv(STATS_DIR / "coded_summary.csv")
    feedback = load_csv(FEEDBACK_DIR / "summary.csv")
    print(
        f"Loaded {len(structural)} structural + {len(coded)} coded + "
        f"{len(feedback)} feedback rows"
    )
    print(
        f"Style: font={style.font_family}, formats={','.join(style.formats)}, "
        f"out={args.out_dir}"
    )
    plot_fig1(structural, args.out_dir, style)
    plot_fig2(coded, feedback, args.out_dir, style)


if __name__ == "__main__":
    main()
