"""End-to-end tests for infra/sandbox/harness.py.

Each test writes a synthetic test_runner.py (+ optional student code) into a
tmp workspace, runs harness.py as a subprocess, and asserts on the parsed
JSON report. Same binary behaviour as production — host Python instead of
sandbox container.
"""

from __future__ import annotations

import textwrap

from conftest import Workspace


# ---------------------------------------------------------------------------
# 1. Happy path: single passing test -> verdict = passed
# ---------------------------------------------------------------------------
def test_single_pass(workspace: Workspace):
    workspace.write_code(
        "solution.py",
        "def greet(name): return f'Hello, {name}!'\n",
    )
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, TestResult
            def run_tests():
                g = TestGroup(name="greeting")
                from solution import greet
                if greet("Deniz") == "Hello, Deniz!":
                    g.add(TestResult(id="test_greet", status="passed"))
                else:
                    g.add(TestResult(id="test_greet", status="failed"))
                return [g]
            """
        )
    )
    r = workspace.run_harness()
    assert r.returncode == 0, r.stderr
    s = r.report["summary"]
    assert s["total"] == 1
    assert s["passed"] == 1
    assert s["verdict"] == "passed"
    assert r.report["groups"][0]["name"] == "greeting"


# ---------------------------------------------------------------------------
# 2. Single failing test -> verdict = failed, expected/actual propagated
# ---------------------------------------------------------------------------
def test_single_fail_propagates_expected_actual(workspace: Workspace):
    workspace.write_code("solution.py", "def greet(n): return 'nope'\n")
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, TestResult
            def run_tests():
                from solution import greet
                actual = greet("Deniz")
                g = TestGroup(name="greeting")
                g.add(TestResult(
                    id="test_greet",
                    status="failed",
                    expected='"Hello, Deniz!"',
                    actual=repr(actual),
                    input='greet("Deniz")',
                    hint="f-string kullan",
                ))
                return [g]
            """
        )
    )
    r = workspace.run_harness()
    s = r.report["summary"]
    assert s["failed"] == 1 and s["passed"] == 0
    assert s["verdict"] == "failed"
    t = r.report["groups"][0]["tests"][0]
    assert t["expected"] == '"Hello, Deniz!"'
    assert t["actual"] == "'nope'"
    assert t["input"] == 'greet("Deniz")'
    assert t["hint"] == "f-string kullan"


# ---------------------------------------------------------------------------
# 3. Student code throws -> status errored, detail present
# ---------------------------------------------------------------------------
def test_student_code_exception_becomes_errored(workspace: Workspace):
    workspace.write_code("solution.py", "def greet(n): raise ValueError('boom')\n")
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, TestResult
            def run_tests():
                g = TestGroup(name="greeting")
                try:
                    from solution import greet
                    greet("x")
                    g.add(TestResult(id="test_greet", status="passed"))
                except Exception as e:
                    g.add(TestResult(id="test_greet", status="errored", detail=str(e)))
                return [g]
            """
        )
    )
    r = workspace.run_harness()
    s = r.report["summary"]
    assert s["errored"] == 1
    assert s["verdict"] == "failed"
    assert r.report["groups"][0]["tests"][0]["detail"] == "boom"


# ---------------------------------------------------------------------------
# 4. Per-test timeout via run_test() helper -> status timeout
# ---------------------------------------------------------------------------
def test_per_test_timeout_via_helper(workspace: Workspace):
    workspace.write_test_runner(
        textwrap.dedent(
            """
            import time
            from harness_api import TestGroup, run_test
            def run_tests():
                g = TestGroup(name="slow")
                run_test(g, "test_sleep_forever", lambda: time.sleep(5), timeout_s=1)
                return [g]
            """
        )
    )
    r = workspace.run_harness(outer_timeout_s=15)
    s = r.report["summary"]
    assert s["timeout"] == 1
    assert s["verdict"] == "failed"
    t = r.report["groups"][0]["tests"][0]
    assert t["status"] == "timeout"
    assert t["runtime_ms"] >= 900  # ~1s alarm


# ---------------------------------------------------------------------------
# 5. run_test helper maps AssertionError -> failed, with message in actual
# ---------------------------------------------------------------------------
def test_run_test_helper_maps_assertion_to_failed(workspace: Workspace):
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, run_test
            def run_tests():
                g = TestGroup(name="asserts")
                def check():
                    assert 1 == 2, "one != two"
                run_test(g, "test_assert", check, expected="1 == 2")
                return [g]
            """
        )
    )
    r = workspace.run_harness()
    t = r.report["groups"][0]["tests"][0]
    assert t["status"] == "failed"
    assert t["actual"] == "one != two"
    assert t["expected"] == "1 == 2"


