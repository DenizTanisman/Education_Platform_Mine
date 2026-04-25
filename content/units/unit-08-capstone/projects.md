# Modül 8 — Capstone: Mini Jarvis

## Amaç

Kursun finalindesin. M0-M7'de öğrendiğin **her şeyi tek bir projede
birleştireceksin**. Mini Jarvis — kullanıcının görevlerini, tercihlerini
ve dokümanlarını yöneten, gerçek anlamda akıllı bir kişisel asistan.

> Bu sadece bir test değil — **bağımsız bir AI uygulaması inşa edebildiğinin
> kanıtı**. Buradaki kodu LinkedIn portfolyona koyacaksın, GitHub'da yıldız
> alacaksın, mülakatlarda anlatacaksın.

---

## Ne Birleşiyor?

| Modül | Capstone'a getirdiği |
|---|---|
| M0 | Disiplinli kod, tip hint, custom exception, docstring |
| M1 | SQLite görev listesi (TaskStore) |
| M2 | retry & error handling pattern |
| M3 | Async paralel tool execution (asyncio.gather) |
| M4 | Pydantic schema'lar (tool input validation) |
| M5 | Tool registry + agent loop |
| M6 | Memory (facts + conversation) + cosine similarity |
| M7 | RAG: chunking + embedding + retrieval |

Her birinin pattern'i koruluyor, sadece tek dosyada **`jarvis.py`** içinde
birleşiyor.

---

## Ön Hazırlık

```bash
mkdir m08-final && cd m08-final

python -m venv venv
source venv/bin/activate

cat > requirements.txt << EOF
openai>=1.50
pydantic>=2.5
python-dotenv>=1.0
EOF

pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-proj-..." > .env
echo ".env" >> .gitignore
```

---

## Görev Tanımı

`jarvis.py` adında **tek bir dosya** oluştur. İçinde:

### Veri yapıları

