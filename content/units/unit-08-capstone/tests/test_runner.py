"""
M8 — Final test runner for the Capstone (Mini Jarvis).

Tests the integrated system from jarvis.py.

Test groups (must match unit.yaml):
  - "Çekirdek yapı"          — JarvisStore composition, TaskStore CRUD, types
  - "Doküman boru hattı"      — chunking, embedding pipeline, ingest
  - "Tool registry"           — 6 tools registered, OpenAI format, registry.call
  - "Agent loop"              — single-iter, multi-tool turn, prior conversation
  - "Bütünleşme"              — end-to-end scenarios mixing memory+tasks+RAG
"""

import asyncio
import json
import os
import sys
from unittest.mock import MagicMock

# In platform sandbox, student code is at /workspace/code
sys.path.insert(0, '/workspace/code')

from harness_api import TestResult, TestGroup


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_tests() -> list[TestGroup]:
    groups = []

    g1 = TestGroup(name="Çekirdek yapı")
    _test_core_structure(g1)
    groups.append(g1)

    g2 = TestGroup(name="Doküman boru hattı")
    _test_document_pipeline(g2)
    groups.append(g2)

    g3 = TestGroup(name="Tool registry")
    _test_tool_registry(g3)
    groups.append(g3)

    g4 = TestGroup(name="Agent loop")
    _test_agent_loop(g4)
    groups.append(g4)

    g5 = TestGroup(name="Bütünleşme")
    _test_integration(g5)
    groups.append(g5)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_import(g: TestGroup, test_id: str):
    try:
        import jarvis
        return jarvis
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"jarvis.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="Dosya adı jarvis.py olmalı; JarvisStore, run_jarvis, ingest_document_into tanımlı mı?",
        ))
        return None


def _make_emb(vec):
    item = MagicMock()
    item.embedding = vec
    resp = MagicMock()
    resp.data = [item]
    return resp