# ---------------------------------------------------------------------------
# 6. Multiple groups with mixed results -> totals aggregated correctly
# ---------------------------------------------------------------------------
def test_multiple_groups_totals_aggregate(workspace: Workspace):
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, TestResult
            def run_tests():
                g1 = TestGroup(name="A", weight=1)
                g1.add(TestResult(id="a1", status="passed"))
                g1.add(TestResult(id="a2", status="passed"))
                g2 = TestGroup(name="B", weight=3)
                g2.add(TestResult(id="b1", status="failed"))
                g2.add(TestResult(id="b2", status="errored", detail="x"))
                g2.add(TestResult(id="b3", status="passed"))
                return [g1, g2]
            """
        )
    )
    r = workspace.run_harness()
    s = r.report["summary"]
    assert s["total"] == 5
    assert s["passed"] == 3
    assert s["failed"] == 1
    assert s["errored"] == 1
    assert s["verdict"] == "failed"
    groups = r.report["groups"]
    assert groups[0]["passed"] == 2 and groups[0]["total"] == 2
    assert groups[1]["passed"] == 1 and groups[1]["total"] == 3
    assert groups[1]["weight"] == 3


# ---------------------------------------------------------------------------
# 7. runtime_ms populated on summary and on run_test-produced tests
# ---------------------------------------------------------------------------
def test_runtime_ms_populated(workspace: Workspace):
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, run_test
            def run_tests():
                g = TestGroup(name="g")
                run_test(g, "t1", lambda: None)
                return [g]
            """
        )
    )
    r = workspace.run_harness()
    assert r.report["summary"]["runtime_ms"] >= 0
    assert r.report["groups"][0]["tests"][0]["runtime_ms"] >= 0


# ---------------------------------------------------------------------------
# 8. test_runner itself crashes at import -> synthetic harness error report
# ---------------------------------------------------------------------------
def test_test_runner_import_crash_synthesizes_error(workspace: Workspace):
    workspace.write_test_runner("raise RuntimeError('top-level boom')\n")
    r = workspace.run_harness()
    assert r.returncode == 0  # harness still emits JSON
    s = r.report["summary"]
    assert s["total"] == 1 and s["errored"] == 1
    assert s["verdict"] == "failed"
    g = r.report["groups"][0]
    assert g["name"] == "harness"
    assert g["tests"][0]["id"] == "harness_load"
    assert "top-level boom" in g["tests"][0]["detail"]


# ---------------------------------------------------------------------------
# 9. Missing tests/test_runner.py -> synthetic harness error report
# ---------------------------------------------------------------------------
def test_missing_test_runner_synthesizes_error(workspace: Workspace):
    # Note: do not create tests/test_runner.py
    r = workspace.run_harness()
    assert r.returncode == 0
    s = r.report["summary"]
    assert s["errored"] == 1
    g = r.report["groups"][0]
    assert g["name"] == "harness"
    assert "test_runner.py not found" in g["tests"][0]["detail"]


# ---------------------------------------------------------------------------
# 10. JSON shape matches 02_CONTENT_CONTRACT.md §3
# ---------------------------------------------------------------------------
def test_json_shape_matches_contract(workspace: Workspace):
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, TestResult
            def run_tests():
                g = TestGroup(name="shape")
                g.add(TestResult(id="t", status="passed"))
                return [g]
            """
        )
    )
    r = workspace.run_harness()
    assert set(r.report.keys()) == {"summary", "groups"}
    s = r.report["summary"]
    for k in ("total", "passed", "failed", "errored", "timeout",
             "runtime_ms", "verdict"):
        assert k in s, f"summary missing key: {k}"
    grp = r.report["groups"][0]
    for k in ("name", "weight", "passed", "total", "tests"):
        assert k in grp, f"group missing key: {k}"
    test = grp["tests"][0]
    assert set(test.keys()) == {"id", "status"}  # None fields stripped


# ---------------------------------------------------------------------------
# 11. None fields are stripped from JSON (keeps report compact)
# ---------------------------------------------------------------------------
def test_none_fields_stripped(workspace: Workspace):
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup, TestResult
            def run_tests():
                g = TestGroup(name="g")
                g.add(TestResult(id="t", status="passed"))  # all other fields None
                return [g]
            """
        )
    )
    r = workspace.run_harness()
    t = r.report["groups"][0]["tests"][0]
    assert "expected" not in t
    assert "actual" not in t
    assert "detail" not in t
    assert "runtime_ms" not in t  # None when built manually


# ---------------------------------------------------------------------------
# 12. run_tests returns wrong type -> synthetic harness error
# ---------------------------------------------------------------------------
def test_run_tests_bad_return_type(workspace: Workspace):
    workspace.write_test_runner("def run_tests(): return 42\n")
    r = workspace.run_harness()
    s = r.report["summary"]
    assert s["errored"] == 1
    assert r.report["groups"][0]["name"] == "harness"
    assert "list[TestGroup]" in r.report["groups"][0]["tests"][0]["detail"]


# ---------------------------------------------------------------------------
# 13. Verdict = passed iff every test passed (zero tests -> failed)
# ---------------------------------------------------------------------------
def test_verdict_rules(workspace: Workspace):
    workspace.write_test_runner(
        textwrap.dedent(
            """
            from harness_api import TestGroup
            def run_tests():
                return [TestGroup(name="empty")]
            """
        )
    )
    r = workspace.run_harness()
    # zero tests: verdict must not falsely be "passed"
    assert r.report["summary"]["verdict"] == "failed"
    assert r.report["summary"]["total"] == 0