- `Chunk` dataclass (M7'den)
- `Task` dataclass (id, title, done)
- `MemoryStore` dataclass (facts + conversation, M6'dan)
- `RAGStore` dataclass (chunks list, M7'den)
- `TaskStore` class (SQLite-backed, M1'den)
- `JarvisStore` dataclass — **composite**: memory + rag + tasks

### 6 Pydantic input schema

1. `RememberFactInput` (key, value)
2. `RecallFactInput` (key)
3. `SearchMemoryInput` (query)
4. `AddTaskInput` (title)
5. `ListTasksInput` (done: Optional[bool])
6. `SearchDocumentsInput` (query)

### Tool altyapısı

- `Tool` dataclass (M5'ten)
- `ToolRegistry` class (M5'ten)
- `build_jarvis_registry(store, client)` — 6 tool'u kaydeden fabrika

### Yardımcı fonksiyonlar

- `cosine_similarity(a, b)` (M6'dan kopya)
- `get_embedding(text, client)` async (M6'dan)
- `chunk_text(text, ...)` (M7'den)

### Ana fonksiyonlar

- `ingest_document_into(text, source, store, client)` async — M7 pipeline
- `run_jarvis(user_message, store, client, max_iters=6)` async — M5 + M6 birleşimi

### Exception

- `JarvisError`

### CLI

```python
parser.add_argument("--message", help="Jarvis'e mesaj")
parser.add_argument("--ingest", help="Doküman dosyası")
```

---

## `JarvisStore` Mimarisi

```python
@dataclass
class JarvisStore:
    memory: MemoryStore = field(default_factory=MemoryStore)
    rag: RAGStore = field(default_factory=RAGStore)
    tasks: TaskStore = field(default_factory=lambda: TaskStore(":memory:"))

    @classmethod
    def fresh(cls):
        return cls()
```

Tek bir store, üç alt-store. `store.memory.recall_fact(...)`,
`store.tasks.add_task(...)`, `store.rag.search(...)` — hepsi temiz API.

---

## `TaskStore` (SQLite, M1'den)

```python
class TaskStore:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done  INTEGER NOT NULL DEFAULT 0
            );
        """)
        self.conn.commit()

    def add_task(self, title: str) -> Task:
        cursor = self.conn.execute(
            "INSERT INTO tasks (title, done) VALUES (?, 0)",
            (title.strip(),),
        )
        self.conn.commit()
        return Task(id=cursor.lastrowid, title=title.strip(), done=False)

    def list_tasks(self, done: Optional[bool] = None) -> list[Task]:
        if done is None:
            rows = self.conn.execute("SELECT ... FROM tasks ORDER BY id").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT ... FROM tasks WHERE done=? ORDER BY id",
                (1 if done else 0,),
            ).fetchall()
        return [Task(id=r["id"], title=r["title"], done=bool(r["done"])) for r in rows]
```

> **Güvenlik:** `?` placeholder ile parameterized query — string concat YOK.

---

## `build_jarvis_registry` (kalp)

Closure pattern ile her tool handler'ı `store` ve `client`'a bağlanır:

```python
def build_jarvis_registry(store: JarvisStore, client) -> ToolRegistry:
    registry = ToolRegistry()

    # Memory tools
    async def _remember(input: RememberFactInput) -> dict:
        store.memory.remember_fact(input.key, input.value)
        return {"status": "saved", "key": input.key, "value": input.value}

    async def _recall(input: RecallFactInput) -> dict:
        v = store.memory.recall_fact(input.key)
        return {"key": input.key, "found": v is not None, "value": v}

    async def _search_memory(input: SearchMemoryInput) -> dict:
        # Embed query, score each user message in conversation
        ...

    # Task tools
    async def _add_task(input: AddTaskInput) -> dict:
        task = store.tasks.add_task(input.title)
        return {"id": task.id, "title": task.title, "status": "added"}

    async def _list_tasks(input: ListTasksInput) -> dict:
        tasks = store.tasks.list_tasks(done=input.done)
        return {"count": len(tasks), "tasks": [...]}

    # RAG tool
    async def _search_documents(input: SearchDocumentsInput) -> dict:
        if not store.rag.chunks:
            return {"results": []}
        query_emb = await get_embedding(input.query, client)
        retrieved = store.rag.search(query_emb, top_k=3)
        return {"results": [...]}

    # Register all 6
    registry.register(Tool("remember_fact", ..., _remember))
    # ... 5 more

    return registry
```

---

## `run_jarvis` (orkestratör)

```python
async def run_jarvis(user_message, store, client, max_iters=6):
    if not user_message.strip():
        raise ValueError("user_message must not be empty")

    registry = build_jarvis_registry(store, client)
    tools = registry.to_openai_list()

    # System prompt + facts hint + indexed summary
    facts_summary = "\n".join(f"- {k}: {v}" for k, v in store.memory.facts.items())
    indexed_summary = f"İndekslenmiş: {len(store.rag.chunks)} chunk"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Hatırlananlar:\n{facts_summary}\n\n{indexed_summary}"},
        *store.memory.conversation[-20:],
        {"role": "user", "content": user_message.strip()},
    ]

    # M5 agent loop (try/except + AgentError, parallel tool exec, etc.)
    for iteration in range(max_iters):
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            answer = msg.content.strip()
            store.memory.conversation.append({"role": "user", "content": user_message.strip()})
            store.memory.conversation.append({"role": "assistant", "content": answer})
            return answer

        # Append assistant tool_call message + execute tools in parallel
        # (M5 + M6 pattern)
        ...

    raise JarvisError(f"Did not finish within {max_iters} iters")
```

---

## Kullanım Örnekleri

### Senaryo 1: Bilgi ezberleme + görev ekleme (multi-tool turn)
```bash
python jarvis.py --message "Adım Deniz, ödevimi listeye ekle"
# Jarvis: remember_fact("name", "Deniz") + add_task("ödevimi yap") + final
# {"answer": "Tamam Deniz, adını kaydettim ve görevini ekledim."}
```

### Senaryo 2: Doküman ingest + soru
```bash
python jarvis.py --ingest readme.md
# {"status": "ingested", "chunks_added": 5}

python jarvis.py --message "RAG nedir? Dokümana göre cevapla"
# Jarvis: search_documents("RAG nedir?") → final answer with citation
# {"answer": "Dokümana göre RAG retrieval-augmented generation demek (kaynak: chunk #2)"}
```

### Senaryo 3: Görev listeleme
```bash
python jarvis.py --message "Bekleyen görevlerim neler?"
# Jarvis: list_tasks(done=False) → final
# {"answer": "Bekleyen 3 görevin var: 1. ödevimi yap, 2. ..."}
```

---

## Test Edilecek Davranışlar

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| Çekirdek yapı | 3 | JarvisStore composite, TaskStore CRUD, MemoryStore facts |
| Doküman boru hattı | 3 | Chunking, ingest pipeline, empty rejection |
| Tool registry | 3 | 6 tools registered, OpenAI format, registry routing |
| Agent loop | 3 | Single-iter response, multi-tool parallel, empty rejected |
| Bütünleşme | 3 | Facts hint to LLM, RAG tool returns chunks, list_tasks via agent |

**Toplam:** 15 test (kursun en yoğunu).

---

## Mock Stratejisi

3 ayrı mock kanal:
- `chat.completions.create` — M5+ scripted responses
- `embeddings.create` — M6+ vektör script veya sabit
- TaskStore — `:memory:` SQLite, gerçek dosya değil

```python
client = _make_mock_client(
    chat_scripts=[...],
    emb_scripts=[...],
    default_emb=[0.5] * 1536,
)
```

---

## Teslim Formatı

```
solution.zip
├── jarvis.py
└── requirements.txt
```

`*.json`, `*.db`, `__pycache__`, `.env` koyma.

---

## İpuçları

### Tek dosya neden?

Capstone modüler olabilirdi (5-6 dosya) ama eğitim için tek dosya **okunaklı**:
yukarıdan aşağı okuyunca tüm yapıyı görebilirsin. Production'da bunu bölersin.

### `JarvisStore.fresh()` neden classmethod?

Test'ler ve CLI iki ayrı yerden boş store yaratıyor. `fresh()` tek tip bir
factory. M6'daki `MemoryStore.load(path)` pattern'i ama dosya'sız.

### `:memory:` SQLite

Test'lerde dosya yaratılmasın diye `TaskStore(":memory:")` default. CLI'da
da varsayılan — process bittiğinde tasks kaybolur. Production'da
`TaskStore("/var/data/tasks.db")` gerekir.

### `search_memory` tool maliyeti

Her query için tüm conversation'daki user message'ları tek tek embed ediyor.
**Pahalı**. Production'da:
1. Conversation'ı **save** ederken her message'ı embed et
2. Embedding'leri saklа (M6 pattern)
3. Search sırasında sadece query embed et

Capstone'da basit tutuyoruz çünkü conversation kısa (max 20 message).

### Persistence?

CLI'da her process bittiğinde her şey gider. Production için:
- `MemoryStore` → `M6 ile birleştir`, JSON file
- `RAGStore` → JSON file (M7 gibi)
- `TaskStore` → SQLite dosyası

Capstone'da test'ler için minimumda tutuyoruz.

---

## Anti-pattern Uyarıları

- ❌ **Her tool için yeni Pydantic schema unutmak** — input validation kaybolur
- ❌ **JarvisStore'u global state olarak kullanmak** — DI ile geç, test'lenebilir
- ❌ **Closure içinde `store` yerine global** — handler'lar çoklu tester'a uyumsuz olur
- ❌ **Conversation'ı sınırsız büyütmek** — `[-20:]` ile sınırla, context window'u dolmasın
- ❌ **TaskStore SQL'de string concat** — parameterized query KESİN, M0 güvenlik kuralı
- ❌ **`max_iters=20` koymak** — agent çok uzun çalışırsa muhtemelen yanlış prompt; 5-6 yeter

---

## Production'a Geçiş Yol Haritası

Capstone bir prototip. Production'da eklenmesi gereken:

| Konu | Çözüm |
|---|---|
| Persistence | JarvisStore.load/save (JSON + SQLite path) |
| Vector DB | Pinecone/Chroma/pgvector (linear scan yerine) |
| Auth | API key başına ayrı JarvisStore |
| Cost tracking | Her API call'da token sayma + DB'ye kaydetme |
| Rate limit | Exponential backoff + queue |
| Streaming | Token-token cevap (chat.completions.create stream=True) |
| Observability | OpenTelemetry, LangSmith, Langfuse |
| Tool error retry | Tool fail olunca model'e geri verip tekrar denemesini iste |
| Memory summarization | Eski conversation'ları LLM ile özetle |
| Document ingest UI | Drag-drop upload, progress bar |

Bu liste capstone'un ne kadar hafif olduğunu gösteriyor — production gerçek
sistem için 10x daha fazla iş var. Ama **temel pattern aynı**, capstone'u
anlayan biri production'ı 1-2 ay içinde yazabilir.

---

## Önerilen Kaynaklar

- [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)
- [LlamaIndex](https://docs.llamaindex.ai/)
- [OpenAI Cookbook — Agentic patterns](https://github.com/openai/openai-cookbook)
- [Awesome AI Agents](https://github.com/e2b-dev/awesome-ai-agents)

---

## Kursu Bitiriyorsun

Bu son modül. Buraya kadar geldiysen:
- 8 modül × ~12 test = ~99 test geçtin
- 8 farklı patterns öğrendin: Python disiplini → SQLite → HTTP/JSON → LLM SDK →
  Pydantic → tool calling → memory → RAG → integration
- Tek dosyalık prototip değil, **mimariyi** anladın

Sonraki adım: kendi projeni yap. İlk fikir: capstone'u **kendi domain'inde**
kişiselleştir. Müzik öneren Jarvis, kod review yapan Jarvis, futbol istatistik
chat botu...

Bol şanslar.
