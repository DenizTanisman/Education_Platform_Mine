"""Example: a submission that should PASS all checks."""
from harness_api import TestGroup, TestResult


def run_tests():
    g = TestGroup(name="greeting")
    try:
        from solution import greet
        result = greet("Deniz")
        if result == "Hello, Deniz!":
            g.add(TestResult(id="test_greet_basic", status="passed"))
        else:
            g.add(TestResult(
                id="test_greet_basic",
                status="failed",
                expected='"Hello, Deniz!"',
                actual=repr(result),
                input='greet("Deniz")',
            ))
    except Exception as e:
        g.add(TestResult(id="test_greet_basic", status="errored", detail=str(e)))
    return [g]
