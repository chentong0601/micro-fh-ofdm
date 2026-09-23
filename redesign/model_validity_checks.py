#!/usr/bin/env python3
"""Model-validity checks for the Python experimental chain.

The checks are intentionally separate from BER/BLER claims.  They verify
closed-form or structural invariants that must hold if the common-grid hopping
model is implemented correctly.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List

from advanced_experiment import AdvancedConfig, structural_experiment


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "results" / "model_validity"
REPORT = ROOT / "docs" / "experiments" / "model_validity_checks.md"


def load_structural_summary(path: Path) -> Dict[str, Dict[str, float | str]]:
    rows: Dict[str, Dict[str, float | str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed: Dict[str, float | str] = {}
            for key, value in row.items():
                if key in {"method", "label"}:
                    parsed[key] = value
                else:
                    parsed[key] = float(value)
            rows[str(row["method"])] = parsed
    return rows


def write_csv(path: Path, rows: Iterable[Dict[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def add_check(
    checks: List[Dict[str, object]],
    name: str,
    value: float,
    expected: str,
    passed: bool,
    tolerance: str,
) -> None:
    checks.append(
        {
            "check": name,
            "value": value,
            "expected": expected,
            "tolerance": tolerance,
            "passed": bool(passed),
        }
    )


def run_checks(rows: Dict[str, Dict[str, float | str]], cfg: AdvancedConfig) -> List[Dict[str, object]]:
    checks: List[Dict[str, object]] = []
    load = cfg.n_active / cfg.n_phys
    eps = 1e-12

    random = rows["random"]
    mcsh2 = rows["mcsh_l2"]
    mcsh6 = rows["mcsh_l6"]
    pash_cap = rows["pash_c15"]

    add_check(
        checks,
        "random short-delay collision equals active load",
        float(random["short_delay_collision"]),
        f"{load:.3f}",
        abs(float(random["short_delay_collision"]) - load) <= 0.003,
        "+/- 0.003",
    )
    add_check(
        checks,
        "random candidate-aware collision equals active load",
        float(random["candidate_collision"]),
        f"{load:.3f}",
        abs(float(random["candidate_collision"]) - load) <= 0.003,
        "+/- 0.003",
    )
    add_check(
        checks,
        "MCSH Lh=2 lag-1 collision is zero",
        float(mcsh2["lag_1"]),
        "0",
        float(mcsh2["lag_1"]) <= eps,
        "<= 1e-12",
    )
    add_check(
        checks,
        "MCSH Lh=2 lag-2 collision is zero",
        float(mcsh2["lag_2"]),
        "0",
        float(mcsh2["lag_2"]) <= eps,
        "<= 1e-12",
    )
    add_check(
        checks,
        "MCSH Lh=2 worst lag is just outside memory",
        float(mcsh2["worst_lag"]),
        "3",
        int(round(float(mcsh2["worst_lag"]))) == 3,
        "exact lag index",
    )
    expected_l2_boundary = cfg.n_active / (cfg.n_phys - 2 * cfg.n_active)
    add_check(
        checks,
        "MCSH Lh=2 boundary collision matches closed form",
        float(mcsh2["lag_3"]),
        f"{expected_l2_boundary:.6f}",
        abs(float(mcsh2["lag_3"]) - expected_l2_boundary) <= 0.002,
        "+/- 0.002",
    )
    add_check(
        checks,
        "MCSH Lh=6 worst lag is just outside memory",
        float(mcsh6["worst_lag"]),
        "7",
        int(round(float(mcsh6["worst_lag"]))) == 7,
        "exact lag index",
    )
    add_check(
        checks,
        "MCSH Lh=6 exposes concentrated lag spike",
        float(mcsh6["worst_lag_collision"]),
        "> 0.45",
        float(mcsh6["worst_lag_collision"]) > 0.45,
        "lower bound",
    )
    expected_l6_boundary = cfg.n_active / (cfg.n_phys - 6 * cfg.n_active)
    add_check(
        checks,
        "MCSH Lh=6 boundary collision matches closed form",
        float(mcsh6["lag_7"]),
        f"{expected_l6_boundary:.6f}",
        abs(float(mcsh6["lag_7"]) - expected_l6_boundary) <= 0.002,
        "+/- 0.002",
    )
    add_check(
        checks,
        "PASH-cap reduces worst structural risk vs MCSH Lh=2",
        max(float(pash_cap["worst_lag_collision"]), float(pash_cap["candidate_collision"])),
        f"< {max(float(mcsh2['worst_lag_collision']), float(mcsh2['candidate_collision'])):.3f}",
        max(float(pash_cap["worst_lag_collision"]), float(pash_cap["candidate_collision"]))
        < max(float(mcsh2["worst_lag_collision"]), float(mcsh2["candidate_collision"])),
        "strict inequality",
    )
    add_check(
        checks,
        "PASH-cap sacrifices zero short-delay avoidance",
        float(pash_cap["short_delay_collision"]),
        "> 0",
        float(pash_cap["short_delay_collision"]) > 0.0,
        "strict inequality",
    )
    add_check(
        checks,
        "PASH-cap candidate-aware collision respects p_max",
        float(pash_cap["candidate_collision"]),
        "<= 0.15",
        float(pash_cap["candidate_collision"]) <= 0.152,
        "0.002 Monte Carlo tolerance",
    )
    return checks


def write_report(checks: List[Dict[str, object]], cfg: AdvancedConfig, generated: bool) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for row in checks if row["passed"])
    lines = [
        "# Python 模型有效性检查",
        "",
        "## 目的",
        "",
        "该检查不用于新增性能收益，而是验证当前 Python 共同物理栅格实现满足",
        "基础结构不变量和可由封闭形式预期的碰撞规律。",
        "",
        "## 运行配置",
        "",
        f"- `N={cfg.n_phys}`",
        f"- `S={cfg.n_active}`",
        f"- `S/N={cfg.n_active/cfg.n_phys:.3f}`",
        "- 结构统计来源："
        + ("重新生成 `structural_experiment('paper')`" if generated else "读取 `results/advanced/structural_summary.csv`"),
        "",
        "## 检查结果",
        "",
        "| 检查项 | 实测值 | 期望 | 容差 | 结果 |",
        "|---|---:|---:|---:|---|",
    ]
    for row in checks:
        lines.append(
            f"| {row['check']} | {float(row['value']):.6g} | {row['expected']} | "
            f"{row['tolerance']} | {'PASS' if row['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            f"通过 `{passed}/{len(checks)}` 项。",
            "",
            "## 解释",
            "",
            "- random hopping 的碰撞率应接近 active load `S/N`。",
            "- MCSH 的记忆内 lag collision 必须为零，否则 recent-set 排斥实现错误。",
            "- MCSH 的 worst lag 出现在 `L_h+1`，说明硬排斥把风险推到记忆边界外。",
            "- PASH-cap 若能降低 worst structural risk，同时短时延碰撞不为零，说明其实现了"
            "“牺牲已知短时延最优性以降低可预测性风险”的设计目标。",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cfg = AdvancedConfig()
    source = RESULT_DIR / "structural_summary_reference.csv"
    comml_summary = ROOT / "results" / "comml" / "stats" / "structural_summary.csv"
    advanced_summary = ROOT / "results" / "advanced" / "stats" / "structural_summary.csv"

    generated = False
    if comml_summary.exists():
        rows = load_structural_summary(comml_summary)
    elif advanced_summary.exists():
        rows = load_structural_summary(advanced_summary)
    else:
        generated = True
        structural = structural_experiment("paper", cfg)
        write_csv(source, structural)
        rows = load_structural_summary(source)

    checks = run_checks(rows, cfg)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(RESULT_DIR / "model_validity_checks.csv", checks)
    write_report(checks, cfg, generated)

    failed = [row for row in checks if not row["passed"]]
    print(f"Model-validity checks passed {len(checks) - len(failed)}/{len(checks)}")
    print(f"Saved checks to {RESULT_DIR / 'model_validity_checks.csv'}")
    print(f"Saved report to {REPORT}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
