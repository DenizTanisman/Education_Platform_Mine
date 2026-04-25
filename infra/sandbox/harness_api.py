"""Public API consumed by every unit's `tests/test_runner.py`.

Two dataclasses and one helper — nothing else. Kept small on purpose so the
contract surface is readable in one screen and easy to pin in unit content.

See 02_CONTENT_CONTRACT.md §2.4 for the `test_runner.py` shape and §3 for the
JSON the harness emits. run_test enforces the per-test 2s wall-clock timeout
required by 01_BUILD_PLAN.md §2.3.
"""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

__all__ = ["TestResult", "TestGroup", "run_test"]

_VALID_STATUSES = ("passed", "failed", "errored", "timeout")


@dataclass
class TestResult:
    id: str
    status: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    input: Optional[str] = None
    hint: Optional[str] = None
    detail: Optional[str] = None
    runtime_ms: Optional[int] = None

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise ValueError(
                f"TestResult.status must be one of {_VALID_STATUSES}, got {self.status!r}"
            )


@dataclass
class TestGroup:
    name: str
    weight: int = 1
    tests: List[TestResult] = field(default_factory=list)

    def add(self, result: TestResult) -> None:
        self.tests.append(result)


class _TestTimeout(Exception):
    """Raised by SIGALRM handler when a single test exceeds its budget."""


def _alarm_handler(signum, frame):  # pragma: no cover - signal handler
    raise _TestTimeout()


def run_test(
    group: TestGroup,
    test_id: str,
    fn: Callable[[], Any],
    *,
    expected: Optional[str] = None,
    input: Optional[str] = None,
    hint: Optional[str] = None,
    timeout_s: int = 2,
) -> None:
    """Run fn() and append a TestResult to group based on the outcome.

    Outcome mapping:
      clean return            -> status="passed"
      AssertionError          -> status="failed", actual=str(e) if present
      any other Exception     -> status="errored", detail="<Type>: <msg>"
      fn exceeded timeout_s   -> status="timeout"

    Uses SIGALRM so the timeout is a real wall-clock kill, not cooperative.
    Only usable from the main thread (signal() requirement); the harness runs
    on the main thread, so that holds.
    """
    start = time.monotonic()
    prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout_s)
    status = "passed"
    actual: Optional[str] = None
    detail: Optional[str] = None
    try:
        fn()
    except _TestTimeout:
        status = "timeout"
    except AssertionError as e:
        status = "failed"
        msg = str(e)
        actual = msg if msg else None
    except Exception as e:
        status = "errored"
        detail = f"{type(e).__name__}: {e}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
    runtime_ms = int((time.monotonic() - start) * 1000)
    group.add(
        TestResult(
            id=test_id,
            status=status,
            runtime_ms=runtime_ms,
            expected=expected,
            actual=actual,
            input=input,
            hint=hint,
            detail=detail,
        )
    )
