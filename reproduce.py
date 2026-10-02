#!/usr/bin/env python3
"""One-worker bounded reproduction using only the Python standard library.

Run from a clean extraction.  Fresh output is separate from published evidence.
Resume records are advisory: a successful exit is skipped only when every
output declared for that task and every declared dependency still validates.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DEFAULT_TASKS = [
    "tests", "pilot", "populations", "horn", "family", "verify",
    "joint", "joint-replay", "report",
]


def child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def _expected_files() -> list[str]:
    path = ROOT / "results" / "expected-files.json"
    return json.loads(path.read_text()) if path.exists() else []


def declared_outputs(task: str) -> tuple[str, ...]:
    """Return deterministic outputs whose presence/content defines task completion."""
    if task == "tests":
        return ("tests.log",)
    if task == "pilot":
        return ("pilot.json",)
    if task.startswith("population-"):
        n = task.split("-", 1)[1]
        return (f"population-{n}.csv", f"population-{n}-summary.json")
    if task == "horn":
        return ("horn.json", "horn-cases.jsonl", "horn-certificates.json")
    if task == "family":
        return ("family.csv", "certificate-pinned.json", "certificate-remined.json")
    if task == "verify":
        return ("independent-verification.json",)
    if task == "joint":
        excluded = {"joint-replay.json", "joint-results-table.tex", "joint-oracle-strata.tex"}
        return tuple(sorted(
            name for name in _expected_files()
            if (name.startswith("joint-") or name.startswith("joint-certificates/"))
            and name not in excluded
        ))
    if task == "joint-replay":
        return ("joint-replay.json",)
    if task == "report":
        return ("summary.json", "population-table.tex", "joint-results-table.tex", "joint-oracle-strata.tex", "choice-profile-table.tex", "paper-numbers.tex")
    raise ValueError(f"unknown task: {task}")


def task_dependencies(task: str) -> tuple[str, ...]:
    populations = tuple(f"population-{n}" for n in range(1, 8))
    if task == "verify":
        return populations + ("horn", "family")
    if task == "joint-replay":
        return ("joint",)
    if task == "report":
        return populations + ("horn", "family", "verify", "joint", "joint-replay")
    return ()


def _tests_log_valid(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(errors="replace")
    return bool(re.search(r"Ran\s+\d+\s+tests?", text) and re.search(r"(?:^|\n)OK(?:\n|$)", text))


def task_outputs_valid(task: str, out: Path, *, compare_reference: bool = True) -> bool:
    """Validate every declared output, including content against retained evidence."""
    try:
        outputs = declared_outputs(task)
    except (ValueError, OSError, json.JSONDecodeError):
        return False
    if not outputs:
        return False
    if task == "tests":
        return _tests_log_valid(out / "tests.log")
    reference_root = ROOT / "results"
    for relative in outputs:
        candidate = out / relative
        if not candidate.is_file():
            return False
        if compare_reference:
            reference = reference_root / relative
            if not reference.is_file() or candidate.read_bytes() != reference.read_bytes():
                return False
    return True


def dependencies_valid(task: str, out: Path) -> bool:
    return all(task_outputs_valid(dependency, out) for dependency in task_dependencies(task))


def task_ready_to_skip(task: str, out: Path, records: list[dict]) -> bool:
    successful_exit = any(record.get("task") == task and record.get("exit_code") == 0 for record in records)
    return successful_exit and task_outputs_valid(task, out) and dependencies_valid(task, out)


def build_tasks(requested: list[str], sizes: list[int]) -> list[tuple[str, list[str]]]:
    tasks: list[tuple[str, list[str]]] = []
    for task in requested:
        if task == "tests":
            tasks.append(("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]))
        elif task == "report":
            tasks.append(("report", [sys.executable, "report.py", "--results", "{out}", "--out", "{out}"]))
        elif task == "joint":
            tasks.append(("joint", [sys.executable, "-m", "src.joint_benchmark", "--out", "{out}", "--part", "all"]))
        elif task == "joint-replay":
            tasks.append(("joint-replay", [sys.executable, "replay_joint.py", "--results", "{out}", "--report", "{out}/joint-replay.json"]))
        elif task == "verify":
            tasks.append(("verify", [sys.executable, "verify.py", "--results", "{out}", "--report", "{out}/independent-verification.json"]))
        elif task == "populations":
            for n in sizes:
                tasks.append((f"population-{n}", [sys.executable, "-m", "src.experiment", "populations", "--n", str(n), "--out", "{out}"]))
        else:
            tasks.append((task, [sys.executable, "-m", "src.experiment", task, "--out", "{out}"]))
    return tasks


def _expand_command(command: list[str], out: Path) -> list[str]:
    return [part.replace("{out}", str(out)) for part in command]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--tasks", nargs="+", default=DEFAULT_TASKS,
        choices=["tests", "pilot", "populations", "horn", "family", "verify", "report", "joint", "joint-replay"],
    )
    parser.add_argument("--sizes", nargs="+", type=int, default=list(range(1, 8)))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    if out == ROOT or out == ROOT / "results" or out.is_relative_to(ROOT / "inputs") or out.is_relative_to(ROOT / "src"):
        parser.error("choose a fresh reproduction output directory")
    if any(n < 1 or n > 7 for n in args.sizes):
        parser.error("sizes must be in 1..7")
    if out.exists() and not out.is_dir():
        parser.error("output must be a directory")
    if out.exists() and any(out.iterdir()) and not args.resume:
        parser.error("output is not empty; use a fresh directory or --resume")
    if out.exists() and any(out.iterdir()) and args.resume and not (out / "measurements.json").exists():
        parser.error("resume requires retained measurements")
    out.mkdir(parents=True, exist_ok=True)
    measurement = out / "measurements.json"
    if measurement.exists() and not args.resume:
        parser.error("output already has measurements; use a fresh directory or --resume")
    records = json.loads(measurement.read_text()) if measurement.exists() else []
    if type(records) is not list:
        parser.error("measurements must contain a JSON list")

    tasks = build_tasks(args.tasks, args.sizes)
    for name, template in tasks:
        if task_ready_to_skip(name, out, records):
            print(json.dumps({"task": name, "resume": "validated-skip"}), flush=True)
            continue
        command = _expand_command(template, out)
        started = time.monotonic()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        env = dict(
            os.environ,
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            PYTHONDONTWRITEBYTECODE="1",
        )
        with (out / f"{name}.log").open("w") as log:
            try:
                result = subprocess.run(
                    command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                    timeout=32, preexec_fn=child_limits,
                )
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                exit_code = 124
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record = {
            "task": name,
            "exit_code": exit_code,
            "wall_seconds": time.monotonic() - started,
            "cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
            "parent_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "child_peak_rss_kib_cumulative": after.ru_maxrss,
            "workers": 1,
            "address_space_limit_bytes": 536870912,
            "wall_timeout_seconds": 32,
        }
        records.append(record)
        measurement.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        if sum(float(item.get("cpu_seconds", 0)) for item in records) > 21600:
            raise SystemExit("campaign working allocation exhausted; repair reserve protected")
        if exit_code:
            raise SystemExit(f"{name} failed: inspect {out / (name + '.log')}")
        if not dependencies_valid(name, out):
            raise SystemExit(f"{name} completed but a declared dependency is missing or stale")
        if not task_outputs_valid(name, out):
            raise SystemExit(f"{name} exited successfully but its declared outputs are missing or stale")

    # Full-run equality covers deterministic outputs, not measurements or log text.
    expected = _expected_files()
    if expected:
        checked = []
        for relative in expected:
            candidate = out / relative
            if candidate.exists():
                if candidate.read_bytes() != (ROOT / "results" / relative).read_bytes():
                    raise SystemExit("deterministic mismatch: " + relative)
                checked.append(relative)
        full_request = set(args.tasks) == set(DEFAULT_TASKS) and set(args.sizes) == set(range(1, 8))
        if full_request and len(checked) != len(expected):
            raise SystemExit("full reproduction is missing deterministic output files")
        (out / "comparison.json").write_text(json.dumps({
            "matched_files": checked,
            "expected_files": len(expected),
            "all_expected_present": len(checked) == len(expected),
        }, indent=2) + "\n")
    print("All requested tasks completed. This is not a general-proof or novelty verdict.")


if __name__ == "__main__":
    main()
