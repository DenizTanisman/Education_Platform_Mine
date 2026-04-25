# Modül 7 — Final Görevi

## Amaç

M6'da basit semantic memory yaptın — kullanıcının attığı her mesajı embed
edip benzer olanları aradın. Bu **mini-RAG** idi: scope dar, chunk'lar
küçük (cümle boyu), kaynak yok.

Şimdi **gerçek RAG** sistemi yazacaksın. Kullanıcı bir doküman verir
(README, kitap bölümü, dokümantasyon), sen onu **chunklara bölüp embed
edip** indeksliyorsun. Sonra dokümandan sorular cevaplıyorsun
**citation'larla**: "şu cevap chunk #3'ten geliyor, kaynak: readme.md".

> RAG = **Retrieval + Augmented Generation**. Üretici yapay zekanın
> "hallucination" sorununu çözmek için kullanılan en yaygın production
> tekniği.

---

## Ön Hazırlık

```bash
mkdir m07-final && cd m07-final

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
echo "rag.json" >> .gitignore
```

---

## Görev Tanımı

`rag.py` adında **tek bir dosya** oluştur. İçinde:

- 1 `cosine_similarity(a, b)` (M6'dan kopya)
- 1 `get_embedding(text, client)` async (M6'dan kopya)
- 1 `chunk_text(text, chunk_size=800, chunk_overlap=100)` — yeni
- 1 `embed_chunks(chunks, client)` async paralel — yeni
- 1 `Chunk` dataclass — text, source, chunk_index, embedding
- 1 `RAGStore` dataclass — load, save, add_chunks, search
- 1 `ingest_document(text, source, store, client)` async — pipeline
- 1 `retrieve(query, store, client, top_k=4)` async — query → chunks
- 1 `answer_with_rag(query, store, client)` async — full pipeline
- 1 `RAGError` exception
- CLI

---

### `chunk_text` (kalp)

```python
def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[str]:
    if not text.strip():
        return []
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap < chunk_size olmalı")

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    step = chunk_size - chunk_overlap
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += step
    return chunks
```

**Walking-window algoritması:**
- Adım 1: index 0'dan `chunk_size` karakter al → chunk 1
- Adım 2: `chunk_size - chunk_overlap` ileri kay → chunk 2
- Sonu görünce dur

**Örnek:** 1000 karakter, `chunk_size=300, overlap=50` → adım 250
- Chunk 0: `[0:300]`
- Chunk 1: `[250:550]`  (50 karakter chunk 0 ile çakışıyor)
- Chunk 2: `[500:800]`
- Chunk 3: `[750:1000]`

> **Niye overlap?** Bir cümle iki chunk'a bölünürse bağlamı kaybolur. Overlap
> ile sınır cümlesi iki chunk'ta da kısmen tekrar eder, retrieval'da
> en az birinde tam yakalanır.

---

### `Chunk` ve `RAGStore`

```python
@dataclass
class Chunk:
    text: str
    source: str          # dosya yolu veya doc ID
    chunk_index: int     # 0-based pozisyon
    embedding: list[float] = field(default_factory=list)

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(text=..., source=..., chunk_index=..., embedding=...)


@dataclass
class RAGStore:
    path: Optional[str] = None
    chunks: list[Chunk] = field(default_factory=list)

    @classmethod
    def load(cls, path): ...   # missing file = fresh store

    def save(self): ...        # path None ise no-op (M6 pattern)

    def add_chunks(self, chunks):
        # Validate: her chunk'ın embedding'i olmalı
        for c in chunks:
            if not c.embedding:
                raise ValueError(...)
        self.chunks.extend(chunks)

    def search(self, query_embedding, top_k=4):
        # Return [(chunk, score), ...] descending
        scored = [(c, cosine_similarity(query_embedding, c.embedding))
                  for c in self.chunks]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
```

**JSON disk formatı:**
```json
{
  "chunks": [
    {
      "text": "RAG retrieval-augmented...",
      "source": "readme.md",
      "chunk_index": 0,
      "embedding": [0.1, -0.05, 0.2, ...]
    }
  ]
}
```

---

### `ingest_document` (pipeline)

```python
async def ingest_document(text, source, store, client,
                           chunk_size=800, chunk_overlap=100):
    if not text.strip():
        raise ValueError("text must not be empty")
    if not source.strip():
        raise ValueError("source must not be empty")

    # 1. Chunk
    pieces = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not pieces:
        return 0

    # 2. Embed (parallel)
    embeddings = await embed_chunks(pieces, client)

    # 3. Build Chunk objects + add to store
    chunks = [
        Chunk(text=piece, source=source, chunk_index=i, embedding=emb)
        for i, (piece, emb) in enumerate(zip(pieces, embeddings))
    ]
    store.add_chunks(chunks)
    return len(chunks)
```

`embed_chunks` M3'teki `summarize_many` pattern'i ama her birine
`get_embedding` çağırıyor.

---

### `answer_with_rag` (full pipeline)

```python
async def answer_with_rag(query, store, client, top_k=4):
    if not query.strip():
        raise ValueError("query must not be empty")

    # 1. Retrieve
    retrieved = await retrieve(query, store, client, top_k=top_k)

    # 2. Boş store → graceful response (chat ÇAĞIRMA)
    if not retrieved:
        return {
            "answer": "Henüz indekslenmiş bir doküman yok, cevap veremiyorum.",
            "citations": [],
        }

    # 3. Build context block
    context = "\n\n".join(
        f"--- chunk #{c.chunk_index} (dosya: {c.source}, "
        f"benzerlik: {score:.3f}) ---\n{c.text}"
        for c, score in retrieved
    )

    # 4. Augmented prompt
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Kaynak parçalar:\n\n{context}\n\nSoru: {query}"},
        ],
    )

    # 5. Citations
    citations = [
        {"source": c.source, "chunk_index": c.chunk_index, "score": round(s, 3)}
        for c, s in retrieved
    ]
    return {
        "answer": response.choices[0].message.content.strip(),
        "citations": citations,
    }
```

**System prompt önerisi:**
```
Sen verilen kaynak parçalardan yararlanarak soruları cevaplayan bir
asistansın. Sadece sağlanan kaynaklara dayan, bilmediğin şeyi uydurma.
Cevabının sonunda kaynak parçaları belirt: (kaynak: chunk #N, dosya: ...).
Cevaplarını Türkçe ver.
```

---

## Kullanım Örneği

```bash
# Bir markdown dosyası ingest et
cat > readme.md << 'EOF'
# Projemiz

RAG sistemleri büyük dokümanlardan bilgi çekmek için kullanılır.
Embedding ile semantic similarity ölçülür.
Cosine similarity 0 ile 1 arasında değer döndürür.

# Kurulum

pip install openai pydantic.
Ortam değişkeni OPENAI_API_KEY ayarla.
EOF

python rag.py --ingest readme.md --store rag.json
# {"status": "ingested", "chunks_added": 1, "total_chunks": 1}

# Soru sor
python rag.py --query "Cosine similarity hangi aralıkta değer döndürür?" --store rag.json
# {
#   "answer": "0 ile 1 arasında değer döndürür (kaynak: chunk #0, dosya: readme.md)",
#   "citations": [{"source": "readme.md", "chunk_index": 0, "score": 0.84}]
# }
```

---

## Test Edilecek Davranışlar

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| Chunking | 3 | Walking-window, kısa text, overlap validation |
| Indeks ve arama | 3 | search ranking, persistence round-trip, no-embedding rejection |
| Embedding boru hattı | 3 | embed_chunks parallel, ingest_document end-to-end, empty rejection |
| RAG cevaplama | 3 | answer_with_rag dict shape, empty store graceful, context passed to LLM |

**Toplam:** 12 test.

---

## OpenAI vs Anthropic — RAG

RAG **provider'a bağımsız** bir teknik. İki SDK ile de çalışır:

| Aşama | OpenAI | Anthropic |
|---|---|---|
| Embedding | `text-embedding-3-small` (kendi) | OpenAI / Voyage / Cohere kullanır |
| Retrieval | Yerel (cosine) veya vector DB | Aynı |
| Augmented gen | `chat.completions.create` | `messages.create` (system ayrı param) |

Anthropic ekibi RAG için "Contextual Retrieval" diye bir gelişmiş teknik
yayınladı (2024) — chunk'a, hangi dokümandan geldiği bilgisini de ekleyerek
embed ediyor. Production iyileştirme.

---

## Teslim Formatı

```
solution.zip
├── rag.py
└── requirements.txt
```

`rag.json`, `__pycache__`, `.env`, `*.md` dosyaları ZIP'e koyma.

---

## İpuçları

### Chunk size nasıl seçilir?

| Chunk size | Avantaj | Dezavantaj |
|---|---|---|
| Küçük (200-400) | Hassas retrieval, az context kirliliği | Bağlam kaybı, çok fazla chunk |
| Orta (600-1000) | Dengeli — varsayılan | — |
| Büyük (1500+) | Az chunk, geniş bağlam | Retrieval bulanık, token maliyeti yüksek |

text-embedding-3-small max 8191 token alabilir (~32K karakter). 800 karakter
çok rahat aralık.

### Overlap nasıl seçilir?

%10-20 mantıklı. 800 chunk_size için 80-160 overlap. Aşırı = boşa embedding
hesaplama, eksik = sınır cümleleri kayıp.

### Top_k nasıl seçilir?

3-5 makul. Daha fazla = LLM gürültü ile boğulur. Daha az = ilgili chunk
kaçabilir.

### Smart chunking (production)

Karakter sayısı yerine **anlamlı bölünmeler** kullanın:
- Markdown → header'larda böl
- Code → fonksiyon sınırlarında
- HTML → DOM elementlerinde

Production'da `langchain-text-splitters` paketinde:
- `RecursiveCharacterTextSplitter` (char-aware)
- `MarkdownTextSplitter`
- `Language.PYTHON` syntax-aware

Eğitimde basit char-based çıkmak için yeterli, mantığı anlatmak için.

### Re-ranking (advanced)

Retrieval sonrası chunk'ları yeniden sıralamak için:
- Cohere rerank API
- Cross-encoder modeller (BGE-reranker)
- Sadece top-N tam embed → top-K'ı reranker'a sok

M8 capstone'da görebilirsiniz.

---

## Anti-pattern Uyarıları

- ❌ **Çok küçük chunk_size** (örn. 50) — bağlam kaybı, retrieval gürültülü
- ❌ **`chunk_overlap >= chunk_size`** — sonsuz döngü
- ❌ **Embedding'leri her sorguda yeniden hesaplamak** — pahalı, indeks kalıcı olsun
- ❌ **Chunk'a source bilgisi koymamak** — citation imkansız
- ❌ **LLM'e ham chunk text'i context olmadan vermek** — system prompt'ta "sadece kaynaklara dayan" demelisin
- ❌ **top_k=20** — bu kadar context LLM'i boğar, maliyet patlar

---

## Önerilen Kaynaklar

- [Anthropic — Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) — 2024 production tekniği
- [OpenAI Cookbook — RAG examples](https://github.com/openai/openai-cookbook/tree/main/examples)
- [LangChain RAG Tutorial](https://python.langchain.com/docs/tutorials/rag/)
- [LlamaIndex](https://www.llamaindex.ai/) — RAG'e adanmış framework
- [Pinecone Learning Center](https://www.pinecone.io/learn/) — production retrieval pattern'leri
