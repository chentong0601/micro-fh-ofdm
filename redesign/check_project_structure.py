#!/usr/bin/env python3
"""Check project structure invariants for the current research workflow."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "run.py",
    "docs/README.md",
    "docs/PROCESS.md",
    "docs/PROJECT_STATUS.md",
    "docs/CHANGELOG.md",
    "docs/reproducibility.md",
    "docs/registry/DATA_REGISTRY.md",
    "docs/registry/FIGURE_REGISTRY.md",
    "docs/registry/ARTIFACT_REGISTRY.md",
    ".vscode/settings.json",
    ".vscode/tasks.json",
    ".vscode/extensions.json",
    "micro_fh_ofdm.code-workspace",
    "redesign/model_validity_checks.py",
    "redesign/pash_parameter_sweep.py",
    "paper/full_ieee.tex",
    "paper/full_ieee.pdf",
    "output/pdf/full_ieee.pdf",
    "results/advanced/paper/structural_summary.csv",
    "results/advanced/paper/coded_summary.csv",
    "figures/paper/fig7_adversarial_pash.pdf",
    "docs/experiments/model_validity_checks.md",
    "results/model_validity/model_validity_checks.csv",
    "docs/experiments/pash_parameter_sweep_results.md",
    "results/pash_sweep/summary.csv",
    "figures/paper/fig8_pash_parameter_sweep.pdf",
    "docs/experiments/pash_optimization_results.md",
]

FORBIDDEN_PATHS = [
    "src",
    "scripts",
    "paper/test_extract",
    "figures/v2_archive",
]

ALLOWED_FIGURE_TOP_FILES = {"README.md"}
ALLOWED_RESULT_TOP_FILES = {"README.md"}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_latex_figures(tex_path: Path) -> list[str]:
    """Parse \\includegraphics commands and verify each referenced file exists."""
    import re
    errors: list[str] = []
    if not tex_path.exists():
        return errors
    content = tex_path.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(r'\\includegraphics(?:\[.*?\])?\{(.*?)\}')
    tex_dir = tex_path.parent
    for m in pattern.finditer(content):
        rel = m.group(1)
        fig_path = (tex_dir / rel).resolve()
        if not fig_path.exists():
            errors.append(f"LaTeX figure not found: {rel} (resolved: {fig_path})")
    return errors


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")

    for rel in FORBIDDEN_PATHS:
        if (ROOT / rel).exists():
            errors.append(f"legacy path should be archived, not top-level: {rel}")

    results_top = ROOT / "results"
    for path in results_top.iterdir():
        if path.is_file() and path.name not in ALLOWED_RESULT_TOP_FILES:
            errors.append(f"unexpected top-level results file: results/{path.name}")

    figures_top = ROOT / "figures"
    for path in figures_top.iterdir():
        if path.is_file() and path.name not in ALLOWED_FIGURE_TOP_FILES:
            errors.append(f"unexpected top-level figures file: figures/{path.name}")

    # Check LaTeX figure references
    for tex_name in ("full_ieee.tex", "comml_ieee.tex"):
        tex_path = ROOT / "paper" / tex_name
        if tex_path.exists():
            errors.extend(check_latex_figures(tex_path))

    paper_pdf = ROOT / "paper" / "full_ieee.pdf"
    output_pdf = ROOT / "output" / "pdf" / "full_ieee.pdf"
    if paper_pdf.exists() and output_pdf.exists() and sha1(paper_pdf) != sha1(output_pdf):
        errors.append("paper/full_ieee.pdf and output/pdf/full_ieee.pdf differ")
    comml_pdf = ROOT / "paper" / "comml_ieee.pdf"
    comml_output_pdf = ROOT / "output" / "pdf" / "comml_ieee.pdf"
    if comml_pdf.exists() and comml_output_pdf.exists() and sha1(comml_pdf) != sha1(comml_output_pdf):
        errors.append("paper/comml_ieee.pdf and output/pdf/comml_ieee.pdf differ")

    if errors:
        print("Project structure check failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Project structure check passed.")
    if paper_pdf.exists():
        print("Current paper PDF hash:", sha1(output_pdf))
    else:
        print("No current paper PDF; run 'python run.py paper' to compile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
