"""Example: a submission that attempts three escape vectors. The sandbox
must contain all of them — each call should raise rather than succeed.
"""
from harness_api import TestGroup, TestResult


def run_tests():
    g = TestGroup(name="security")

    # Attempt 1: outbound network (--network=none should block DNS)
    try:
        from solution import try_network
        try_network()
        g.add(TestResult(id="test_network_blocked", status="failed",
                         expected="network call raises",
                         actual="call succeeded — sandbox is leaking!"))
    except Exception as e:
        g.add(TestResult(id="test_network_blocked", status="passed",
                         detail=f"contained: {type(e).__name__}"))

    # Attempt 2: write to read-only rootfs (--read-only should block)
    try:
        from solution import try_write_etc
        try_write_etc()
        g.add(TestResult(id="test_readonly_blocked", status="failed",
                         expected="OSError on /etc write",
                         actual="write succeeded — sandbox is leaking!"))
    except Exception as e:
        g.add(TestResult(id="test_readonly_blocked", status="passed",
                         detail=f"contained: {type(e).__name__}"))

    # Attempt 3: ptrace (seccomp should block)
    try:
        from solution import try_ptrace
        rv = try_ptrace()
        # rv == -1 means seccomp/cap-drop produced EPERM; success would be 0
        if rv == -1:
            g.add(TestResult(id="test_ptrace_blocked", status="passed",
                             detail="ptrace returned -1 (denied)"))
        else:
            g.add(TestResult(id="test_ptrace_blocked", status="failed",
                             expected="rv == -1",
                             actual=f"rv == {rv}"))
    except Exception as e:
        g.add(TestResult(id="test_ptrace_blocked", status="passed",
                         detail=f"contained: {type(e).__name__}"))

    return [g]
