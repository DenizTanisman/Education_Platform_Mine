"""
M6 — Final test runner.

Tests the stateful assistant from assistant.py.

Test groups (must match unit.yaml):
  - "Bellek temelleri"       — cosine_similarity, MemoryStore CRUD
  - "Kalıcılık"              — save/load round-trip, fresh on missing file
  - "Bellek araçları"         — remember_fact / recall_fact / search_memory tool calls
  - "Asistan döngüsü"        — multi-turn flow, conversation persisted
"""

import asyncio
import json
import math
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

    g1 = TestGroup(name="Bellek temelleri")
    _test_memory_basics(g1)
    groups.append(g1)

    g2 = TestGroup(name="Kalıcılık")
    _test_persistence(g2)
    groups.append(g2)

    g3 = TestGroup(name="Bellek araçları")
    _test_memory_tools(g3)
    groups.append(g3)

    g4 = TestGroup(name="Asistan döngüsü")
    _test_assistant_loop(g4)
    groups.append(g4)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_import(g: TestGroup, test_id: str):
    try:
        import assistant
        return assistant
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"assistant.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="Dosya adı assistant.py olmalı; MemoryStore, run_assistant, cosine_similarity tanımlı mı?",
        ))
        return None


def _make_response(content=None, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_tool_call(call_id, name, args_dict):
    tc = MagicMock()
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(args_dict)
    return tc


def _make_embedding_response(vec):
    item = MagicMock()
    item.embedding = vec
    resp = MagicMock()
    resp.data = [item]
    return resp


def _make_mock_client(chat_scripts=None, embedding_vec=None):
    """Mock async client with scripted chat responses + fixed embedding vector."""
    client = MagicMock()
    client._call_log = []
    client._embed_log = []
    chat_iter = iter(chat_scripts or [])

    async def fake_chat(**kwargs):
        client._call_log.append(kwargs)
        try:
            return next(chat_iter)
        except StopIteration:
            return _make_response(content="<exhausted>")

    async def fake_emb(**kwargs):
        client._embed_log.append(kwargs)
        return _make_embedding_response(embedding_vec or [0.1] * 1536)

    client.chat.completions.create = fake_chat
    client.embeddings.create = fake_emb
    return client


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Group 1 — Memory basics (cosine similarity + MemoryStore CRUD)
# ---------------------------------------------------------------------------

def _test_memory_basics(g: TestGroup) -> None:
    assistant = _safe_import(g, "test_cosine_similarity_math")
    if assistant is None:
        return

    # 1.1: cosine_similarity returns expected values for known vectors
    try:
        identical = assistant.cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        orthogonal = assistant.cosine_similarity([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])
        opposite = assistant.cosine_similarity([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0])

        ok = (
            math.isclose(identical, 1.0, abs_tol=1e-6)
            and math.isclose(orthogonal, 0.0, abs_tol=1e-6)
            and math.isclose(opposite, -1.0, abs_tol=1e-6)
        )
        if ok:
            g.add(TestResult(id="test_cosine_similarity_math", status="passed"))
        else:
            g.add(TestResult(
                id="test_cosine_similarity_math",
                status="failed",
                input='cosine_similarity tests: identical, orthogonal, opposite',
                expected="1.0, 0.0, -1.0",
                actual=f"{identical}, {orthogonal}, {opposite}",
                hint="cosine_similarity = dot(a,b) / (||a|| * ||b||)",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_cosine_similarity_math",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.2: MemoryStore.remember_fact and recall_fact roundtrip
    try:
        store = assistant.MemoryStore()
        store.remember_fact("name", "Deniz")
        store.remember_fact("city", "İstanbul")
        v1 = store.recall_fact("name")
        v2 = store.recall_fact("city")
        v3 = store.recall_fact("missing")
        if v1 == "Deniz" and v2 == "İstanbul" and v3 is None:
            g.add(TestResult(id="test_facts_crud", status="passed"))
        else:
            g.add(TestResult(
                id="test_facts_crud",
                status="failed",
                input='remember/recall facts',
                expected="('Deniz', 'İstanbul', None)",
                actual=f"({v1!r}, {v2!r}, {v3!r})",
                hint="recall_fact key bulamazsa None döndürmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_facts_crud",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.3: search_memories ranks by similarity
    try:
        store = assistant.MemoryStore()
        store.add_memory("apple text", [1.0, 0.0, 0.0])
        store.add_memory("banana text", [0.0, 1.0, 0.0])
        store.add_memory("close-to-apple", [0.9, 0.1, 0.0])

        # Query close to first vector
        results = store.search_memories([1.0, 0.0, 0.0], top_k=2)
        if (
            len(results) == 2
            and results[0]["text"] == "apple text"
            and results[1]["text"] == "close-to-apple"
        ):
            g.add(TestResult(id="test_search_memories_ranks", status="passed"))
        else:
            g.add(TestResult(
                id="test_search_memories_ranks",
                status="failed",
                input='search_memories with query=[1,0,0], top_k=2',
                expected='["apple text", "close-to-apple"] in order',
                actual=f"got {[r['text'] for r in results]}",
                hint="cosine score'a göre azalan sırada sırala",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_search_memories_ranks",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — Persistence
# ---------------------------------------------------------------------------

def _test_persistence(g: TestGroup) -> None:
    assistant = _safe_import(g, "test_save_load_roundtrip")
    if assistant is None:
        return

    # 2.1: save() and load() roundtrip
    try:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)  # ensure fresh

        store1 = assistant.MemoryStore(path=path)
        store1.remember_fact("name", "Deniz")
        store1.add_memory("test note", [0.1, 0.2, 0.3])
        store1.save()

        if not os.path.exists(path):
            g.add(TestResult(
                id="test_save_load_roundtrip",
                status="failed",
                input='store.save() with path set',
                expected="file exists at path",
                actual="file missing",
                hint="save() path is None değilse JSON dosyaya yazmalı",
            ))
        else:
            store2 = assistant.MemoryStore.load(path)
            if (
                store2.recall_fact("name") == "Deniz"
                and len(store2.memories) == 1
                and store2.memories[0]["text"] == "test note"
            ):
                g.add(TestResult(id="test_save_load_roundtrip", status="passed"))
            else:
                g.add(TestResult(
                    id="test_save_load_roundtrip",
                    status="failed",
                    input='save then load',
                    expected="facts and memories preserved",
                    actual=f"facts={store2.facts}, mems={len(store2.memories)}",
                    hint="JSON encoding/decoding doğru olmalı; facts ve memories ayrı tutulmalı",
                ))
        os.unlink(path)
    except Exception as e:
        g.add(TestResult(
            id="test_save_load_roundtrip",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.2: Loading a missing file returns empty store
    try:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)  # delete

        store = assistant.MemoryStore.load(path)
        if (
            isinstance(store, assistant.MemoryStore)
            and store.facts == {}
            and store.memories == []
            and store.path == path
        ):
            g.add(TestResult(id="test_load_missing_file_fresh", status="passed"))
        else:
            g.add(TestResult(
                id="test_load_missing_file_fresh",
                status="failed",
                input='load() on non-existent path',
                expected="fresh empty store with path set",
                actual=f"facts={store.facts}, mems={len(store.memories)}, path={store.path!r}",
                hint="Dosya yoksa MemoryStore(path=path) ile boş store döndür (FileNotFoundError fırlatma)",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_load_missing_file_fresh",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.3: save() with None path is a no-op (in-memory mode)
    try:
        store = assistant.MemoryStore()  # path=None
        store.remember_fact("x", "y")
        store.save()  # should not raise, should not create files
        g.add(TestResult(id="test_save_inmemory_noop", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_save_inmemory_noop",
            status="failed",
            input='store with path=None, then save()',
            expected="no error (no-op)",
            actual=f"{e.__class__.__name__}: {e}",
            hint="save() içinde path is None ise erken dön (return)",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Memory tools (LLM-callable wrappers)
# ---------------------------------------------------------------------------

def _test_memory_tools(g: TestGroup) -> None:
    assistant = _safe_import(g, "test_remember_fact_tool")
    if assistant is None:
        return

    # 3.1: remember_fact tool persists into the store
    try:
        store = assistant.MemoryStore()
        client = _make_mock_client()
        registry = assistant.build_memory_registry(store, client)

        result = _run_async(registry.call("remember_fact", {"key": "name", "value": "Deniz"}))
        if store.recall_fact("name") == "Deniz" and result.get("status") == "saved":
            g.add(TestResult(id="test_remember_fact_tool", status="passed"))
        else:
            g.add(TestResult(
                id="test_remember_fact_tool",
                status="failed",
                input='registry.call("remember_fact", {"key":"name","value":"Deniz"})',
                expected='store.facts["name"] == "Deniz", result {"status":"saved",...}',
                actual=f"facts={store.facts}, result={result}",
                hint="remember_fact handler store.remember_fact(key,value) çağırmalı",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_remember_fact_tool",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.2: recall_fact tool returns found / not found
    try:
        store = assistant.MemoryStore()
        store.remember_fact("home_city", "İstanbul")
        client = _make_mock_client()
        registry = assistant.build_memory_registry(store, client)

        found = _run_async(registry.call("recall_fact", {"key": "home_city"}))
        missing = _run_async(registry.call("recall_fact", {"key": "favorite_food"}))

        ok = (
            found.get("found") is True and found.get("value") == "İstanbul"
            and missing.get("found") is False
        )
        if ok:
            g.add(TestResult(id="test_recall_fact_tool", status="passed"))
        else:
            g.add(TestResult(
                id="test_recall_fact_tool",
                status="failed",
                input='recall_fact for existing and missing key',
                expected='{"found": True, "value": ...}, {"found": False}',
                actual=f"found={found}, missing={missing}",
                hint="recall_fact handler store.recall_fact()'i çağırıp found/value döndürmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_recall_fact_tool",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.3: search_memory tool calls embedding API and returns top results
    try:
        store = assistant.MemoryStore()
        store.add_memory("İstanbul'da yaşıyorum", [1.0, 0.0, 0.0])
        store.add_memory("Python öğreniyorum", [0.0, 1.0, 0.0])

        client = _make_mock_client(embedding_vec=[1.0, 0.0, 0.0])
        registry = assistant.build_memory_registry(store, client)

        result = _run_async(registry.call("search_memory", {"query": "şehrim"}))
        if (
            "results" in result
            and isinstance(result["results"], list)
            and len(result["results"]) >= 1
            and result["results"][0]["text"] == "İstanbul'da yaşıyorum"
        ):
            g.add(TestResult(id="test_search_memory_tool", status="passed"))
        else:
            g.add(TestResult(
                id="test_search_memory_tool",
                status="failed",
                input='search_memory with mocked embedding=[1,0,0]',
                expected='results[0].text == "İstanbul\'da yaşıyorum"',
                actual=repr(result)[:120],
                hint="search_memory handler get_embedding ile query'i embed et, sonra search_memories çağır",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_search_memory_tool",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 4 — Assistant loop (multi-turn, persistence integration)
# ---------------------------------------------------------------------------

def _test_assistant_loop(g: TestGroup) -> None:
    assistant = _safe_import(g, "test_basic_turn_with_tool")
    if assistant is None:
        return

    # 4.1: A turn that calls remember_fact then returns final answer.
    # After the turn, store should have the fact and a conversation entry.
    try:
        store = assistant.MemoryStore()
        client = _make_mock_client(chat_scripts=[
            _make_response(tool_calls=[
                _make_tool_call("c1", "remember_fact", {"key": "name", "value": "Deniz"}),
            ]),
            _make_response(content="Tamam Deniz, kaydettim.", tool_calls=None),
        ], embedding_vec=[0.5] * 1536)

        answer = _run_async(assistant.run_assistant("Adım Deniz", client, store))

        ok = (
            answer == "Tamam Deniz, kaydettim."
            and store.recall_fact("name") == "Deniz"
            and len(store.conversation) == 2
        )
        if ok:
            g.add(TestResult(id="test_basic_turn_with_tool", status="passed"))
        else:
            g.add(TestResult(
                id="test_basic_turn_with_tool",
                status="failed",
                input='run_assistant("Adım Deniz") with scripted remember_fact',
                expected='answer correct, fact saved, 2 conversation entries',
                actual=f"answer={answer!r}, name={store.recall_fact('name')!r}, "
                       f"conv={len(store.conversation)}",
                hint="Final cevaptan sonra user+assistant mesajları conversation'a eklenmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_basic_turn_with_tool",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.2: Empty message rejected with no API calls
    try:
        store = assistant.MemoryStore()
        client = _make_mock_client(chat_scripts=[])
        try:
            _run_async(assistant.run_assistant("", client, store))
            g.add(TestResult(
                id="test_empty_message_rejected",
                status="failed",
                input='run_assistant("", ...)',
                expected="ValueError",
                actual="No exception",
                hint="Boş mesaj için ValueError fırlat (API çağrısı yapma)",
            ))
        except ValueError:
            if not client._call_log and not client._embed_log:
                g.add(TestResult(id="test_empty_message_rejected", status="passed"))
            else:
                g.add(TestResult(
                    id="test_empty_message_rejected",
                    status="failed",
                    input='run_assistant("", ...)',
                    expected="ValueError BEFORE API calls",
                    actual=f"chat={len(client._call_log)}, embed={len(client._embed_log)}",
                    hint="Validation kontrolünü create() çağrısından önce yap",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_empty_message_rejected",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.3: Prior conversation is included in next turn's messages
    try:
        store = assistant.MemoryStore()
        # Pre-populate one prior turn
        store.conversation = [
            {"role": "user", "content": "Adım Deniz"},
            {"role": "assistant", "content": "Tanıştığımıza memnun oldum Deniz."},
        ]

        client = _make_mock_client(chat_scripts=[
            _make_response(content="Evet hatırlıyorum, sen Deniz'sin.", tool_calls=None),
        ], embedding_vec=[0.5] * 1536)

        _run_async(assistant.run_assistant("Adımı hatırlıyor musun?", client, store))

        # Inspect the messages that were sent to the API on the first call
        if client._call_log:
            sent_messages = client._call_log[0]["messages"]
            user_contents = [m["content"] for m in sent_messages if m.get("role") == "user"]
            # Both old user msg and new one should be present
            if "Adım Deniz" in user_contents and "Adımı hatırlıyor musun?" in user_contents:
                g.add(TestResult(id="test_prior_conversation_carried", status="passed"))
            else:
                g.add(TestResult(
                    id="test_prior_conversation_carried",
                    status="failed",
                    input='run_assistant after prior turn in store.conversation',
                    expected="prior 'Adım Deniz' message in API call",
                    actual=f"user contents: {user_contents}",
                    hint="messages listesini kurarken store.conversation'ı dahil et",
                ))
        else:
            g.add(TestResult(
                id="test_prior_conversation_carried",
                status="errored",
                detail="No API call recorded",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_prior_conversation_carried",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))
