"""
M4 — Final test runner.

Tests the structured review extractor from extractor.py.

Test groups (must match unit.yaml):
  - "Schema doğrulama"       — Pydantic class structure, field constraints
  - "LLM çağrısı"           — parse method, response_format, message format
  - "Hata yönetimi"          — empty text, API error wrapping, None parsed
  - "Dosyaya kaydetme"       — JSON schema, enum serialization, length mismatch
"""

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

# In platform sandbox, student code is at /workspace/code
sys.path.insert(0, '/workspace/code')

from harness_api import TestResult, TestGroup


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_tests() -> list[TestGroup]:
    groups = []

    g1 = TestGroup(name="Schema doğrulama")
    _test_schema(g1)
    groups.append(g1)

    g2 = TestGroup(name="LLM çağrısı")
    _test_llm_call(g2)
    groups.append(g2)

    g3 = TestGroup(name="Hata yönetimi")
    _test_error_handling(g3)
    groups.append(g3)

    g4 = TestGroup(name="Dosyaya kaydetme")
    _test_save(g4)
    groups.append(g4)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_import(g: TestGroup, test_id: str):
    try:
        import extractor
        return extractor
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"extractor.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="Dosya adı extractor.py olmalı; ReviewAnalysis, Sentiment, Category, extract_review tanımlı mı?",
        ))
        return None


def _make_mock_client(parsed_obj, log=None):
    """Build a mock async client whose parse() returns parsed_obj."""
    client = MagicMock()
    log = log if log is not None else []

    async def _parse(**kwargs):
        log.append(kwargs)
        msg = MagicMock()
        msg.parsed = parsed_obj
        msg.refusal = None
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    client.chat.completions.parse = _parse
    client._call_log = log
    return client


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Group 1 — Schema validation
# ---------------------------------------------------------------------------

