"""
M2 — Final test runner.

Tests the resilient HTTP fetcher from fetcher.py.

Test groups (must match unit.yaml):
  - "Başarılı istek"          — happy path with mocked 200 response
  - "Hata yönetimi"           — 404 fail-fast, retry exhaustion, JSON decode
  - "Retry davranışı"         — 500 then 200, backoff timing, attempt count
  - "Dosyaya kaydetme"        — JSON output format, UTF-8, indent

Mock strategy:
  We patch requests.Session.get on the student's module so no real network
  traffic occurs. This is identical to how M3+ will mock OpenAI clients.
"""

import json
import os
import sys
import tempfile
import time
from unittest.mock import patch, MagicMock

# In platform sandbox, student code is at /workspace/code
sys.path.insert(0, '/workspace/code')

from harness_api import TestResult, TestGroup


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_tests() -> list[TestGroup]:
    groups = []

    g1 = TestGroup(name="Başarılı istek")
    _test_happy_path(g1)
    groups.append(g1)

    g2 = TestGroup(name="Hata yönetimi")
    _test_error_handling(g2)
    groups.append(g2)

    g3 = TestGroup(name="Retry davranışı")
    _test_retry_behaviour(g3)
    groups.append(g3)

    g4 = TestGroup(name="Dosyaya kaydetme")
    _test_save_to_json(g4)
    groups.append(g4)

    return groups


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, json_data=None, text="", reason=""):
    """Build a mock requests.Response object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.reason = reason or _default_reason(status_code)
    resp.text = text

    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    if 400 <= status_code:
        # raise_for_status raises HTTPError for 4xx/5xx
        import requests
        resp.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} {resp.reason}"
        )
    else:
        resp.raise_for_status = MagicMock()

    return resp


def _default_reason(code: int) -> str:
    return {
        200: "OK", 404: "Not Found", 429: "Too Many Requests",
        500: "Internal Server Error", 502: "Bad Gateway",
        503: "Service Unavailable", 504: "Gateway Timeout",
    }.get(code, "")


def _safe_import(g: TestGroup, test_id: str):
    try:
        import fetcher
        return fetcher
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"fetcher.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="solution dosyası fetcher.py olmalı; fetch_with_retry, save_to_json, FetchError tanımlı mı?",
        ))
        return None


def _patched_session(fetcher_module, get_side_effect):
    """Return a context manager that patches requests.Session in fetcher's namespace.

    get_side_effect can be either a single Response (returned every call) or
    a list (returned in order, like a script).
    """
    mock_session = MagicMock()
    if isinstance(get_side_effect, list):
        mock_session.get.side_effect = get_side_effect
    else:
        mock_session.get.return_value = get_side_effect

    # Patch where requests.Session is looked up — inside fetcher's namespace
    return patch.object(fetcher_module.requests, "Session", return_value=mock_session)


# ---------------------------------------------------------------------------
# Group 1 — Happy path
# ---------------------------------------------------------------------------

def _test_happy_path(g: TestGroup) -> None:
    fetcher = _safe_import(g, "test_fetch_returns_dict")
    if fetcher is None:
        return

    # 1.1: 200 OK with dict body
    resp = _make_response(200, json_data={"name": "Turkey", "capital": "Ankara"})
    try:
        with _patched_session(fetcher, resp):
            result = fetcher.fetch_with_retry(
                "http://example.com/api", backoff_base=0
            )
        if result == {"name": "Turkey", "capital": "Ankara"}:
            g.add(TestResult(id="test_fetch_returns_dict", status="passed"))
        else:
            g.add(TestResult(
                id="test_fetch_returns_dict",
                status="failed",
                input='fetch_with_retry(url) with mocked 200 response',
                expected='{"name": "Turkey", "capital": "Ankara"}',
                actual=repr(result),
                hint="response.json() çıktısını döndürmelisin",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_fetch_returns_dict",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.2: 200 OK with list body (REST APIs often return arrays)
    resp = _make_response(200, json_data=[{"id": 1}, {"id": 2}])
    try:
        with _patched_session(fetcher, resp):
            result = fetcher.fetch_with_retry("http://x", backoff_base=0)
        if result == [{"id": 1}, {"id": 2}]:
            g.add(TestResult(id="test_fetch_returns_list", status="passed"))
        else:
            g.add(TestResult(
                id="test_fetch_returns_list",
                status="failed",
                input='fetch_with_retry(url) with list response',
                expected='[{"id": 1}, {"id": 2}]',
                actual=repr(result),
                hint="JSON dizi de geçerli — return type list veya dict olmalı",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_fetch_returns_list",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.3: Empty URL rejected before any HTTP call
    try:
        fetcher.fetch_with_retry("")
        g.add(TestResult(
            id="test_fetch_empty_url_rejected",
            status="failed",
            input='fetch_with_retry("")',
            expected="ValueError",
            actual="No exception",
            hint="Boş URL'i HTTP çağrısı yapmadan ValueError ile reddet",
        ))
    except ValueError:
        g.add(TestResult(id="test_fetch_empty_url_rejected", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_fetch_empty_url_rejected",
            status="failed",
            input='fetch_with_retry("")',
            expected="ValueError",
            actual=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — Error handling
# ---------------------------------------------------------------------------

def _test_error_handling(g: TestGroup) -> None:
    fetcher = _safe_import(g, "test_404_raises_immediately")
    if fetcher is None:
        return

    # 2.1: 404 should raise FetchError without retrying
    resp = _make_response(404, text="not found")
    try:
        with _patched_session(fetcher, resp) as mock_sess:
            try:
                fetcher.fetch_with_retry("http://x", max_retries=3, backoff_base=0)
                g.add(TestResult(
                    id="test_404_raises_immediately",
                    status="failed",
                    input='fetch_with_retry with mocked 404',
                    expected="FetchError",
                    actual="No exception",
                    hint="4xx hatalarında (429 hariç) retry yapma, FetchError fırlat",
                ))
            except fetcher.FetchError:
                # Must have called get exactly once (no retries)
                # Note: mock_sess returns the patched Session class, not an instance
                instance = mock_sess.return_value
                call_count = instance.get.call_count
                if call_count == 1:
                    g.add(TestResult(id="test_404_raises_immediately", status="passed"))
                else:
                    g.add(TestResult(
                        id="test_404_raises_immediately",
                        status="failed",
                        input='fetch_with_retry with mocked 404',
                        expected="exactly 1 HTTP call (no retry)",
                        actual=f"{call_count} calls",
                        hint="4xx hatasında retry döngüsünden çık, bir kez dene yeter",
                    ))
    except Exception as e:
        g.add(TestResult(
            id="test_404_raises_immediately",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.2: All 500s exhaust retries -> FetchError
    responses = [_make_response(500) for _ in range(5)]  # plenty
    try:
        with _patched_session(fetcher, responses) as mock_sess:
            try:
                fetcher.fetch_with_retry(
                    "http://x", max_retries=3, backoff_base=0
                )
                g.add(TestResult(
                    id="test_500_exhausts_retries",
                    status="failed",
                    input='3x mocked 500 response',
                    expected="FetchError after retries",
                    actual="No exception",
                    hint="Tüm denemeler başarısız olunca FetchError fırlat",
                ))
            except fetcher.FetchError:
                instance = mock_sess.return_value
                call_count = instance.get.call_count
                if call_count == 3:
                    g.add(TestResult(id="test_500_exhausts_retries", status="passed"))
                else:
                    g.add(TestResult(
                        id="test_500_exhausts_retries",
                        status="failed",
                        input='max_retries=3, all 500',
                        expected="exactly 3 HTTP calls",
                        actual=f"{call_count} calls",
                        hint="max_retries=N için tam N deneme yap",
                    ))
    except Exception as e:
        g.add(TestResult(
            id="test_500_exhausts_retries",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.3: Invalid JSON response -> FetchError
    bad_resp = _make_response(200)  # status 200 but json() raises JSONDecodeError
    try:
        with _patched_session(fetcher, bad_resp):
            try:
                fetcher.fetch_with_retry("http://x", backoff_base=0)
                g.add(TestResult(
                    id="test_invalid_json_raises",
                    status="failed",
                    input='200 OK but non-JSON body',
                    expected="FetchError",
                    actual="No exception",
                    hint="response.json() JSONDecodeError verirse FetchError'a sar",
                ))
            except fetcher.FetchError:
                g.add(TestResult(id="test_invalid_json_raises", status="passed"))
            except json.JSONDecodeError:
                g.add(TestResult(
                    id="test_invalid_json_raises",
                    status="failed",
                    input='200 OK but non-JSON body',
                    expected="FetchError (custom)",
                    actual="JSONDecodeError raw (not wrapped)",
                    hint="JSONDecodeError'ı try/except ile yakalayıp FetchError fırlat",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_invalid_json_raises",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Retry behaviour
# ---------------------------------------------------------------------------

def _test_retry_behaviour(g: TestGroup) -> None:
    fetcher = _safe_import(g, "test_retry_then_success")
    if fetcher is None:
        return

    # 3.1: 500 then 200 -> success on second try
    responses = [
        _make_response(500),
        _make_response(200, json_data={"ok": True}),
    ]
    try:
        with _patched_session(fetcher, responses) as mock_sess:
            result = fetcher.fetch_with_retry(
                "http://x", max_retries=3, backoff_base=0
            )
            instance = mock_sess.return_value
            call_count = instance.get.call_count
            if result == {"ok": True} and call_count == 2:
                g.add(TestResult(id="test_retry_then_success", status="passed"))
            else:
                g.add(TestResult(
                    id="test_retry_then_success",
                    status="failed",
                    input='500 then 200 sequence',
                    expected='{"ok": True} after 2 calls',
                    actual=f"result={result!r}, calls={call_count}",
                    hint="500 sonrası retry ederek tekrar dene; 200 gelince başarılı dön",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_retry_then_success",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.2: 503 (retryable) -> retried
    responses = [_make_response(503), _make_response(200, json_data={"ok": True})]
    try:
        with _patched_session(fetcher, responses) as mock_sess:
            try:
                result = fetcher.fetch_with_retry(
                    "http://x", max_retries=3, backoff_base=0
                )
                if result == {"ok": True}:
                    g.add(TestResult(id="test_503_is_retryable", status="passed"))
                else:
                    g.add(TestResult(
                        id="test_503_is_retryable",
                        status="failed",
                        input='503 then 200',
                        expected='{"ok": True} after retry',
                        actual=repr(result),
                        hint="503 (Service Unavailable) retryable kabul et",
                    ))
            except fetcher.FetchError:
                g.add(TestResult(
                    id="test_503_is_retryable",
                    status="failed",
                    input='503 then 200',
                    expected="successful retry",
                    actual="FetchError (503 not treated as retryable)",
                    hint="503 RETRYABLE_STATUS setine eklenmeli",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_503_is_retryable",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.3: Connection error then success
    import requests
    responses = [
        requests.exceptions.ConnectionError("DNS fail"),
        _make_response(200, json_data={"ok": True}),
    ]
    try:
        with _patched_session(fetcher, responses) as mock_sess:
            result = fetcher.fetch_with_retry(
                "http://x", max_retries=3, backoff_base=0
            )
            if result == {"ok": True}:
                g.add(TestResult(id="test_connection_error_retried", status="passed"))
            else:
                g.add(TestResult(
                    id="test_connection_error_retried",
                    status="failed",
                    input='ConnectionError then 200',
                    expected='{"ok": True} after retry',
                    actual=repr(result),
                    hint="ConnectionError yakala, retry et",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_connection_error_retried",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
            hint="ConnectionError'ı RequestException olarak yakala (parent class)",
        ))


# ---------------------------------------------------------------------------
# Group 4 — Save to JSON
# ---------------------------------------------------------------------------

def _test_save_to_json(g: TestGroup) -> None:
    fetcher = _safe_import(g, "test_save_creates_file")
    if fetcher is None:
        return

    # 4.1: save_to_json creates a file
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    try:
        fetcher.save_to_json({"name": "Turkey"}, path)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            g.add(TestResult(id="test_save_creates_file", status="passed"))
        else:
            g.add(TestResult(
                id="test_save_creates_file",
                status="failed",
                input='save_to_json({"name": "Turkey"}, path)',
                expected="non-empty file at path",
                actual="missing or empty",
                hint="open(path, 'w') ile dosyayı yazmayı unutma",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_save_creates_file",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.2: Saved file is valid JSON with correct content
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    data = {"isim": "Türkiye", "başkent": "Ankara", "nüfus": 85000000}
    try:
        fetcher.save_to_json(data, path)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if loaded == data:
            g.add(TestResult(id="test_save_round_trip", status="passed"))
        else:
            g.add(TestResult(
                id="test_save_round_trip",
                status="failed",
                input='save then read back',
                expected=repr(data),
                actual=repr(loaded),
                hint="json.dump kullan, encoding='utf-8' geç",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_save_round_trip",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.3: Turkish characters preserved (not \\u escapes)
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    try:
        fetcher.save_to_json({"şehir": "İstanbul"}, path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "İstanbul" in content and "şehir" in content:
            g.add(TestResult(id="test_save_unicode_preserved", status="passed"))
        else:
            g.add(TestResult(
                id="test_save_unicode_preserved",
                status="failed",
                input='save {"şehir": "İstanbul"}, read raw text',
                expected="literal İstanbul / şehir in file",
                actual="\\u escaped (ensure_ascii=True default)",
                hint="json.dump çağrısına ensure_ascii=False ekle",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_save_unicode_preserved",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))
