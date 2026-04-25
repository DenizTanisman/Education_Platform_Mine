"""Sandbox harness — runs a unit's test_runner.py and emits the JSON report
defined in 02_CONTENT_CONTRACT.md §3 to stdout (or --out path).

Expected workspace layout at runtime (inside the sandbox container):

    /workspace/harness.py        <- this file, baked into the image
    /workspace/harness_api.py    <- TestResult/TestGroup/run_test
    /workspace/tests/test_runner.py   <- bind-mounted from unit content
    /workspace/code/...          <- bind-mounted student submission

Design notes:
  * Every exit path produces a well-formed JSON document. If the harness
    itself cannot load or run test_runner (file missing, SyntaxError, crash
    inside run_tests), we synthesize a single-test 'errored' report so the
    runner can parse the same shape in every case.
  * Outer timeout wraps the whole run_tests() call — per-test timeout lives
    in harness_api.run_test() and is optional for test authors.
  * Always exits 0 when JSON is emitted cleanly; non-zero only for argparse
    / IO failures that happen before we can form a report.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import signal
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List

_STATUS_KEYS = ("passed", "failed", "errored", "timeout")


class _OuterTimeout(Exception):
    pass


def _outer_alarm_handler(signum, frame):  # pragma: no cover - signal handler
    raise _OuterTimeout()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IAU sandbox harness")
    parser.add_argument(
        "--workspace",
        default="/workspace",
        help="Root containing harness_api.py, tests/, and code/",
    )
    parser.add_argument(
        "--out",
        default="-",
        help="Output path for the JSON report; '-' for stdout",
    )
    parser.add_argument(
        "--outer-timeout-s",
        type=int,
        default=60,
        help="Wall-clock budget for the whole run_tests() invocation",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve()
    code_dir = workspace / "code"
    test_runner_path = workspace / "tests" / "test_runner.py"

    # Make harness_api (colocated with this file) and student code importable.
    # Insert at front so we beat any stdlib shadowing.
    sys.path.insert(0, str(workspace))
    sys.path.insert(0, str(code_dir))

    started = time.monotonic()
    try:
        report = _run(test_runner_path, args.outer_timeout_s, started)
    except Exception as exc:  # belt-and-suspenders: never crash without JSON
        report = _harness_error_report(exc, started)

    _write_report(args.out, report)
    return 0


def _run(test_runner_path: Path, outer_timeout_s: int, started: float) -> Dict[str, Any]:
    if not test_runner_path.is_file():
        raise FileNotFoundError(f"test_runner.py not found at {test_runner_path}")

    spec = importlib.util.spec_from_file_location("test_runner", str(test_runner_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build import spec for {test_runner_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # top-level failure in test_runner.py
        raise RuntimeError(f"test_runner.py failed to import: {exc}") from exc

    run_tests = getattr(module, "run_tests", None)
    if not callable(run_tests):
        raise AttributeError("test_runner.run_tests() callable is required")

    prev_handler = signal.signal(signal.SIGALRM, _outer_alarm_handler)
    signal.alarm(outer_timeout_s)
    try:
        groups = run_tests()
    except _OuterTimeout as exc:
        raise TimeoutError(
            f"run_tests() exceeded outer timeout of {outer_timeout_s}s"
        ) from exc
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)

    if not isinstance(groups, list):
        raise TypeError(
            f"run_tests() must return list[TestGroup], got {type(groups).__name__}"
        )

    return _build_report(groups, started)


def _build_report(groups: List[Any], started: float) -> Dict[str, Any]:
    groups_out: List[Dict[str, Any]] = []
    totals = {"total": 0, "passed": 0, "failed": 0, "errored": 0, "timeout": 0}

    for g in groups:
        tests_out: List[Dict[str, Any]] = []
        g_total = 0
        g_passed = 0
        for t in getattr(g, "tests", []):
            tests_out.append(_test_to_dict(t))
            status = getattr(t, "status", None)
            g_total += 1
            totals["total"] += 1
            if status in _STATUS_KEYS:
                totals[status] += 1
            if status == "passed":
                g_passed += 1
        groups_out.append(
            {
                "name": getattr(g, "name", "<unnamed>"),
                "weight": getattr(g, "weight", 1),
                "passed": g_passed,
                "total": g_total,
                "tests": tests_out,
            }
        )

    verdict = (
        "passed"
        if totals["total"] > 0 and totals["passed"] == totals["total"]
        else "failed"
    )
    runtime_ms = int((time.monotonic() - started) * 1000)
    return {
        "summary": {**totals, "runtime_ms": runtime_ms, "verdict": verdict},
        "groups": groups_out,
    }


def _test_to_dict(t: Any) -> Dict[str, Any]:
    if is_dataclass(t):
        raw = asdict(t)
    else:
        raw = dict(getattr(t, "__dict__", {}))
    return {k: v for k, v in raw.items() if v is not None}


def _harness_error_report(exc: Exception, started: float) -> Dict[str, Any]:
    runtime_ms = int((time.monotonic() - started) * 1000)
    return {
        "summary": {
            "total": 1,
            "passed": 0,
            "failed": 0,
            "errored": 1,
            "timeout": 0,
            "runtime_ms": runtime_ms,
            "verdict": "failed",
        },
        "groups": [
            {
                "name": "harness",
                "weight": 1,
                "passed": 0,
                "total": 1,
                "tests": [
                    {
                        "id": "harness_load",
                        "status": "errored",
                        "detail": f"{type(exc).__name__}: {exc}",
                    }
                ],
            }
        ],
    }


def _write_report(out: str, report: Dict[str, Any]) -> None:
    payload = json.dumps(report) + "\n"
    if out == "-":
        sys.stdout.write(payload)
        sys.stdout.flush()
    else:
        Path(out).write_text(payload)


if __name__ == "__main__":
    sys.exit(main())