def _test_schema(g: TestGroup) -> None:
    extractor = _safe_import(g, "test_schema_has_required_fields")
    if extractor is None:
        return

    # 1.1: ReviewAnalysis has all required fields
    try:
        ra = extractor.ReviewAnalysis(
            rating=4,
            sentiment=extractor.Sentiment.POSITIVE,
            category=extractor.Category.PRODUCT,
            summary="Memnunum",
        )
        # Verify field accessors
        assert ra.rating == 4
        assert ra.sentiment == extractor.Sentiment.POSITIVE
        assert ra.category == extractor.Category.PRODUCT
        assert ra.summary == "Memnunum"
        assert ra.red_flags == []  # default empty list
        g.add(TestResult(id="test_schema_has_required_fields", status="passed"))
    except AssertionError as e:
        g.add(TestResult(
            id="test_schema_has_required_fields",
            status="failed",
            input='ReviewAnalysis(rating=4, sentiment=POSITIVE, ...)',
            expected="all fields populate correctly",
            actual=f"assertion failure: {e}",
            hint="ReviewAnalysis'in 5 alanı olmalı: rating, sentiment, category, summary, red_flags",
        ))
    except Exception as e:
        g.add(TestResult(
            id="test_schema_has_required_fields",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
            hint="Sentiment ve Category enum'ları, ReviewAnalysis BaseModel olmalı",
        ))

    # 1.2: rating constraint enforced (1 <= rating <= 5)
    try:
        try:
            bad = extractor.ReviewAnalysis(
                rating=10,
                sentiment=extractor.Sentiment.POSITIVE,
                category=extractor.Category.PRODUCT,
                summary="X",
            )
            g.add(TestResult(
                id="test_rating_bounds_enforced",
                status="failed",
                input='ReviewAnalysis(rating=10, ...)',
                expected="ValidationError (rating must be <= 5)",
                actual=f"accepted rating={bad.rating}",
                hint="Field(ge=1, le=5) ile rating'i 1-5 arasına sınırla",
            ))
        except Exception:
            # Should raise pydantic.ValidationError or similar
            g.add(TestResult(id="test_rating_bounds_enforced", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_rating_bounds_enforced",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.3: Sentiment enum has 3 values
    try:
        values = {m.value for m in extractor.Sentiment}
        expected = {"positive", "neutral", "negative"}
        if values == expected:
            g.add(TestResult(id="test_sentiment_enum_values", status="passed"))
        else:
            g.add(TestResult(
                id="test_sentiment_enum_values",
                status="failed",
                input='Sentiment enum members',
                expected=f"{expected}",
                actual=f"{values}",
                hint='Sentiment enum\'ı 3 değer içermeli: "positive", "neutral", "negative"',
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_sentiment_enum_values",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — LLM call
# ---------------------------------------------------------------------------

def _test_llm_call(g: TestGroup) -> None:
    extractor = _safe_import(g, "test_extract_returns_pydantic")
    if extractor is None:
        return

    # 2.1: extract_review returns a ReviewAnalysis instance
    expected_obj = extractor.ReviewAnalysis(
        rating=3,
        sentiment=extractor.Sentiment.NEUTRAL,
        category=extractor.Category.SERVICE,
        summary="Vasat",
        red_flags=[],
    )
    client = _make_mock_client(expected_obj)
    try:
        result = _run_async(extractor.extract_review("test yorum", client))
        if isinstance(result, extractor.ReviewAnalysis) and result.rating == 3:
            g.add(TestResult(id="test_extract_returns_pydantic", status="passed"))
        else:
            g.add(TestResult(
                id="test_extract_returns_pydantic",
                status="failed",
                input='extract_review("test yorum", mock_client)',
                expected="ReviewAnalysis(rating=3, ...)",
                actual=f"{type(result).__name__}: {result!r}",
                hint="response.choices[0].message.parsed'i döndürmelisin",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_extract_returns_pydantic",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.2: response_format = ReviewAnalysis is passed
    expected_obj = extractor.ReviewAnalysis(
        rating=5, sentiment=extractor.Sentiment.POSITIVE,
        category=extractor.Category.PRODUCT, summary="iyi",
    )
    log = []
    client = _make_mock_client(expected_obj, log=log)
    try:
        _run_async(extractor.extract_review("güzel ürün", client))
        if not log:
            g.add(TestResult(
                id="test_response_format_passed",
                status="failed",
                input='extract_review(...)',
                expected="parse() called",
                actual="no API call recorded",
                hint="client.chat.completions.parse(...) çağrılmalı",
            ))
        else:
            kwargs = log[0]
            rf = kwargs.get("response_format")
            if rf is extractor.ReviewAnalysis:
                g.add(TestResult(id="test_response_format_passed", status="passed"))
            else:
                g.add(TestResult(
                    id="test_response_format_passed",
                    status="failed",
                    input='extract_review(...)',
                    expected="response_format=ReviewAnalysis",
                    actual=f"response_format = {rf!r}",
                    hint="parse() çağrısına response_format=ReviewAnalysis ekle",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_response_format_passed",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.3: messages have system + user roles
    log = []
    client = _make_mock_client(expected_obj, log=log)
    try:
        _run_async(extractor.extract_review("test", client))
        if log:
            messages = log[0].get("messages", [])
            roles = {m.get("role") for m in messages}
            if "system" in roles and "user" in roles:
                g.add(TestResult(id="test_messages_have_system_user", status="passed"))
            else:
                g.add(TestResult(
                    id="test_messages_have_system_user",
                    status="failed",
                    input='extract_review(...)',
                    expected='roles include {"system", "user"}',
                    actual=f"roles = {sorted(roles)}",
                    hint="messages listesine hem system hem user mesajı koy",
                ))
        else:
            g.add(TestResult(
                id="test_messages_have_system_user",
                status="errored",
                detail="No call recorded",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_messages_have_system_user",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Error handling
# ---------------------------------------------------------------------------

def _test_error_handling(g: TestGroup) -> None:
    extractor = _safe_import(g, "test_empty_text_rejected")
    if extractor is None:
        return

    obj = extractor.ReviewAnalysis(
        rating=3, sentiment=extractor.Sentiment.NEUTRAL,
        category=extractor.Category.OTHER, summary="X",
    )

    # 3.1: empty text raises ValueError before API call
    log = []
    client = _make_mock_client(obj, log=log)
    try:
        _run_async(extractor.extract_review("", client))
        g.add(TestResult(
            id="test_empty_text_rejected",
            status="failed",
            input='extract_review("", client)',
            expected="ValueError",
            actual="No exception",
            hint="Boş metin için ValueError fırlat (API ÇAĞRISI YAPMA)",
        ))
    except ValueError:
        if not log:
            g.add(TestResult(id="test_empty_text_rejected", status="passed"))
        else:
            g.add(TestResult(
                id="test_empty_text_rejected",
                status="failed",
                input='extract_review("", client)',
                expected="ValueError BEFORE API call",
                actual=f"ValueError raised but {len(log)} API calls happened",
                hint="text kontrolünü parse() çağrısından ÖNCE yap",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_empty_text_rejected",
            status="failed",
            input='extract_review("")',
            expected="ValueError",
            actual=f"{e.__class__.__name__}: {e}",
        ))

    # 3.2: API error wrapped in ExtractError
    bad_client = MagicMock()
    async def _boom(**kw):
        raise RuntimeError("rate limit")
    bad_client.chat.completions.parse = _boom
    try:
        _run_async(extractor.extract_review("test", bad_client))
        g.add(TestResult(
            id="test_api_error_wrapped",
            status="failed",
            input='extract_review with API raising RuntimeError',
            expected="ExtractError",
            actual="No exception",
            hint="API çağrısını try/except ile sar, ExtractError fırlat",
        ))
    except extractor.ExtractError:
        g.add(TestResult(id="test_api_error_wrapped", status="passed"))
    except RuntimeError:
        g.add(TestResult(
            id="test_api_error_wrapped",
            status="failed",
            input='extract_review with API raising RuntimeError',
            expected="ExtractError (wrapped)",
            actual="RuntimeError raised raw",
            hint="raise ExtractError(...) from e ile sarmala",
        ))
    except Exception as e:
        g.add(TestResult(
            id="test_api_error_wrapped",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.3: parsed=None handled (refusal scenario)
    null_client = MagicMock()
    async def _null(**kw):
        msg = MagicMock()
        msg.parsed = None
        msg.refusal = None
        choice = MagicMock(); choice.message = msg
        resp = MagicMock(); resp.choices = [choice]
        return resp
    null_client.chat.completions.parse = _null
    try:
        _run_async(extractor.extract_review("test", null_client))
        g.add(TestResult(
            id="test_none_parsed_handled",
            status="failed",
            input='API returns parsed=None',
            expected="ExtractError",
            actual="No exception",
            hint="parsed None ise ExtractError fırlat — None'u kullanıcıya verme",
        ))
    except extractor.ExtractError:
        g.add(TestResult(id="test_none_parsed_handled", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_none_parsed_handled",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 4 — Save
# ---------------------------------------------------------------------------

def _test_save(g: TestGroup) -> None:
    extractor = _safe_import(g, "test_save_creates_json_array")
    if extractor is None:
        return

    a1 = extractor.ReviewAnalysis(
        rating=5, sentiment=extractor.Sentiment.POSITIVE,
        category=extractor.Category.PRODUCT, summary="Harika ürün",
        red_flags=[],
    )
    a2 = extractor.ReviewAnalysis(
        rating=1, sentiment=extractor.Sentiment.NEGATIVE,
        category=extractor.Category.DELIVERY, summary="Kargo gelmedi",
        red_flags=["1 hafta gecikme", "iletişim yok"],
    )

    # 4.1: Saved file is JSON array with review + analysis fields
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        extractor.save_analyses(["yorum 1", "yorum 2"], [a1, a2], path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if (
            isinstance(data, list)
            and len(data) == 2
            and {"review", "analysis"} <= set(data[0].keys())
        ):
            g.add(TestResult(id="test_save_creates_json_array", status="passed"))
        else:
            g.add(TestResult(
                id="test_save_creates_json_array",
                status="failed",
                input='save_analyses(2 reviews, 2 analyses)',
                expected='[{"review":..., "analysis":...}, ...]',
                actual=repr(data)[:120],
                hint="Her kayıt review + analysis içeren bir dict olmalı",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_save_creates_json_array",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.2: Enum values serialize as strings (not Sentiment.POSITIVE objects)
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        extractor.save_analyses(["yorum"], [a1], path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()  # raw text
            data = json.loads(content)
        sentiment_value = data[0]["analysis"]["sentiment"]
        if sentiment_value == "positive" and "Sentiment.POSITIVE" not in content:
            g.add(TestResult(id="test_enum_serialized_as_string", status="passed"))
        else:
            g.add(TestResult(
                id="test_enum_serialized_as_string",
                status="failed",
                input='save_analyses with Sentiment.POSITIVE',
                expected='"sentiment": "positive"',
                actual=f'sentiment = {sentiment_value!r}',
                hint='Pydantic\'in model_dump(mode="json") kullan — Enum\'lar string\'e dönüşür',
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_enum_serialized_as_string",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.3: Length mismatch raises ValueError
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        extractor.save_analyses(["a", "b", "c"], [a1, a2], path)  # 3 vs 2
        g.add(TestResult(
            id="test_save_length_mismatch_raises",
            status="failed",
            input='save_analyses(3 texts, 2 analyses)',
            expected="ValueError",
            actual="No exception",
            hint="len(texts) != len(analyses) ise ValueError fırlat",
        ))
    except ValueError:
        g.add(TestResult(id="test_save_length_mismatch_raises", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_save_length_mismatch_raises",
            status="failed",
            input='save_analyses with mismatched lengths',
            expected="ValueError",
            actual=f"{e.__class__.__name__}: {e}",
        ))
