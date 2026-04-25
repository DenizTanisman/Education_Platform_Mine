"""
M0 — Final test runner.

Tests three functions from solution.py:
  - selamla(isim) -> str
  - topla(sayilar) -> int
  - cift_say(sayilar) -> int

Each function is tested by a TestGroup whose name matches unit.yaml's
test_groups[*].name exactly.
"""

import sys
import time

# In the platform sandbox, student code is mounted at /workspace/code
# In the local harness, the same path is set up by the harness script
sys.path.insert(0, '/workspace/code')

from harness_api import TestResult, TestGroup


# ---------------------------------------------------------------------------
# Public entry point — harness calls this
# ---------------------------------------------------------------------------

def run_tests() -> list[TestGroup]:
    """Build and return the list of test groups for this module."""
    groups = []

    g1 = TestGroup(name="selamla fonksiyonu")
    _test_selamla(g1)
    groups.append(g1)

    g2 = TestGroup(name="topla fonksiyonu")
    _test_topla(g2)
    groups.append(g2)

    g3 = TestGroup(name="cift_say fonksiyonu")
    _test_cift_say(g3)
    groups.append(g3)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check(group, test_id, call_repr, expected, actual, hint=None):
    """Compare expected vs actual and add the appropriate TestResult."""
    if expected == actual:
        group.add(TestResult(id=test_id, status="passed"))
    else:
        group.add(TestResult(
            id=test_id,
            status="failed",
            input=call_repr,
            expected=repr(expected),
            actual=repr(actual),
            hint=hint,
        ))


def _safe_import(group, test_id, import_stmt):
    """Try to import a name from solution. Record errored TestResult on fail."""
    try:
        # Execute import in a controlled namespace
        ns = {}
        exec(import_stmt, ns)
        return ns
    except Exception as e:
        group.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"solution.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="solution.py dosyasının var olduğundan ve fonksiyonun doğru isimde tanımlandığından emin ol",
        ))
        return None


# ---------------------------------------------------------------------------
# Group 1 — selamla
# ---------------------------------------------------------------------------

def _test_selamla(g: TestGroup) -> None:
    ns = _safe_import(g, "test_selamla_normal", "from solution import selamla")
    if ns is None:
        return
    selamla = ns["selamla"]

    # Test 1: Normal isim
    start = time.perf_counter()
    actual = selamla("Ayşe")
    rt = int((time.perf_counter() - start) * 1000)
    if actual == "Merhaba, Ayşe!":
        g.add(TestResult(id="test_selamla_normal", status="passed", runtime_ms=rt))
    else:
        g.add(TestResult(
            id="test_selamla_normal",
            status="failed",
            input='selamla("Ayşe")',
            expected='"Merhaba, Ayşe!"',
            actual=repr(actual),
            hint="f-string ile 'Merhaba, {isim}!' formatını kullan",
        ))

    # Test 2: Boş string
    actual = selamla("")
    if actual == "Merhaba!":
        g.add(TestResult(id="test_selamla_empty", status="passed"))
    else:
        g.add(TestResult(
            id="test_selamla_empty",
            status="failed",
            input='selamla("")',
            expected='"Merhaba!"',
            actual=repr(actual),
            hint="Boş string verilirse sade 'Merhaba!' dönmeli (köşe durumu)",
        ))

    # Test 3: Türkçe karakter (ğüşıöç)
    actual = selamla("Çağrı")
    if actual == "Merhaba, Çağrı!":
        g.add(TestResult(id="test_selamla_turkish_chars", status="passed"))
    else:
        g.add(TestResult(
            id="test_selamla_turkish_chars",
            status="failed",
            input='selamla("Çağrı")',
            expected='"Merhaba, Çağrı!"',
            actual=repr(actual),
            hint="UTF-8 karakterleri destekle, encode/decode gerekmez",
        ))


# ---------------------------------------------------------------------------
# Group 2 — topla
# ---------------------------------------------------------------------------

def _test_topla(g: TestGroup) -> None:
    ns = _safe_import(g, "test_topla_basic", "from solution import topla")
    if ns is None:
        return
    topla = ns["topla"]

    # Test 1: Pozitif sayılar
    actual = topla([1, 2, 3, 4, 5])
    _check(
        g, "test_topla_basic",
        "topla([1, 2, 3, 4, 5])",
        15, actual,
        hint="for döngüsüyle her elemanı toplama ekle",
    )

    # Test 2: Boş liste
    actual = topla([])
    _check(
        g, "test_topla_empty",
        "topla([])",
        0, actual,
        hint="Boş liste verilirse 0 dönmeli (toplama birim elemanı)",
    )

    # Test 3: Negatif sayılar dahil
    actual = topla([-3, -2, -1, 0, 1, 2, 3])
    _check(
        g, "test_topla_with_negatives",
        "topla([-3, -2, -1, 0, 1, 2, 3])",
        0, actual,
        hint="Negatif sayılar normal toplanır, özel kod gerekmez",
    )


# ---------------------------------------------------------------------------
# Group 3 — cift_say
# ---------------------------------------------------------------------------

def _test_cift_say(g: TestGroup) -> None:
    ns = _safe_import(g, "test_cift_say_basic", "from solution import cift_say")
    if ns is None:
        return
    cift_say = ns["cift_say"]

    # Test 1: Karışık sayılar
    actual = cift_say([1, 2, 3, 4, 5, 6])
    _check(
        g, "test_cift_say_basic",
        "cift_say([1, 2, 3, 4, 5, 6])",
        3, actual,
        hint="x % 2 == 0 olan sayıları say",
    )

    # Test 2: Boş liste
    actual = cift_say([])
    _check(
        g, "test_cift_say_empty",
        "cift_say([])",
        0, actual,
        hint="Boş liste -> 0 (saymak için bir şey yok)",
    )

    # Test 3: Sıfır ve negatifler (köşe durumu)
    actual = cift_say([0, -2, -1, -4, 7])
    _check(
        g, "test_cift_say_zero_and_negatives",
        "cift_say([0, -2, -1, -4, 7])",
        3, actual,
        hint="Sıfır çifttir, -2 ve -4 de çifttir; modulo işareti Python'da pozitif kalır",
    )
