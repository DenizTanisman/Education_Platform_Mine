"""Shared pytest helpers for harness tests.

Builds a temp workspace mirroring the sandbox layout:

    <tmp>/harness.py
    <tmp>/harness_api.py
    <tmp>/tests/test_runner.py   (written per-test)
    <tmp>/code/...               (written per-test)

and runs the real harness as a subprocess — same code path as production,
just on the host Python instead of inside the docker container.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_SRC = REPO_ROOT / "infra" / "sandbox" / "harness.py"
HARNESS_API_SRC = REPO_ROOT / "infra" / "sandbox" / "harness_api.py"


@dataclass
class HarnessRun:
    returncode: int
    stdout: str
    stderr: str
    report: Optional[Dict[str, Any]]


@dataclass
class Workspace:
    root: Path

    @property
    def tests_dir(self) -> Path:
        d = self.root / "tests"
        d.mkdir(exist_ok=True)
        return d

    @property
    def code_dir(self) -> Path:
        d = self.root / "code"
        d.mkdir(exist_ok=True)
        return d

    def write_test_runner(self, src: str) -> Path:
        path = self.tests_dir / "test_runner.py"
        path.write_text(src)
        return path

    def write_code(self, relpath: str, src: str) -> Path:
        path = self.code_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(src)
        return path

    def run_harness(self, *, outer_timeout_s: int = 30) -> HarnessRun:
        proc = subprocess.run(
            [
                sys.executable,
                str(self.root / "harness.py"),
                "--workspace",
                str(self.root),
                "--outer-timeout-s",
                str(outer_timeout_s),
            ],
            capture_output=True,
            text=True,
            timeout=outer_timeout_s + 10,
        )
        report: Optional[Dict[str, Any]]
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            report = None
        return HarnessRun(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            report=report,
        )


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Fresh workspace with harness files copied in. Tests/code written per-test."""
    shutil.copy(HARNESS_SRC, tmp_path / "harness.py")
    shutil.copy(HARNESS_API_SRC, tmp_path / "harness_api.py")
    return Workspace(root=tmp_path)
