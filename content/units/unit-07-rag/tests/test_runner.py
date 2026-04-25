"""
M7 — Final test runner.

Tests the RAG system from rag.py.

Test groups (must match unit.yaml):
  - "Chunking"               — text splitting with overlap
  - "Indeks ve arama"        — RAGStore CRUD, search ranking, persistence
  - "Embedding boru hattı"   — embed_chunks parallel, ingest_document end-to-end
  - "RAG cevaplama"          — answer_with_rag retrieve+generate, citations
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

    g1 = TestGroup(name="Chunking")
    _test_chunking(g1)
    groups.append(g1)

    g2 = TestGroup(name="Indeks ve arama")
    _test_index_and_search(g2)
    groups.append(g2)

    g3 = TestGroup(name="Embedding boru hattı")
    _test_embedding_pipeline(g3)
    groups.append(g3)

    g4 = TestGroup(name="RAG cevaplama")
    _test_rag_answer(g4)
    groups.append(g4)

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_import(g: TestGroup, test_id: str):
    try:
        import rag
        return rag
    except Exception as e:
        g.add(TestResult(
            id=test_id,
            status="errored",
            detail=f"rag.py içe aktarılamadı: {e.__class__.__name__}: {e}",
            hint="Dosya adı rag.py olmalı; chunk_text, RAGStore, ingest_document, answer_with_rag tanımlı mı?",
        ))
        return None


def _make_emb_response(vec):
    item = MagicMock()
    item.embedding = vec
    resp = MagicMock()
    resp.data = [item]
    return resp


def _make_chat_response(content):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_mock_client(embeddings_script=None, chat_response=None):
    """Mock async client.
    embeddings_script: list of vectors returned in order, or single vector for all calls.
    chat_response: content string to return on chat.completions.create.
    """
    client = MagicMock()
    client._embed_log = []
    client._chat_log = []

    if isinstance(embeddings_script, list) and embeddings_script and isinstance(embeddings_script[0], list):
        emb_iter = iter(embeddings_script)
        async def fake_emb(**kwargs):
            client._embed_log.append(kwargs)
            try:
                return _make_emb_response(next(emb_iter))
            except StopIteration:
                return _make_emb_response([0.0] * 3)
    else:
        # constant vector
        const = embeddings_script if embeddings_script else [0.5, 0.5, 0.0]
        async def fake_emb(**kwargs):
            client._embed_log.append(kwargs)
            return _make_emb_response(const)

    async def fake_chat(**kwargs):
        client._chat_log.append(kwargs)
        return _make_chat_response(chat_response or "default mock answer")

    client.embeddings.create = fake_emb
    client.chat.completions.create = fake_chat
    return client


def _run_async(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Group 1 — Chunking
# ---------------------------------------------------------------------------

def _test_chunking(g: TestGroup) -> None:
    rag = _safe_import(g, "test_basic_chunking")
    if rag is None:
        return

    # 1.1: Long text produces multiple chunks of roughly chunk_size
    try:
        text = "abcdefghij" * 100  # 1000 chars
        chunks = rag.chunk_text(text, chunk_size=300, chunk_overlap=50)
        # Step = 250, so first 4 starts at 0, 250, 500, 750
        ok = (
            len(chunks) >= 3
            and len(chunks[0]) <= 300
            and len(chunks[0]) >= 100
        )
        if ok:
            g.add(TestResult(id="test_basic_chunking", status="passed"))
        else:
            g.add(TestResult(
                id="test_basic_chunking",
                status="failed",
                input='chunk_text(1000-char text, size=300, overlap=50)',
                expected="3+ chunks, each <= 300 chars",
                actual=f"len={len(chunks)}, first={len(chunks[0]) if chunks else 0}",
                hint="walking-window: start=0, step=size-overlap, take size chars",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_basic_chunking",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.2: Short text returns single chunk
    try:
        text = "merhaba dünya"  # 13 chars
        chunks = rag.chunk_text(text, chunk_size=300)
        if len(chunks) == 1 and chunks[0] == "merhaba dünya":
            g.add(TestResult(id="test_short_text_single_chunk", status="passed"))
        else:
            g.add(TestResult(
                id="test_short_text_single_chunk",
                status="failed",
                input='chunk_text("merhaba dünya", chunk_size=300)',
                expected='["merhaba dünya"]',
                actual=repr(chunks),
                hint="text uzunluğu chunk_size'dan kısaysa tek elemanlı liste döndür",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_short_text_single_chunk",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 1.3: Overlap validation: overlap >= chunk_size should raise
    try:
        try:
            rag.chunk_text("test text", chunk_size=10, chunk_overlap=15)
            g.add(TestResult(
                id="test_overlap_validation",
                status="failed",
                input='chunk_text(..., chunk_size=10, chunk_overlap=15)',
                expected="ValueError",
                actual="No exception",
                hint="chunk_overlap >= chunk_size durumu sonsuz döngüye yol açar; ValueError fırlat",
            ))
        except ValueError:
            g.add(TestResult(id="test_overlap_validation", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_overlap_validation",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 2 — Index and search
# ---------------------------------------------------------------------------

def _test_index_and_search(g: TestGroup) -> None:
    rag = _safe_import(g, "test_store_search_ranks")
    if rag is None:
        return

    # 2.1: search returns chunks ordered by similarity descending
    try:
        store = rag.RAGStore()
        store.add_chunks([
            rag.Chunk(text="alpha", source="a.md", chunk_index=0, embedding=[1.0, 0.0, 0.0]),
            rag.Chunk(text="beta",  source="a.md", chunk_index=1, embedding=[0.0, 1.0, 0.0]),
            rag.Chunk(text="gamma", source="a.md", chunk_index=2, embedding=[0.9, 0.1, 0.0]),
        ])
        results = store.search([1.0, 0.0, 0.0], top_k=2)
        # Each result should be (chunk, score) — accept tuple or dict with chunk
        ok = (
            len(results) == 2
            and (results[0][0].text if isinstance(results[0], tuple) else results[0]["chunk"].text) == "alpha"
        )
        if ok:
            g.add(TestResult(id="test_store_search_ranks", status="passed"))
        else:
            g.add(TestResult(
                id="test_store_search_ranks",
                status="failed",
                input='store.search([1,0,0], top_k=2) on 3 chunks',
                expected='top result is "alpha" (score 1.0)',
                actual=f"got {results}",
                hint="search cosine score'a göre azalan sırada sırala, top_k kadar döndür",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_store_search_ranks",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.2: persistence round-trip
    try:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)

        store1 = rag.RAGStore(path=path)
        store1.add_chunks([
            rag.Chunk(text="İstanbul'da", source="x.md", chunk_index=0, embedding=[0.1, 0.2, 0.3]),
        ])
        store1.save()

        store2 = rag.RAGStore.load(path)
        ok = (
            len(store2.chunks) == 1
            and store2.chunks[0].text == "İstanbul'da"
            and store2.chunks[0].source == "x.md"
            and store2.chunks[0].chunk_index == 0
            and store2.chunks[0].embedding == [0.1, 0.2, 0.3]
        )
        if ok:
            g.add(TestResult(id="test_persistence_roundtrip", status="passed"))
        else:
            g.add(TestResult(
                id="test_persistence_roundtrip",
                status="failed",
                input='RAGStore save then load',
                expected="chunk preserved with all fields",
                actual=f"got {len(store2.chunks)} chunks, first={store2.chunks[0] if store2.chunks else None}",
                hint="JSON encoding/decoding tüm Chunk alanlarını korusun (text/source/chunk_index/embedding)",
            ))
        os.unlink(path)
    except Exception as e:
        g.add(TestResult(
            id="test_persistence_roundtrip",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 2.3: add_chunks rejects chunks without embeddings
    try:
        store = rag.RAGStore()
        bad = rag.Chunk(text="no emb", source="x.md", chunk_index=0, embedding=[])
        try:
            store.add_chunks([bad])
            g.add(TestResult(
                id="test_no_embedding_rejected",
                status="failed",
                input='add_chunks with empty-embedding chunk',
                expected="ValueError",
                actual="No exception",
                hint="add_chunks içinde her chunk için embedding boş olmamalı, yoksa ValueError",
            ))
        except ValueError:
            g.add(TestResult(id="test_no_embedding_rejected", status="passed"))
    except Exception as e:
        g.add(TestResult(
            id="test_no_embedding_rejected",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 3 — Embedding pipeline
# ---------------------------------------------------------------------------

def _test_embedding_pipeline(g: TestGroup) -> None:
    rag = _safe_import(g, "test_embed_chunks_parallel")
    if rag is None:
        return

    # 3.1: embed_chunks calls API once per chunk and returns list of vectors
    try:
        client = _make_mock_client(embeddings_script=[0.1, 0.2, 0.3])
        chunks = ["a", "b", "c"]
        result = _run_async(rag.embed_chunks(chunks, client))
        if (
            isinstance(result, list)
            and len(result) == 3
            and all(isinstance(v, list) for v in result)
            and len(client._embed_log) == 3
        ):
            g.add(TestResult(id="test_embed_chunks_parallel", status="passed"))
        else:
            g.add(TestResult(
                id="test_embed_chunks_parallel",
                status="failed",
                input='embed_chunks(["a","b","c"])',
                expected="3 vectors returned, 3 API calls",
                actual=f"len={len(result) if isinstance(result, list) else '?'}, calls={len(client._embed_log)}",
                hint="Her chunk için embeddings.create çağır, asyncio.gather ile paralel",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_embed_chunks_parallel",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.2: ingest_document chunks + embeds + adds to store
    try:
        client = _make_mock_client(embeddings_script=[0.5, 0.5, 0.0])
        store = rag.RAGStore()
        # Long enough to produce 2+ chunks at chunk_size=200
        text = ("Bu bir test belgesidir. " * 30)  # ~720 chars
        count = _run_async(rag.ingest_document(
            text, source="test.md", store=store, client=client,
            chunk_size=200, chunk_overlap=20,
        ))
        if count >= 2 and len(store.chunks) == count:
            # All chunks should have source set
            sources = {c.source for c in store.chunks}
            indices = [c.chunk_index for c in store.chunks]
            if sources == {"test.md"} and indices == list(range(count)):
                g.add(TestResult(id="test_ingest_document", status="passed"))
            else:
                g.add(TestResult(
                    id="test_ingest_document",
                    status="failed",
                    input='ingest_document with 720-char text',
                    expected="chunks have source='test.md' and sequential chunk_index",
                    actual=f"sources={sources}, indices={indices}",
                    hint="Her chunk source'u parametre olarak set edilmeli, chunk_index 0,1,2... olmalı",
                ))
        else:
            g.add(TestResult(
                id="test_ingest_document",
                status="failed",
                input='ingest_document(720 chars, chunk_size=200, overlap=20)',
                expected="2+ chunks added to store",
                actual=f"count={count}, store has {len(store.chunks)}",
                hint="ingest_document chunk_text + embed_chunks + store.add_chunks zinciri olmalı",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_ingest_document",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 3.3: empty text rejected
    try:
        client = _make_mock_client()
        store = rag.RAGStore()
        try:
            _run_async(rag.ingest_document("", source="x.md", store=store, client=client))
            g.add(TestResult(
                id="test_ingest_empty_rejected",
                status="failed",
                input='ingest_document("", source="x.md")',
                expected="ValueError",
                actual="No exception",
                hint="Boş text için ValueError fırlat (API çağrısı yapma)",
            ))
        except ValueError:
            if not client._embed_log:
                g.add(TestResult(id="test_ingest_empty_rejected", status="passed"))
            else:
                g.add(TestResult(
                    id="test_ingest_empty_rejected",
                    status="failed",
                    input='ingest_document("")',
                    expected="ValueError BEFORE embedding API call",
                    actual=f"ValueError raised but {len(client._embed_log)} API calls happened",
                    hint="Validation kontrolünü embed_chunks/embeddings.create çağrılarından önce yap",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_ingest_empty_rejected",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))


# ---------------------------------------------------------------------------
# Group 4 — RAG answer
# ---------------------------------------------------------------------------

def _test_rag_answer(g: TestGroup) -> None:
    rag = _safe_import(g, "test_answer_returns_dict_with_citations")
    if rag is None:
        return

    # 4.1: answer_with_rag returns {answer, citations} after retrieve + chat
    try:
        store = rag.RAGStore()
        store.add_chunks([
            rag.Chunk(text="RAG retrieval-augmented generation demek.",
                      source="doc.md", chunk_index=0, embedding=[1.0, 0.0, 0.0]),
            rag.Chunk(text="Embedding ile benzerlik ölçülür.",
                      source="doc.md", chunk_index=1, embedding=[0.0, 1.0, 0.0]),
        ])
        client = _make_mock_client(
            embeddings_script=[1.0, 0.0, 0.0],  # query embedding
            chat_response="RAG retrieval-augmented generation demek (kaynak: chunk #0, dosya: doc.md)",
        )
        result = _run_async(rag.answer_with_rag("RAG nedir?", store, client, top_k=2))

        ok = (
            isinstance(result, dict)
            and "answer" in result
            and "citations" in result
            and isinstance(result["citations"], list)
            and len(result["citations"]) >= 1
            and "RAG" in result["answer"]
        )
        if ok:
            g.add(TestResult(id="test_answer_returns_dict_with_citations", status="passed"))
        else:
            g.add(TestResult(
                id="test_answer_returns_dict_with_citations",
                status="failed",
                input='answer_with_rag("RAG nedir?", store, client, top_k=2)',
                expected='{"answer": ..., "citations": [...]}',
                actual=repr(result)[:200],
                hint="answer_with_rag {answer, citations} dict döndürmeli; citations top_k chunk için kaynak/skor",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_answer_returns_dict_with_citations",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.2: empty store yields a graceful response (no chat call)
    try:
        store = rag.RAGStore()
        client = _make_mock_client(
            embeddings_script=[1.0, 0.0, 0.0],
            chat_response="should not be called",
        )
        result = _run_async(rag.answer_with_rag("any question", store, client))
        if (
            isinstance(result, dict)
            and "answer" in result
            and result["citations"] == []
            and len(client._chat_log) == 0
        ):
            g.add(TestResult(id="test_empty_store_graceful", status="passed"))
        else:
            g.add(TestResult(
                id="test_empty_store_graceful",
                status="failed",
                input='answer_with_rag on empty store',
                expected='{"answer": "...", "citations": []}, no chat call',
                actual=f"result={result}, chat_calls={len(client._chat_log)}",
                hint="store.chunks boşsa chat çağırma; bilgilendirici cevap ve boş citations döndür",
            ))
    except Exception as e:
        g.add(TestResult(
            id="test_empty_store_graceful",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))

    # 4.3: chat prompt includes retrieved chunk text as context
    try:
        store = rag.RAGStore()
        store.add_chunks([
            rag.Chunk(text="UNIQUE_PHRASE_XYZ123",
                      source="doc.md", chunk_index=0, embedding=[1.0, 0.0, 0.0]),
        ])
        client = _make_mock_client(
            embeddings_script=[1.0, 0.0, 0.0],
            chat_response="cevap",
        )
        _run_async(rag.answer_with_rag("test", store, client))

        if not client._chat_log:
            g.add(TestResult(
                id="test_context_passed_to_llm",
                status="errored",
                detail="No chat call recorded",
                hint="answer_with_rag chat.completions.create çağırmalı",
            ))
        else:
            messages = client._chat_log[0]["messages"]
            # Concatenate all message contents to search for our marker
            blob = "\n".join(
                str(m.get("content", "")) for m in messages
            )
            if "UNIQUE_PHRASE_XYZ123" in blob:
                g.add(TestResult(id="test_context_passed_to_llm", status="passed"))
            else:
                g.add(TestResult(
                    id="test_context_passed_to_llm",
                    status="failed",
                    input='answer_with_rag with chunk text="UNIQUE_PHRASE_XYZ123"',
                    expected="chunk text appears in messages sent to LLM",
                    actual=f"messages: {messages}",
                    hint="Retrieved chunk'ları context olarak prompt'a ekle (system veya user mesajında)",
                ))
    except Exception as e:
        g.add(TestResult(
            id="test_context_passed_to_llm",
            status="errored",
            detail=f"{e.__class__.__name__}: {e}",
        ))