def _make_chat(content=None, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_tc(call_id, name, args_dict):
    tc = MagicMock()
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(args_dict)
    return tc


def _make_mock_client(chat_scripts=None, emb_scripts=None, default_emb=None):
    """Mock async client.

    chat_scripts: list of pre-built chat responses (StopIteration -> default)
    emb_scripts: list of vectors (StopIteration -> default_emb or [0.5]*1536)
    """
    client = MagicMock()
    client._chat_log = []
    client._emb_log = []

    chat_iter = iter(chat_scripts or [])
    emb_iter = iter(emb_scripts or [])
    default_vec = default_emb if default_emb else [0.5] * 1536

    async def fake_chat(**kwargs):
        client._chat_log.append(kwargs)
        try:
            return next(chat_iter)
        except StopIteration:
            return _make_chat(content="<exhausted>")

    async def fake_emb(**kwargs):
        client._emb_log.append(kwargs)
        try:
            return _make_emb(next(emb_iter))
        except StopIteration:
            return _make_emb(default_vec)

    client.chat.completions.create = fake_chat
    client.embeddings.create = fake_emb
    return client


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Group 1 — Core structure
# ---------------------------------------------------------------------------

def _test_core_structure(g: TestGroup) -> None:
    jarvis = _safe_import(g, "test_jarvis_store_has_three_substores")
    if jarvis is None:
        return

    # 1.1: JarvisStore.fresh() returns object with memory, rag, tasks
    try:
        store = jarvis.JarvisStore.fresh()
        ok = (
            hasattr(store, "memory")
            and hasattr(store, "rag")
            and hasattr(store, "tasks")
            and isinstance(store.memory, jarvis.MemoryStore)
            and isinstance(store.rag, jarvis.RAGStore)
        )
        if ok:
            g.add(TestResult(id="test_jarvis_store_has_three_substores", status="passed"))
        else:
            g.add(TestResult(
                id="test_jarvis_store_has_three_substores",
                status="failed",
                input='JarvisStore.fresh()',
                expected="store.memory (MemoryStore), store.rag (RAGStore), store.tasks",
                actual=f"memory={hasattr(store, 'memory')}, rag={hasattr(store, 'rag')}, tasks={hasattr(store, 'tasks')}",
                hint="JarvisStore üç alt-store içermeli: memory, rag, tasks",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_jarvis_store_has_three_substores",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.2: TaskStore.add_task + list_tasks roundtrip
    try:
        store = jarvis.JarvisStore.fresh()
        t1 = store.tasks.add_task("Görev 1")
        t2 = store.tasks.add_task("Görev 2")
        all_tasks = store.tasks.list_tasks()
        ids = [t.id for t in all_tasks]
        titles = [t.title for t in all_tasks]
        ok = (
            len(all_tasks) == 2
            and ids == sorted(ids)  # ascending
            and titles == ["Görev 1", "Görev 2"]
            and all(not t.done for t in all_tasks)
        )
        if ok:
            g.add(TestResult(id="test_task_store_crud", status="passed"))
        else:
            g.add(TestResult(
                id="test_task_store_crud",
                status="failed",
                input='add 2 tasks, list_tasks()',
                expected="2 tasks with sequential ids, both undone",
                actual=f"ids={ids}, titles={titles}",
                hint="TaskStore SQLite ile çalışmalı; AUTOINCREMENT id, done=0 default",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_task_store_crud",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.3: MemoryStore facts + recall basics
    try:
        store = jarvis.JarvisStore.fresh()
        store.memory.remember_fact("name", "Deniz")
        v1 = store.memory.recall_fact("name")
        v2 = store.memory.recall_fact("missing_key")
        if v1 == "Deniz" and v2 is None:
            g.add(TestResult(id="test_memory_facts_basic", status="passed"))
        else:
            g.add(TestResult(
                id="test_memory_facts_basic",
                status="failed",
                input='remember "name"="Deniz", recall both',
                expected='("Deniz", None)',
                actual=f"({v1!r}, {v2!r})",
                hint="recall_fact eksik key için None döndürmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_memory_facts_basic",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — Document pipeline
# ---------------------------------------------------------------------------

def _test_document_pipeline(g: TestGroup) -> None:
    jarvis = _safe_import(g, "test_chunking_walking_window")
    if jarvis is None:
        return

    # 2.1: Walking-window chunking
    try:
        text = "abcdefghij" * 100  # 1000 chars
        chunks = jarvis.chunk_text(text, chunk_size=300, chunk_overlap=50)
        ok = (
            len(chunks) >= 3
            and len(chunks[0]) <= 300
        )
        if ok:
            g.add(TestResult(id="test_chunking_walking_window", status="passed"))
        else:
            g.add(TestResult(
                id="test_chunking_walking_window",
                status="failed",
                input='chunk_text(1000 chars, size=300, overlap=50)',
                expected="3+ chunks, each <= 300 chars",
                actual=f"len={len(chunks)}, first_size={len(chunks[0]) if chunks else 0}",
                hint="walking-window: start=0, step=size-overlap",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_chunking_walking_window",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.2: ingest_document_into pipelines text -> embedded chunks in store.rag
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client(default_emb=[0.5] * 1536)
        text = ("Bu bir test belgesidir. " * 30)  # ~720 chars
        count = _run_async(jarvis.ingest_document_into(
            text, source="test.md", store=store, client=client,
            chunk_size=200, chunk_overlap=20,
        ))
        ok = (
            count >= 2
            and len(store.rag.chunks) == count
            and {c.source for c in store.rag.chunks} == {"test.md"}
            and all(len(c.embedding) > 0 for c in store.rag.chunks)
        )
        if ok:
            g.add(TestResult(id="test_ingest_pipeline", status="passed"))
        else:
            g.add(TestResult(
                id="test_ingest_pipeline",
                status="failed",
                input='ingest_document_into(720 chars, size=200, overlap=20)',
                expected="2+ chunks added with embeddings, all from 'test.md'",
                actual=(
                    f"count={count}, store has {len(store.rag.chunks)} chunks, "
                    f"sources={ {c.source for c in store.rag.chunks} }, "
                    f"embedded={all(c.embedding for c in store.rag.chunks)}"
                ),
                hint="ingest_document_into chunk_text + parallel embed + store.rag.add_chunks zinciri",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_ingest_pipeline",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.3: ingest empty rejected, no API calls
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client()
        try:
            _run_async(jarvis.ingest_document_into("", "x.md", store, client))
            g.add(TestResult(
                id="test_ingest_empty_rejected",
                status="failed",
                input='ingest_document_into("", "x.md")',
                expected="ValueError",
                actual="No exception",
                hint="Boş text için ValueError fırlat (API çağrısı yapma)",
            ))
        except ValueError:
            if not client._emb_log:
                g.add(TestResult(id="test_ingest_empty_rejected", status="passed"))
            else:
                g.add(TestResult(
                    id="test_ingest_empty_rejected",
                    status="failed",
                    input='ingest_document_into("")',
                    expected="ValueError BEFORE embedding API",
                    actual=f"ValueError raised but {len(client._emb_log)} embed calls happened",
                    hint="Validation kontrolünü embedding'den önce yap",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_ingest_empty_rejected",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Tool registry
# ---------------------------------------------------------------------------

def _test_tool_registry(g: TestGroup) -> None:
    jarvis = _safe_import(g, "test_six_tools_registered")
    if jarvis is None:
        return

    # 3.1: build_jarvis_registry produces 6 tools (memory:3, tasks:2, rag:1)
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client()
        registry = jarvis.build_jarvis_registry(store, client)
        names = set(registry.tools.keys())
        expected = {
            "remember_fact", "recall_fact", "search_memory",
            "add_task", "list_tasks",
            "search_documents",
        }
        if names == expected:
            g.add(TestResult(id="test_six_tools_registered", status="passed"))
        else:
            g.add(TestResult(
                id="test_six_tools_registered",
                status="failed",
                input='build_jarvis_registry(...).tools.keys()',
                expected=f"{sorted(expected)}",
                actual=f"{sorted(names)}",
                hint="6 tool olmalı: 3 memory + 2 task + 1 RAG",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_six_tools_registered",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.2: registry.to_openai_list produces correctly shaped tool entries
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client()
        registry = jarvis.build_jarvis_registry(store, client)
        tools_list = registry.to_openai_list()

        if not isinstance(tools_list, list) or len(tools_list) != 6:
            g.add(TestResult(
                id="test_openai_tool_format",
                status="failed",
                input='registry.to_openai_list()',
                expected="list of 6 entries",
                actual=f"len={len(tools_list) if isinstance(tools_list, list) else type(tools_list).__name__}",
                hint="to_openai_list 6 elemanlı liste döndürmeli",
            ))
        else:
            first = tools_list[0]
            ok = (
                first.get("type") == "function"
                and "function" in first
                and "name" in first["function"]
                and "parameters" in first["function"]
            )
            if ok:
                g.add(TestResult(id="test_openai_tool_format", status="passed"))
            else:
                g.add(TestResult(
                    id="test_openai_tool_format",
                    status="failed",
                    input='first tool entry shape',
                    expected='{"type":"function", "function":{"name", "description", "parameters"}}',
                    actual=repr(first)[:140],
                    hint="Her tool {type:'function', function:{...}} formatında",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_openai_tool_format",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.3: registry.call routes to handler with parsed Pydantic input
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client()
        registry = jarvis.build_jarvis_registry(store, client)

        # add_task tool routes through registry — should mutate store.tasks
        result = _run_async(registry.call("add_task", {"title": "Test görev"}))
        tasks = store.tasks.list_tasks()

        ok = (
            isinstance(result, dict)
            and result.get("title") == "Test görev"
            and len(tasks) == 1
            and tasks[0].title == "Test görev"
        )
        if ok:
            g.add(TestResult(id="test_registry_call_routes", status="passed"))
        else:
            g.add(TestResult(
                id="test_registry_call_routes",
                status="failed",
                input='registry.call("add_task", {"title":"Test görev"})',
                expected='task added to store, result has title',
                actual=f"result={result}, tasks={[(t.id, t.title) for t in tasks]}",
                hint="add_task handler store.tasks.add_task çağırmalı, result dict döndürmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_registry_call_routes",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 4 — Agent loop
# ---------------------------------------------------------------------------

def _test_agent_loop(g: TestGroup) -> None:
    jarvis = _safe_import(g, "test_simple_text_response")
    if jarvis is None:
        return

    # 4.1: Single iteration — model returns content, no tools called
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client(chat_scripts=[
            _make_chat(content="Direkt cevap.", tool_calls=None),
        ])
        result = _run_async(jarvis.run_jarvis("hello", store, client))
        # Conversation must be persisted
        if (
            result == "Direkt cevap."
            and len(store.memory.conversation) == 2
            and store.memory.conversation[0]["content"] == "hello"
            and store.memory.conversation[1]["content"] == "Direkt cevap."
        ):
            g.add(TestResult(id="test_simple_text_response", status="passed"))
        else:
            g.add(TestResult(
                id="test_simple_text_response",
                status="failed",
                input='run_jarvis with model returning text only',
                expected="answer correct + 2 conversation entries",
                actual=f"result={result!r}, conv_len={len(store.memory.conversation)}",
                hint="Final cevaptan sonra user+assistant mesajları conversation'a eklenmeli",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_simple_text_response",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.2: Multi-tool turn — 2 parallel tool calls, then final answer
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client(chat_scripts=[
            _make_chat(tool_calls=[
                _make_tc("c1", "remember_fact", {"key": "name", "value": "Deniz"}),
                _make_tc("c2", "add_task", {"title": "Ödevi yap"}),
            ]),
            _make_chat(content="Tamam, kaydettim.", tool_calls=None),
        ])
        answer = _run_async(jarvis.run_jarvis("Adım Deniz, ödevi listeme ekle", store, client))

        # Both side-effects must have happened
        ok = (
            answer == "Tamam, kaydettim."
            and store.memory.recall_fact("name") == "Deniz"
            and any(t.title == "Ödevi yap" for t in store.tasks.list_tasks())
        )
        if ok:
            g.add(TestResult(id="test_multi_tool_turn", status="passed"))
        else:
            g.add(TestResult(
                id="test_multi_tool_turn",
                status="failed",
                input='run_jarvis with 2 parallel tool calls',
                expected="both side-effects (memory + task) occurred + final answer",
                actual=(
                    f"answer={answer!r}, "
                    f"name={store.memory.recall_fact('name')}, "
                    f"tasks={[t.title for t in store.tasks.list_tasks()]}"
                ),
                hint="Aynı turn'de 2+ tool call paralel execute edilmeli, hepsi store'a yansımalı",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_multi_tool_turn",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.3: Empty message rejected, no API calls
    try:
        store = jarvis.JarvisStore.fresh()
        client = _make_mock_client()
        try:
            _run_async(jarvis.run_jarvis("", store, client))
            g.add(TestResult(
                id="test_empty_message_rejected",
                status="failed",
                input='run_jarvis("", ...)',
                expected="ValueError",
                actual="No exception",
                hint="Boş mesaj için ValueError fırlat (API çağrısı yapma)",
            ))
        except ValueError:
            if not client._chat_log and not client._emb_log:
                g.add(TestResult(id="test_empty_message_rejected", status="passed"))
            else:
                g.add(TestResult(
                    id="test_empty_message_rejected",
                    status="failed",
                    input='run_jarvis("")',
                    expected="ValueError BEFORE any API call",
                    actual=f"chat={len(client._chat_log)}, emb={len(client._emb_log)}",
                    hint="Validation create() çağrısından önce yapılmalı",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_empty_message_rejected",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 5 — Integration scenarios
# ---------------------------------------------------------------------------

def _test_integration(g: TestGroup) -> None:
    jarvis = _safe_import(g, "test_facts_summary_in_system_message")
    if jarvis is None:
        return

    # 5.1: Facts are surfaced as a system hint to the model
    try:
        store = jarvis.JarvisStore.fresh()
        store.memory.facts["name"] = "Deniz"
        store.memory.facts["home_city"] = "İstanbul"

        client = _make_mock_client(chat_scripts=[
            _make_chat(content="Hi Deniz!", tool_calls=None),
        ])
        _run_async(jarvis.run_jarvis("Hi", store, client))

        if not client._chat_log:
            g.add(TestResult(
                id="test_facts_summary_in_system_message",
                status="errored",
                detail="No chat call recorded",
            ))
        else:
            sent_messages = client._chat_log[0]["messages"]
            blob = "\n".join(str(m.get("content", "")) for m in sent_messages)
            # facts hint should mention both keys/values
            if "Deniz" in blob and "İstanbul" in blob:
                g.add(TestResult(id="test_facts_summary_in_system_message", status="passed"))
            else:
                g.add(TestResult(
                    id="test_facts_summary_in_system_message",
                    status="failed",
                    input='run_jarvis with pre-existing facts',
                    expected="facts surfaced in system message blob",
                    actual=f"blob doesn't contain Deniz/İstanbul",
                    hint="run_jarvis system message'a facts hint olarak ekle",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_facts_summary_in_system_message",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 5.2: search_documents tool actually queries store.rag.chunks
    try:
        store = jarvis.JarvisStore.fresh()
        # Pre-populate RAG store directly
        store.rag.add_chunks([
            jarvis.Chunk(
                text="UNIQUE_DOC_PHRASE_777",
                source="docs.md", chunk_index=0,
                embedding=[1.0, 0.0, 0.0],
            ),
        ])

        client = _make_mock_client(
            emb_scripts=[[1.0, 0.0, 0.0]],   # query embedding
            chat_scripts=[
                _make_chat(tool_calls=[
                    _make_tc("c1", "search_documents", {"query": "ne yazıyor?"}),
                ]),
                _make_chat(content="Dokümanda UNIQUE_DOC_PHRASE_777 var."),
            ],
        )
        answer = _run_async(jarvis.run_jarvis("doküman", store, client))

        # The second chat call should have the chunk text in the tool result
        if len(client._chat_log) < 2:
            g.add(TestResult(
                id="test_rag_tool_returns_chunks",
                status="failed",
                input='run_jarvis triggers search_documents',
                expected="2 chat calls (tool + final)",
                actual=f"chat calls: {len(client._chat_log)}",
                hint="Tool execute edilince ikinci chat çağrısı yapılmalı",
            ))
        else:
            second_messages = client._chat_log[1]["messages"]
            tool_results_blob = "\n".join(
                str(m.get("content", "")) for m in second_messages
                if m.get("role") == "tool"
            )
            if "UNIQUE_DOC_PHRASE_777" in tool_results_blob:
                g.add(TestResult(id="test_rag_tool_returns_chunks", status="passed"))
            else:
                g.add(TestResult(
                    id="test_rag_tool_returns_chunks",
                    status="failed",
                    input='search_documents tool with chunk in store',
                    expected="chunk text appears in tool result on next API call",
                    actual=f"tool blob: {tool_results_blob[:100]}",
                    hint="search_documents handler store.rag.search çağırıp text'i result'a koymalı",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_rag_tool_returns_chunks",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 5.3: list_tasks tool returns existing tasks via the agent loop
    try:
        store = jarvis.JarvisStore.fresh()
        store.tasks.add_task("Önceden eklenmiş görev")

        client = _make_mock_client(chat_scripts=[
            _make_chat(tool_calls=[
                _make_tc("c1", "list_tasks", {"done": False}),
            ]),
            _make_chat(content="Bekleyen 1 görevin var."),
        ])
        answer = _run_async(jarvis.run_jarvis("Görevlerimi göster", store, client))

        if len(client._chat_log) < 2:
            g.add(TestResult(
                id="test_list_tasks_via_agent",
                status="failed",
                input='run_jarvis -> list_tasks tool',
                expected="2 chat calls",
                actual=f"got {len(client._chat_log)}",
                hint="Tool çağrısı sonrası ikinci chat call yapılmalı",
            ))
        else:
            tool_blob = "\n".join(
                str(m.get("content", "")) for m in client._chat_log[1]["messages"]
                if m.get("role") == "tool"
            )
            if "Önceden eklenmiş görev" in tool_blob:
                g.add(TestResult(id="test_list_tasks_via_agent", status="passed"))
            else:
                g.add(TestResult(
                    id="test_list_tasks_via_agent",
                    status="failed",
                    input='list_tasks tool with done=False',
                    expected='task title appears in tool result',
                    actual=f"blob: {tool_blob[:100]}",
                    hint="list_tasks handler store.tasks.list_tasks(done=...) çağırıp result'a koymalı",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_list_tasks_via_agent",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))
