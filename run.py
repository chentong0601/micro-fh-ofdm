#!/usr/bin/env python3
"""Unified command runner for the Micro-FH OFDM research project.

The runner deliberately separates three concerns:

1. project checks and lightweight experiment validation;
2. experiment execution;
3. paper compilation.

Use `python run.py quick` while developing, `python run.py paper` when only the
PDF should be rebuilt, and `python run.py preflight` before handing over the
current paper artifact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / "bin" / "python"

PYTHON_CHECK_FILES = [
    ROOT / "run.py",
    ROOT / "redesign" / "check_project_structure.py",
    ROOT / "redesign" / "plot_results.py",
    ROOT / "redesign" / "plot_innovation.py",
    ROOT / "redesign" / "audit_lag_predictability.py",
    ROOT / "redesign" / "advanced_experiment.py",
    ROOT / "redesign" / "model_validity_checks.py",
    ROOT / "redesign" / "pash_parameter_sweep.py",
    ROOT / "redesign" / "pash_optimization_experiment.py",
    ROOT / "redesign" / "plot_comml.py",
    ROOT / "redesign" / "validate_adversarial_threats.py",
    ROOT / "redesign" / "feedback_robustness_experiment.py",
]


@dataclass(frozen=True)
class OutputItem:
    label: str
    path: Path
    kind: str


OUTPUTS = [
    OutputItem("CommL paper source", ROOT / "paper" / "comml_ieee.tex", "file"),
    OutputItem("CommL working PDF", ROOT / "paper" / "comml_ieee.pdf", "pdf"),
    OutputItem("CommL deliverable PDF", ROOT / "output" / "pdf" / "comml_ieee.pdf", "pdf"),
    OutputItem("Main paper source", ROOT / "paper" / "full_ieee.tex", "file"),
    OutputItem("Working paper PDF", ROOT / "paper" / "full_ieee.pdf", "pdf"),
    OutputItem("Deliverable paper PDF", ROOT / "output" / "pdf" / "full_ieee.pdf", "pdf"),
    OutputItem("Advanced structural data (paper)", ROOT / "results" / "advanced" / "paper" / "structural_summary.csv", "csv"),
    OutputItem("Advanced coded data (paper)", ROOT / "results" / "advanced" / "paper" / "coded_summary.csv", "csv"),
    OutputItem("CommL final coded data", ROOT / "results" / "comml" / "stats" / "coded_summary.csv", "csv"),
    OutputItem("CommL structural figure", ROOT / "figures" / "paper" / "comml_fig1_structural.pdf", "pdf"),
    OutputItem("CommL compact results figure", ROOT / "figures" / "paper" / "comml_fig2_compact.pdf", "pdf"),
    OutputItem("Feedback robustness data", ROOT / "results" / "comml" / "feedback_robustness" / "summary.csv", "csv"),
    OutputItem("Adversarial threat validity", ROOT / "results" / "model_validity" / "adversarial_threat_checks.csv", "csv"),
    OutputItem("PASH sweep data", ROOT / "results" / "pash_sweep" / "summary.csv", "csv"),
    OutputItem("PASH sweep figure", ROOT / "figures" / "paper" / "fig8_pash_parameter_sweep.pdf", "pdf"),
    OutputItem("Model-validity data", ROOT / "results" / "model_validity" / "model_validity_checks.csv", "csv"),
    OutputItem("Model-validity report", ROOT / "docs" / "experiments" / "model_validity_checks.md", "file"),
    OutputItem("PASH sweep report", ROOT / "docs" / "experiments" / "pash_parameter_sweep_results.md", "file"),
    OutputItem("PASH opt diagnostic data", ROOT / "results" / "pash_opt" / "summary.csv", "csv"),
    OutputItem("PASH opt report", ROOT / "docs" / "experiments" / "pash_optimization_results.md", "file"),
]


def project_python() -> Path:
    if PYTHON.exists():
        return PYTHON
    return Path(sys.executable)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72, flush=True)


def step(index: int, total: int, title: str) -> None:
    print(f"\n[{index}/{total}] {title}", flush=True)


def run(cmd: Sequence[str | Path], cwd: Path = ROOT) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"  cwd: {cwd}")
    print(f"  cmd: {printable}", flush=True)
    started = time.perf_counter()
    subprocess.run([str(part) for part in cmd], cwd=cwd, check=True)
    print(f"  done in {time.perf_counter() - started:.1f}s", flush=True)


def run_steps(title: str, actions: Sequence[tuple[str, Callable[[], None]]]) -> None:
    banner(title)
    total = len(actions)
    started = time.perf_counter()
    for index, (name, action) in enumerate(actions, start=1):
        step(index, total, name)
        action()
    print(f"\nFinished: {title} ({time.perf_counter() - started:.1f}s)", flush=True)


def check_structure() -> None:
    run([project_python(), ROOT / "redesign" / "check_project_structure.py"])


def check_python_files() -> None:
    run([project_python(), "-m", "py_compile", *PYTHON_CHECK_FILES])


def run_validity() -> None:
    run([project_python(), ROOT / "redesign" / "model_validity_checks.py"])
    print("  outputs:")
    print(f"  - {rel(ROOT / 'results' / 'model_validity' / 'model_validity_checks.csv')}")
    print(f"  - {rel(ROOT / 'docs' / 'experiments' / 'model_validity_checks.md')}")


def build_full_ieee() -> None:
    run(["tectonic", "full_ieee.tex"], cwd=ROOT / "paper")
    output_dir = ROOT / "output" / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "paper" / "full_ieee.pdf", output_dir / "full_ieee.pdf")
    print("  outputs:")
    print(f"  - {rel(ROOT / 'paper' / 'full_ieee.pdf')}")
    print(f"  - {rel(output_dir / 'full_ieee.pdf')}")


def build_comml_ieee() -> None:
    run(["tectonic", "comml_ieee.tex"], cwd=ROOT / "paper")
    output_dir = ROOT / "output" / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "paper" / "comml_ieee.pdf", output_dir / "comml_ieee.pdf")
    print("  outputs:")
    print(f"  - {rel(ROOT / 'paper' / 'comml_ieee.pdf')}")
    print(f"  - {rel(output_dir / 'comml_ieee.pdf')}")


def check_comml_outputs() -> None:
    expected = [
        ROOT / "paper" / "comml_ieee.tex",
        ROOT / "paper" / "comml_ieee.pdf",
        ROOT / "output" / "pdf" / "comml_ieee.pdf",
        ROOT / "results" / "comml" / "stats" / "structural_summary.csv",
        ROOT / "results" / "comml" / "stats" / "coded_summary.csv",
        ROOT / "results" / "comml" / "stats" / "run_manifest.json",
        ROOT / "results" / "model_validity" / "adversarial_threat_checks.csv",
        ROOT / "figures" / "paper" / "comml_fig1_structural.pdf",
        ROOT / "figures" / "paper" / "comml_fig2_compact.pdf",
        ROOT / "results" / "comml" / "feedback_robustness" / "summary.csv",
        ROOT / "results" / "comml" / "feedback_robustness" / "run_manifest.json",
    ]
    print_expected(expected)
    if any(not path.exists() for path in expected):
        raise SystemExit(1)
    if sha1(expected[1]) != sha1(expected[2]):
        print("  - MISMATCH CommL PDF copies have different SHA1")
        raise SystemExit(1)
    print("  - OK      CommL PDF copies have identical SHA1")

    source = expected[0].read_text(encoding="utf-8")
    if not re.search(r"\\documentclass\[[^\]]*10pt[^\]]*\]\{IEEEtran\}", source):
        print("  - MISMATCH CommL source must use IEEEtran 10pt format")
        raise SystemExit(1)
    abstract_match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", source, flags=re.DOTALL
    )
    if abstract_match is None:
        print("  - MISSING CommL abstract")
        raise SystemExit(1)
    abstract_plain = re.sub(r"\\[A-Za-z]+|[{}$~\\]", " ", abstract_match.group(1))
    abstract_words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", abstract_plain)
    if not 75 <= len(abstract_words) <= 100:
        print(f"  - MISMATCH CommL abstract has {len(abstract_words)} words; expected 75--100")
        raise SystemExit(1)
    print(f"  - OK      CommL abstract word count={len(abstract_words)}")

    pdf_info = subprocess.check_output(["pdfinfo", expected[1]], text=True)
    pages_match = re.search(r"^Pages:\s+(\d+)", pdf_info, flags=re.MULTILINE)
    pages = int(pages_match.group(1)) if pages_match else 999
    if pages > 5:
        print(f"  - MISMATCH CommL PDF has {pages} pages; maximum is 5")
        raise SystemExit(1)
    print(f"  - OK      CommL PDF page count={pages}")

    manifest = json.loads((ROOT / "results" / "comml" / "stats" / "run_manifest.json").read_text())
    recorded_hash = manifest["source_files"]["redesign/advanced_experiment.py"]["sha256"]
    current_hash = hashlib.sha256(
        (ROOT / "redesign" / "advanced_experiment.py").read_bytes()
    ).hexdigest()
    if recorded_hash != current_hash:
        print("  - MISMATCH CommL stats were not generated by the current advanced_experiment.py")
        raise SystemExit(1)
    print("  - OK      CommL stats source hash matches current implementation")

    feedback_manifest = json.loads(
        (ROOT / "results" / "comml" / "feedback_robustness" / "run_manifest.json").read_text()
    )
    feedback_sources = feedback_manifest["source_sha256"]
    for source_name in (
        "redesign/advanced_experiment.py",
        "redesign/feedback_robustness_experiment.py",
    ):
        current_source_hash = hashlib.sha256((ROOT / source_name).read_bytes()).hexdigest()
        if feedback_sources[source_name] != current_source_hash:
            print(f"  - MISMATCH Feedback results were not generated by current {source_name}")
            raise SystemExit(1)
    print("  - OK      Feedback-results source hashes match current implementations")


def check_outputs() -> None:
    print("  normalized output locations:")
    missing = []
    for item in OUTPUTS:
        exists = item.path.exists()
        status = "OK" if exists else "MISSING"
        detail = ""
        if exists and item.kind == "csv":
            detail = f", rows={csv_rows(item.path)}"
        elif exists and item.kind == "pdf":
            detail = f", sha1={sha1(item.path)[:12]}"
        elif exists:
            detail = f", size={item.path.stat().st_size} bytes"
        print(f"  - {status:7s} {item.label}: {rel(item.path)}{detail}")
        if not exists:
            missing.append(item)

    paper_pdf = ROOT / "paper" / "full_ieee.pdf"
    deliverable_pdf = ROOT / "output" / "pdf" / "full_ieee.pdf"
    if paper_pdf.exists() and deliverable_pdf.exists():
        same = sha1(paper_pdf) == sha1(deliverable_pdf)
        print(f"  - {'OK' if same else 'MISMATCH':7s} PDF copies have identical SHA1")
        if not same:
            missing.append(OutputItem("PDF hash match", deliverable_pdf, "pdf"))

    if missing:
        raise SystemExit(1)


def run_experiment(command: str) -> None:
    commands = {
        "pash-smoke": ([project_python(), ROOT / "redesign" / "pash_parameter_sweep.py", "smoke"], [
            ROOT / "tmp" / "smoke-pash-sweep" / "results" / "summary.csv",
            ROOT / "tmp" / "smoke-pash-sweep" / "figures" / "fig8_pash_parameter_sweep.pdf",
        ]),
        "pash-paper": ([project_python(), ROOT / "redesign" / "pash_parameter_sweep.py", "paper"], [
            ROOT / "results" / "pash_sweep" / "summary.csv",
            ROOT / "figures" / "paper" / "fig8_pash_parameter_sweep.pdf",
        ]),
        "advanced-smoke": (["sh", ROOT / "redesign" / "run_advanced.sh", "smoke"], [
            ROOT / "tmp" / "smoke-advanced" / "results" / "structural_summary.csv",
            ROOT / "tmp" / "smoke-advanced" / "results" / "coded_summary.csv",
        ]),
        "advanced-paper": (["sh", ROOT / "redesign" / "run_advanced.sh", "paper"], [
            ROOT / "results" / "advanced" / "paper" / "structural_summary.csv",
            ROOT / "results" / "advanced" / "paper" / "coded_summary.csv",
            ROOT / "figures" / "paper" / "fig7_adversarial_pash.pdf",
        ]),
        "advanced-stats": (["sh", ROOT / "redesign" / "run_advanced.sh", "stats"], [
            ROOT / "results" / "advanced" / "stats" / "structural_summary.csv",
            ROOT / "results" / "advanced" / "stats" / "coded_summary.csv",
            ROOT / "figures" / "paper" / "fig7_adversarial_pash.pdf",
        ]),
        "comml-smoke": (["sh", ROOT / "redesign" / "run_advanced.sh", "comml-smoke"], [
            ROOT / "tmp" / "smoke-comml" / "results" / "structural_summary.csv",
            ROOT / "tmp" / "smoke-comml" / "results" / "coded_summary.csv",
        ]),
        "comml-stats": (["sh", ROOT / "redesign" / "run_advanced.sh", "comml-stats"], [
            ROOT / "results" / "comml" / "stats" / "structural_summary.csv",
            ROOT / "results" / "comml" / "stats" / "coded_summary.csv",
            ROOT / "figures" / "paper" / "comml_fig1_structural.pdf",
            ROOT / "figures" / "paper" / "comml_fig2_compact.pdf",
        ]),
        "comml-stats-9db": ([project_python(), ROOT / "redesign" / "advanced_experiment.py",
                             "--profile", "comml-stats", "--snr", "9.0"], [
            ROOT / "results" / "comml" / "stats_9dB" / "structural_summary.csv",
            ROOT / "results" / "comml" / "stats_9dB" / "coded_summary.csv",
        ]),
        "comml-stats-jsr10": ([project_python(), ROOT / "redesign" / "advanced_experiment.py",
                               "--profile", "comml-stats", "--jsr", "10.0"], [
            ROOT / "results" / "comml" / "stats_jsr10dB" / "structural_summary.csv",
            ROOT / "results" / "comml" / "stats_jsr10dB" / "coded_summary.csv",
        ]),
        "feedback-smoke": ([project_python(), ROOT / "redesign" / "feedback_robustness_experiment.py", "smoke"], [
            ROOT / "tmp" / "smoke-feedback-robustness" / "summary.csv",
            ROOT / "tmp" / "smoke-feedback-robustness" / "comml_fig3_feedback_robustness.pdf",
        ]),
        "feedback-stats": ([project_python(), ROOT / "redesign" / "feedback_robustness_experiment.py", "stats"], [
            ROOT / "results" / "comml" / "feedback_robustness" / "summary.csv",
            ROOT / "results" / "comml" / "feedback_robustness" / "run_manifest.json",
            ROOT / "figures" / "paper" / "comml_fig3_feedback_robustness.pdf",
        ]),
        "feedback-plot": ([project_python(), ROOT / "redesign" / "feedback_robustness_experiment.py", "plot"], [
            ROOT / "figures" / "paper" / "comml_fig3_feedback_robustness.pdf",
            ROOT / "docs" / "experiments" / "comml_feedback_robustness_results.md",
        ]),
        "pash-opt-smoke": (["sh", ROOT / "redesign" / "run_pash_opt.sh", "smoke"], [
            ROOT / "tmp" / "smoke-pash-opt" / "results" / "summary.csv",
        ]),
        "pash-opt-paper": (["sh", ROOT / "redesign" / "run_pash_opt.sh", "paper"], [
            ROOT / "results" / "pash_opt" / "summary.csv",
        ]),
        "phase2-smoke": (["sh", ROOT / "redesign" / "run_phase2.sh", "smoke"], [
            ROOT / "tmp" / "innovation-smoke" / "summary.csv",
        ]),
        "phase2-paper": (["sh", ROOT / "redesign" / "run_phase2.sh", "paper"], [
            ROOT / "results" / "innovation" / "summary.csv",
            ROOT / "figures" / "paper" / "fig3_core_method.pdf",
        ]),
        "baseline-smoke": (["sh", ROOT / "redesign" / "run_all.sh", "smoke"], [
            ROOT / "tmp" / "smoke-results" / "summary.csv",
        ]),
        "baseline-paper": (["sh", ROOT / "redesign" / "run_all.sh", "paper"], [
            ROOT / "results" / "redesign" / "summary.csv",
            ROOT / "figures" / "paper" / "fig1_ber_common_grid.pdf",
        ]),
    }
    cmd, expected = commands[command]
    actions: list[tuple[str, Callable[[], None]]] = [
        ("run experiment script", lambda: run(cmd)),
    ]
    if command == "comml-stats":
        actions.append(
            ("generate Communications Letters figures",
             lambda: run([project_python(), ROOT / "redesign" / "plot_comml.py"]))
        )
    if command == "comml-stats-9db":
        pass  # 9dB run is data-only; skip figure generation to avoid overwriting 12dB plots
    if command == "comml-stats-jsr10":
        pass  # JSR run is data-only
    actions.append(("show expected storage paths", lambda: print_expected(expected)))
    run_steps(f"Experiment: {command}", actions)


def run_experiment_sequence(profile: str) -> None:
    if profile == "smoke":
        sequence = [
            ("model-validity checks", "validity"),
            ("baseline common-grid smoke", "baseline-smoke"),
            ("MCSH-BRW phase-2 smoke", "phase2-smoke"),
            ("PASH adversarial smoke", "advanced-smoke"),
            ("PASH parameter sweep smoke", "pash-smoke"),
        ]
        title = "All experiments: smoke profile, no paper compilation"
    elif profile == "paper":
        sequence = [
            ("model-validity checks", "validity"),
            ("baseline common-grid formal experiment", "baseline-paper"),
            ("MCSH-BRW phase-2 formal experiment", "phase2-paper"),
            ("PASH adversarial formal experiment", "advanced-paper"),
            ("PASH parameter sweep formal experiment", "pash-paper"),
        ]
        title = "All experiments: paper profile, no paper compilation"
    else:
        raise ValueError(profile)

    actions: list[tuple[str, Callable[[], None]]] = []
    for label, command in sequence:
        if command == "validity":
            actions.append((label, run_validity))
        else:
            actions.append((label, lambda command=command: run_experiment(command)))
    actions.append(("check normalized output storage", check_outputs))
    run_steps(title, actions)


def print_expected(paths: Sequence[Path]) -> None:
    for path in paths:
        status = "OK" if path.exists() else "MISSING"
        detail = ""
        if path.exists() and path.suffix == ".csv":
            detail = f", rows={csv_rows(path)}"
        elif path.exists() and path.suffix == ".pdf":
            detail = f", sha1={sha1(path)[:12]}"
        print(f"  - {status:7s} {rel(path)}{detail}")


def quick_check() -> None:
    run_steps(
        "Project quick check: no paper compilation",
        [
            ("check project structure", check_structure),
            ("compile Python entry points", check_python_files),
            ("run model-validity experiment", run_validity),
            ("check normalized output storage", check_outputs),
        ],
    )


def smoke_check() -> None:
    run_steps(
        "Project smoke check: no paper compilation",
        [
            ("run quick project check", quick_check),
            ("run all smoke experiments", lambda: run_experiment_sequence("smoke")),
        ],
    )


def preflight() -> None:
    run_steps(
        "Full preflight: checks plus paper compilation",
        [
            ("run quick project check", quick_check),
            ("compile full IEEE paper", build_full_ieee),
            ("final structure check", check_structure),
            ("final output storage check", check_outputs),
        ],
    )


def comml_preflight() -> None:
    run_steps(
        "Communications Letters preflight",
        [
            ("compile Python entry points", check_python_files),
            ("run adversarial threat checks",
             lambda: run([project_python(), ROOT / "redesign" / "validate_adversarial_threats.py"])),
            ("regenerate Communications Letters figures",
             lambda: run([project_python(), ROOT / "redesign" / "plot_comml.py"])),
            ("compile Communications Letters paper", build_comml_ieee),
            ("check project structure", check_structure),
            ("check Communications Letters artifacts", check_comml_outputs),
        ],
    )


def dispatch(command: str) -> None:
    if command in {"quick", "check"}:
        quick_check()
    elif command == "smoke":
        smoke_check()
    elif command == "validity":
        run_steps("Model-validity experiment", [("run model-validity checks", run_validity)])
    elif command == "threat-validity":
        run_steps(
            "Adversarial threat validity",
            [("run adversarial threat checks",
              lambda: run([project_python(), ROOT / "redesign" / "validate_adversarial_threats.py"]))],
        )
    elif command == "comml-plot":
        run_steps(
            "Communications Letters figures",
            [("generate figures", lambda: run([project_python(), ROOT / "redesign" / "plot_comml.py"]))],
        )
    elif command == "paper":
        run_steps("Paper build only", [("compile full IEEE paper", build_full_ieee)])
    elif command == "comml-paper":
        run_steps(
            "Communications Letters paper build only",
            [("compile Communications Letters paper", build_comml_ieee)],
        )
    elif command == "comml-preflight":
        comml_preflight()
    elif command == "preflight":
        preflight()
    elif command == "outputs":
        run_steps("Output storage check", [("check normalized output storage", check_outputs)])
    elif command == "experiments-smoke":
        run_experiment_sequence("smoke")
    elif command == "experiments-paper":
        run_experiment_sequence("paper")
    else:
        run_experiment(command)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run project checks, experiments, and paper builds from one entry point."
    )
    parser.add_argument(
        "command",
        choices=[
            "quick",
            "check",
            "smoke",
            "validity",
            "threat-validity",
            "paper",
            "comml-paper",
            "comml-preflight",
            "preflight",
            "outputs",
            "experiments-smoke",
            "experiments-paper",
            "pash-smoke",
            "pash-paper",
            "advanced-smoke",
            "advanced-paper",
            "advanced-stats",
            "comml-smoke",
            "comml-stats",
            "comml-stats-9db",
            "comml-stats-jsr10",
            "comml-plot",
            "feedback-smoke",
            "feedback-stats",
            "feedback-plot",
            "pash-opt-smoke",
            "pash-opt-paper",
            "phase2-smoke",
            "phase2-paper",
            "baseline-smoke",
            "baseline-paper",
        ],
        help="Task to run. Use 'quick' for checks only; use 'paper' to rebuild the PDF.",
    )
    args = parser.parse_args()
    dispatch(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
