"""Example: a submission that should FAIL with a clean expected/actual diff."""
from harness_api import TestGroup, TestResult


def run_tests():
    g = TestGroup(name="greeting")
    from solution import greet
    actual = greet("Deniz")
    g.add(TestResult(
        id="test_greet_basic",
        status="failed" if actual != "Hello, Deniz!" else "passed",
        expected='"Hello, Deniz!"',
        actual=repr(actual),
        input='greet("Deniz")',
        hint="f-string ile name'i interpolate et",
    ))
    return [g]
