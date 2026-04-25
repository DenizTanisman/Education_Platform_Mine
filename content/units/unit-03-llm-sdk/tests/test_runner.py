"""
M3 — Final test runner.

Tests the async parallel summarizer from summarizer.py.

Test groups (must match unit.yaml):
  - "SDK çağrısı"             — single call, message format, response parse
  - "Hata yönetimi"           — empty title, API error wrapping
  - "Async paralellik"        — order preservation, actual concurrency
  - "Dosyaya kaydetme"        — JSON schema, UTF-8, length mismatch

Mock strategy:
  We pass a fake AsyncOpenAI-shaped client to the student's functions.
  No real network traffic, no real API key, fully deterministic timing.
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock

# In platform sandbox, student code is at /workspace/code
sys.path.insert(0, '/workspace/code')

from harness_api import TestResult, TestGroup


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_tests() -> list[TestGroup]:
    groups = []

    g1 = TestGroup(name="SDK çağrısı")
    _test_sdk_call(g1)
    groups.append(g1)

    g2 = TestGroup(name="Hata yönetimi")
    _test_error_handling(g2)
    groups.append(g2)

    g3 = TestGroup(name="Async paralellik")
    _test_async_parallelism(g3)
    groups.append(g3)

    g4 = TestGroup(name="Dosyaya kaydetme")
    _test_save_summaries(g4)
    groups.append(g4)

    return groups


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_mock_client(content: str = "Bu bir özettir.", latency_ms: int = 0):
    """Build a MagicMock that mimics an AsyncOpenAI client.

    The shape:
        client.chat.completions.create(...) -> AsyncMock
            -> response.choices[0].message.content
    """
    client = MagicMock()

    async def _create(**kwargs):
        if latency_ms > 0:
            await asyncio.sleep(latency_ms / 1000)
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        # store the call for inspection
        return response

    # Use a real coroutine function so AsyncMock isn't needed
    client.chat.completions.create = _create
    client._call_log = []  # we don't track here — see _make_recording_client
    return client


def _make_recording_client(content: str = "özet", latency_ms: int = 0):
    """A mock client that logs all calls so we can inspect message format."""
    call_log = []

    async def _create(**kwargs):
        call_log.append(kwargs)
        if latency_ms > 0:
            await asyncio.sleep(latency_ms / 1000)
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]
        return response

    client = MagicMock()
    client.chat.completions.create = _create
    client._call_log = call_log
    return client


def _safe_import(g: TestGroup, test_id: str):
    try:
        import summarizer
        return summarizer
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"summarizer.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="Dosya adı summarizer.py olmalı; summarize_one, summarize_many, save_summaries, SummarizeError tanımlı mı?",
        ))
        return None


def _run_async(coro):
    """Run an async coroutine and return its result, isolated from any
    existing event loop."""
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Group 1 — SDK call shape
# ---------------------------------------------------------------------------

def _test_sdk_call(g: TestGroup) -> None:
    summarizer = _safe_import(g, "test_summarize_returns_string")
    if summarizer is None:
        return

    # 1.1: summarize_one returns a string with content from response
    client = _make_mock_client(content="Yapay zeka her geçen gün gelişiyor.")
    try:
        result = _run_async(summarizer.summarize_one("AI gelişimi", client))
        if result == "Yapay zeka her geçen gün gelişiyor.":
            g.add(TestResult(id="test_summarize_returns_string", status="passed"))
        else:
            g.add(TestResult(
                id="test_summarize_returns_string",
                status="failed",
                input='summarize_one("AI gelişimi", mock_client)',
                expected='"Yapay zeka her geçen gün gelişiyor."',
                actual=repr(result),
                hint="response.choices[0].message.content'ı döndürmelisin (strip ile)",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_summarize_returns_string",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.2: messages contain both system and user roles
    client = _make_recording_client(content="özet")
    try:
        _run_async(summarizer.summarize_one("Test başlığı", client))
        if not client._call_log:
            g.add(TestResult(
                id="test_messages_have_system_and_user",
                status="failed",
                input='summarize_one(...)',
                expected="API çağrısı yapıldı",
                actual="No call recorded",
                hint="client.chat.completions.create çağrılmalı",
            ))
        else:
            messages = client._call_log[0].get("messages", [])
            roles = {m.get("role") for m in messages}
            if "system" in roles and "user" in roles:
                g.add(TestResult(id="test_messages_have_system_and_user", status="passed"))
            else:
                g.add(TestResult(
                    id="test_messages_have_system_and_user",
                    status="failed",
                    input='summarize_one(...)',
                    expected='roles include {"system", "user"}',
                    actual=f"roles = {sorted(roles)}",
                    hint="messages listesine system + user mesajı koy",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_messages_have_system_and_user",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.3: model parameter is passed through
    client = _make_recording_client()
    try:
        _run_async(summarizer.summarize_one("X", client, model="gpt-4o-mini"))
        if client._call_log:
            kwargs = client._call_log[0]
            if kwargs.get("model") == "gpt-4o-mini":
                g.add(TestResult(id="test_model_param_passed", status="passed"))
            else:
                g.add(TestResult(
                    id="test_model_param_passed",
                    status="failed",
                    input='summarize_one(..., model="gpt-4o-mini")',
                    expected="kwargs include model='gpt-4o-mini'",
                    actual=f"model = {kwargs.get('model')!r}",
                    hint="model parametresini chat.completions.create'e geç",
                ))
        else:
            g.add(TestResult(
                id="test_model_param_passed",
                status="errored",
                detail="No API call was recorded",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_model_param_passed",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — Error handling
# ---------------------------------------------------------------------------

def _test_error_handling(g: TestGroup) -> None:
    summarizer = _safe_import(g, "test_empty_title_rejected")
    if summarizer is None:
        return

    # 2.1: empty title raises ValueError before API call
    client = _make_recording_client()
    try:
        _run_async(summarizer.summarize_one("", client))
        g.add(TestResult(
            id="test_empty_title_rejected",
            status="failed",
            input='summarize_one("", client)',
            expected="ValueError",
            actual="No exception",
            hint="Boş veya whitespace title için ValueError fırlat (API çağrısı YAPMA)",
        ))
    except ValueError:
        # Bonus: verify no API call was made
        if not client._call_log:
            g.add(TestResult(id="test_empty_title_rejected", status="passed"))
        else:
            g.add(TestResult(
                id="test_empty_title_rejected",
                status="failed",
                input='summarize_one("", client)',
                expected="ValueError BEFORE any API call",
                actual=f"ValueError raised but {len(client._call_log)} API calls happened",
                hint="title kontrolünü create() çağrısından ÖNCE yap",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_empty_title_rejected",
            status="failed",
            input='summarize_one("", client)',
            expected="ValueError",
            actual=f"{e.__class__.__name__}: {e}",
        ))

    # 2.2: API raises -> SummarizeError wraps it
    bad_client = MagicMock()
    async def _boom(**kw):
        raise RuntimeError("rate limit exceeded")
    bad_client.chat.completions.create = _boom
    try:
        _run_async(summarizer.summarize_one("Test", bad_client))
        g.add(TestResult(
            id="test_api_error_wrapped",
            status="failed",
            input='summarize_one with API raising RuntimeError',
            expected="SummarizeError (wrapping the RuntimeError)",
            actual="No exception",
            hint="API çağrısını try/except ile sarmalı, SummarizeError fırlatmalı",
        ))
    except summarizer.SummarizeError:
        g.add(TestResult(id="test_api_error_wrapped", status="passed"))
    except RuntimeError:
        g.add(TestResult(
            id="test_api_error_wrapped",
            status="failed",
            input='summarize_one with API raising RuntimeError',
            expected="SummarizeError (wrapping)",
            actual="RuntimeError raised raw (not wrapped)",
            hint="try/except ile yakala, raise SummarizeError(...) from e ile sar",
        ))
    except Exception as e:
        g.add(TestResult(
            id="test_api_error_wrapped",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.3: None content raises SummarizeError (not AttributeError)
    null_client = MagicMock()
    async def _null(**kw):
        msg = MagicMock(); msg.content = None
        choice = MagicMock(); choice.message = msg
        resp = MagicMock(); resp.choices = [choice]
        return resp
    null_client.chat.completions.create = _null
    try:
        _run_async(summarizer.summarize_one("Test", null_client))
        g.add(TestResult(
            id="test_none_content_handled",
            status="failed",
            input='API returns choices[0].message.content = None',
            expected="SummarizeError",
            actual="No exception (returned None or empty?)",
            hint="content None ise SummarizeError fırlat — None.strip() AttributeError'a yol açar",
        ))
    except summarizer.SummarizeError:
        g.add(TestResult(id="test_none_content_handled", status="passed"))
    except AttributeError:
        g.add(TestResult(
            id="test_none_content_handled",
            status="failed",
            input='API returns content=None',
            expected="SummarizeError",
            actual="AttributeError (None.strip() called)",
            hint="content kontrolü ekle: if content is None: raise SummarizeError(...)",
        ))
    except Exception as e:
        g.add(TestResult(
            id="test_none_content_handled",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Async parallelism
# ---------------------------------------------------------------------------

def _test_async_parallelism(g: TestGroup) -> None:
    summarizer = _safe_import(g, "test_order_preserved")
    if summarizer is None:
        return

    # 3.1: Order is preserved — summaries[i] corresponds to titles[i]
    # We make the mock return the title itself so we can match positions.
    client = MagicMock()
    async def _echo(**kwargs):
        # extract the user message (last in the list)
        title = kwargs["messages"][-1]["content"]
        msg = MagicMock(); msg.content = f"echo:{title}"
        choice = MagicMock(); choice.message = msg
        resp = MagicMock(); resp.choices = [choice]
        return resp
    client.chat.completions.create = _echo

    titles = [f"Başlık-{i}" for i in range(8)]
    try:
        results = _run_async(summarizer.summarize_many(titles, client, max_concurrency=4))
        # Each result should mention its title's index. Pull the digit.
        order_correct = all(
            f"-{i}" in results[i] for i in range(len(titles))
        )
        if order_correct and len(results) == 8:
            g.add(TestResult(id="test_order_preserved", status="passed"))
        else:
            g.add(TestResult(
                id="test_order_preserved",
                status="failed",
                input='summarize_many(8 titles, max_concurrency=4)',
                expected="results in same order as input titles",
                actual=f"len={len(results)}, mismatched order",
                hint="asyncio.gather sırayı korur; sonuçları sırayla döndürmen yeterli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_order_preserved",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.2: Actually parallel (10 calls @ 100ms each, max_concurrency=10 -> < 500ms)
    client = _make_mock_client(content="özet", latency_ms=100)
    titles = [f"t{i}" for i in range(10)]
    try:
        t0 = time.perf_counter()
        _run_async(summarizer.summarize_many(titles, client, max_concurrency=10))
        elapsed = time.perf_counter() - t0
        # Sequential would be ~1000ms, parallel should be ~100-300ms
        if elapsed < 0.5:
            g.add(TestResult(id="test_actually_parallel", status="passed"))
        else:
            g.add(TestResult(
                id="test_actually_parallel",
                status="failed",
                input='10 calls × 100ms each, max_concurrency=10',
                expected="elapsed < 500ms (parallel)",
                actual=f"{elapsed*1000:.0f}ms (sequential?)",
                hint="asyncio.gather ile tüm task'ları aynı anda başlat — for döngüsünde await kullanma",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_actually_parallel",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.3: Concurrency limit is respected (max_concurrency=2 -> ~500ms for 10x100ms)
    client = _make_mock_client(content="özet", latency_ms=100)
    titles = [f"t{i}" for i in range(10)]
    try:
        t0 = time.perf_counter()
        _run_async(summarizer.summarize_many(titles, client, max_concurrency=2))
        elapsed = time.perf_counter() - t0
        # 10 calls / 2 concurrent = 5 batches × 100ms = ~500ms (with overhead, < 800ms)
        # Way less than sequential (1000ms), way more than fully parallel (~150ms)
        if 0.4 <= elapsed <= 0.9:
            g.add(TestResult(id="test_concurrency_limit_respected", status="passed"))
        else:
            g.add(TestResult(
                id="test_concurrency_limit_respected",
                status="failed",
                input='10 calls × 100ms, max_concurrency=2',
                expected="elapsed in [400ms, 900ms] range",
                actual=f"{elapsed*1000:.0f}ms",
                hint="asyncio.Semaphore(max_concurrency) kullan, yoksa limit yok demek",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_concurrency_limit_respected",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 4 — Save summaries
# ---------------------------------------------------------------------------

def _test_save_summaries(g: TestGroup) -> None:
    summarizer = _safe_import(g, "test_save_creates_json_array")
    if summarizer is None:
        return

    # 4.1: Saved file is a JSON array of objects with title + summary
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        summarizer.save_summaries(["a", "b"], ["x", "y"], path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if (
            isinstance(data, list)
            and len(data) == 2
            and all(isinstance(d, dict) for d in data)
            and {"title", "summary"} <= set(data[0].keys())
        ):
            g.add(TestResult(id="test_save_creates_json_array", status="passed"))
        else:
            g.add(TestResult(
                id="test_save_creates_json_array",
                status="failed",
                input='save_summaries(["a","b"], ["x","y"], path)',
                expected='JSON array with {title, summary} objects',
                actual=repr(data)[:120],
                hint="Her başlığı kendi özetiyle eşle, [{'title':..., 'summary':...}, ...] formatında",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_save_creates_json_array",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.2: UTF-8 preserved
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        summarizer.save_summaries(
            ["İstanbul ve şehir"],
            ["Türkiye'nin en büyük şehri."],
            path,
        )
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "İstanbul" in content and "Türkiye" in content:
            g.add(TestResult(id="test_save_unicode_preserved", status="passed"))
        else:
            g.add(TestResult(
                id="test_save_unicode_preserved",
                status="failed",
                input='save_summaries with Turkish characters',
                expected="literal İstanbul / Türkiye in file",
                actual="\\u escaped",
                hint="json.dump(..., ensure_ascii=False)",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_save_unicode_preserved",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.3: Length mismatch raises
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        summarizer.save_summaries(["a", "b", "c"], ["x", "y"], path)  # 3 vs 2
        g.add(TestResult(
            id="test_save_length_mismatch_raises",
            status="failed",
            input='save_summaries with 3 titles but 2 summaries',
            expected="ValueError",
            actual="No exception",
            hint="len(titles) != len(summaries) durumunda ValueError fırlat",
        ))
    except ValueError:
        g.add(TestResult(id="test_save_length_mismatch_raises", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_save_length_mismatch_raises",
            status="failed",
            input='save_summaries(3 titles, 2 summaries)',
            expected="ValueError",
            actual=f"{e.__class__.__name__}: {e}",
        ))
