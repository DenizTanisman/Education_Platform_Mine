# Modül 6 — Final Görevi

## Amaç

M5'te agent yazdın, ama agent'ın **bellek yoktu** — her konuşma sıfırdan
başlıyordu. Şimdi **stateful agent** yapacaksın: kullanıcının adını
hatırlayan, tercihlerini saklayan, geçmiş konuşmalarda semantik arama
yapabilen bir asistan.

> Bu modülün en heyecanlı yanı: ilk kez **embedding** kullanacaksın.
> Yapay zekanın "anlam uzayı"na ilk dokunuş — RAG'in (M7) ön koşulu.

---

## Ön Hazırlık

```bash
mkdir m06-final && cd m06-final

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
echo "memory.json" >> .gitignore  # bellek dosyası
```

---

## Görev Tanımı

`assistant.py` adında **tek bir dosya** oluştur. İçinde:

- 1 vektör fonksiyonu: `cosine_similarity(a, b)`
- 1 async embedding fonksiyonu: `get_embedding(text, client)`
- 1 `MemoryStore` dataclass (load, save, CRUD)
- 3 Pydantic schema: `RememberFactInput`, `RecallFactInput`, `SearchMemoryInput`
- M5'in `Tool` ve `ToolRegistry` class'ları (kopya)
- 1 fabrika fonksiyonu: `build_memory_registry(store, client)` — 3 tool kaydeder
- 1 `AssistantError` exception
- 1 `run_assistant(user_message, client, store)` — ana giriş
- CLI

---

### Vektör matematik

#### `cosine_similarity(a, b)`

```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(...)
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

Sonuç [-1, 1] aralığında: 1 = identical, 0 = orthogonal, -1 = opposite.

> **NumPy ile değil mi?** NumPy hızlı ama bağımlılık. Eğitim için pure
> Python yeterli (1536 boyut için bile mikrosaniyeler). Production'da
> NumPy + scipy kullan.

#### `get_embedding(text, client)` (async)

```python
async def get_embedding(text: str, client, model="text-embedding-3-small"):
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    response = await client.embeddings.create(
        input=text.strip(),
        model=model,
    )
    return response.data[0].embedding
```

Çıktı 1536 boyutlu float vektör. OpenAI bunları **L2-normalized** üretiyor
yani `||v|| = 1` — ama biz cosine formülünü tam yazıyoruz (öğretmek için).

---

### `MemoryStore` (kalp)

```python
@dataclass
class MemoryStore:
    path: Optional[str] = None       # None ise in-memory mode
    facts: dict[str, str] = field(default_factory=dict)
    conversation: list[dict] = field(default_factory=list)
    memories: list[dict] = field(default_factory=list)
```

**Üç bellek katmanı:**

| Katman | Tip | İçerik | Örnek |
|---|---|---|---|
| `facts` | `dict[str,str]` | Hızlı erişimli key-value | `{"name": "Deniz"}` |
| `conversation` | `list[dict]` | Multi-turn message history | `[{"role":"user","content":"..."}]` |
| `memories` | `list[dict]` | Embedding'li semantic notes | `[{"text":"...","embedding":[0.1,...]}]` |

**Sınıf metodları:**
- `MemoryStore.load(path)` (classmethod) → dosyadan oku, yoksa boş döndür
- `store.save()` → JSON'a yaz, path None ise no-op
- `store.remember_fact(key, value)` / `recall_fact(key)`
- `store.add_memory(text, embedding, tags=None)`
- `store.search_memories(query_embedding, top_k=3)` → cosine'a göre sıralı

**JSON dosya formatı:**
```json
{
  "facts": {"name": "Deniz", "home_city": "İstanbul"},
  "conversation": [
    {"role": "user", "content": "Adım Deniz"},
    {"role": "assistant", "content": "Tanıştığımıza memnun oldum."}
  ],
  "memories": [
    {"text": "Adım Deniz", "embedding": [0.1, 0.2, ...], "tags": ["user_msg"]}
  ]
}
```

> **Önemli:** `path=None` ile yarat → in-memory store, `save()` no-op olur.
> Tests bunu kullanır. CLI'da `path="memory.json"` ile gerçek dosya kullan.

---

### 3 Bellek Tool'u

#### `remember_fact`
```python
class RememberFactInput(BaseModel):
    key: str = Field(description="Bilgi anahtarı, örn: 'home_city'")
    value: str = Field(description="Bilginin değeri")

async def _remember(input: RememberFactInput) -> dict:
    store.remember_fact(input.key, input.value)
    return {"status": "saved", "key": input.key, "value": input.value}
```

#### `recall_fact`
```python
class RecallFactInput(BaseModel):
    key: str = Field(description="Aranacak bilgi anahtarı")

async def _recall(input: RecallFactInput) -> dict:
    value = store.recall_fact(input.key)
    if value is None:
        return {"key": input.key, "found": False}
    return {"key": input.key, "found": True, "value": value}
```

#### `search_memory`
```python
class SearchMemoryInput(BaseModel):
    query: str = Field(description="Geçmiş mesajlarda aranacak metin")

async def _search(input: SearchMemoryInput) -> dict:
    if not store.memories:
        return {"results": []}
    query_emb = await get_embedding(input.query, client)
    results = store.search_memories(query_emb, top_k=3)
    return {
        "results": [
            {"text": r["text"], "score": round(r["score"], 3)}
            for r in results
        ],
    }
```

**`build_memory_registry(store, client)`** üç tool'u registry'ye ekleyip
döndürmeli. Closure ile `store` ve `client`'ı handler'lara bağla.

---

### `run_assistant` (multi-turn loop)

```python
async def run_assistant(user_message, client, store, max_iters=5):
    if not user_message or not user_message.strip():
        raise ValueError("user_message must not be empty")

    registry = build_memory_registry(store, client)
    tools = registry.to_openai_list()

    # System + facts hint + prior conversation + new message
    facts_summary = "\n".join(f"- {k}: {v}" for k, v in store.facts.items())
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Hatırlananlar:\n{facts_summary}"},
    ]
    messages.extend(store.conversation[-20:])  # last 20 turns max
    user_msg = {"role": "user", "content": user_message.strip()}
    messages.append(user_msg)

    # M5 agent loop pattern
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
            # Persist this turn
            store.conversation.append(user_msg)
            store.conversation.append({"role": "assistant", "content": answer})
            # Add to semantic memory
            try:
                emb = await get_embedding(user_message, client)
                store.add_memory(user_message, emb, tags=["user_msg"])
            except Exception as e:
                logger.warning("embed failed: %s", e)
            store.save()
            return answer

        # Tool calls — M5 pattern
        # ...
```

> **M5'ten farkı sadece son kısım:** Final cevap geldiğinde conversation
> ve memory'ye yazıp save() çağırıyorsun.

---

## Kullanım Örneği

```bash
# Tur 1
python assistant.py --message "Adım Deniz" --store memory.json
# → "Tanıştığımıza memnun oldum Deniz."

cat memory.json
# {"facts": {"name": "Deniz"}, "conversation": [...], "memories": [...]}

# Tur 2 — yeni terminal session, ama bellek korundu
python assistant.py --message "Adımı hatırlıyor musun?" --store memory.json
# → "Evet, sen Deniz'sin."

# Tur 3 — semantic search
python assistant.py --message "İstanbul'da yaşıyorum" --store memory.json
# → "Tamam, kaydettim. İstanbul güzel bir şehir."

python assistant.py --message "Daha önce hangi şehri konuşmuştuk?" --store memory.json
# LLM search_memory tool'unu çağırır → İstanbul anısını bulur
# → "İstanbul'da yaşadığını söylemiştin."
```

---

## Test Edilecek Davranışlar

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| Bellek temelleri | 3 | cosine_similarity matematik, facts CRUD, search ranking |
| Kalıcılık | 3 | Save/load round-trip, missing file fresh, in-memory no-op |
| Bellek araçları | 3 | remember_fact persists, recall_fact found/missing, search_memory embeds |
| Asistan döngüsü | 3 | Multi-turn flow, empty rejected, prior conversation carried |

**Toplam:** 12 test.

---

## Mock Stratejisi

Test runner **iki çeşit mock** kullanır:
1. **Chat completions mock** — M5 ile aynı, scripted responses
2. **Embeddings mock** — sabit vektör döndürür

```python
async def fake_emb(**kwargs):
    item = MagicMock(); item.embedding = [0.5] * 1536
    resp = MagicMock(); resp.data = [item]
    return resp

client.embeddings.create = fake_emb
```

Bu sayede test'ler gerçek API çağırmadan deterministik çalışır.

---

## OpenAI vs Anthropic — Embedding

| Konu | OpenAI | Anthropic |
|---|---|---|
| Embedding API | `client.embeddings.create(input, model)` | **Yok** — Anthropic embedding sunmaz |
| Önerilen alternatif | text-embedding-3-small (1536 boyut) | Voyage AI, Cohere, OpenAI, veya open-source modeller |
| Normalization | L2-normalized (cosine = dot) | Provider'a bağlı |

**Pratikte:** Claude kullanıcısı bile embedding için OpenAI veya başka
provider'a gider. M6 reference solution OpenAI embeddings kullanıyor —
Claude'la chat yapıp OpenAI'la embed etmek olağan kombinasyon.

---

## Teslim Formatı

```
solution.zip
├── assistant.py
└── requirements.txt
```

`memory.json`, `.env`, `__pycache__` ZIP'e koyma.

---

## İpuçları

### Embedding maliyeti

text-embedding-3-small **çok ucuz**: 1M token = $0.02. Yani 100 cümle = ~$0.0001.
Test etmekten korkma.

### `top_k` ne olmalı?

3-5 makul. Çok düşük = ilgili anıyı kaçırırsın, çok yüksek = LLM'e gürültü.

### Conversation truncation

`store.conversation[-20:]` — son 20 mesajı al, daha eskileri unutsun.
Context window taşmaması için. Production'da daha sofistike (summarization)
gerekebilir.

### Embedding boyutu

`text-embedding-3-small` 1536 boyut, `text-embedding-3-large` 3072 boyut.
Test'lerde 3 boyutlu vektörler kullanıyoruz (matematik anlaşılsın diye)
ama gerçekte 1536 normaldir.

### NumPy alternatifi

```python
# Pure Python (yavaş ama bağımlılık yok)
dot = sum(x * y for x, y in zip(a, b))

# NumPy (hızlı, production)
import numpy as np
dot = float(np.dot(a, b))
```

---

## Anti-pattern Uyarıları

- ❌ **Her turda tüm conversation'u API'ye gönderme** — context patlar, maliyet artar; son N mesaj yeterli
- ❌ **Embedding'leri her seferinde yeniden hesaplama** — pahalı, sakla
- ❌ **`facts` dict'ini conversation içinde tutmak** — hızlı erişim için ayrı tutmalısın
- ❌ **MemoryStore.save()'i tool handler içinde çağırmak** — race condition, sadece turn sonunda kaydet
- ❌ **Embedding API'yi try/except'siz çağırmak** — embedding rate limit yiyebilir, fallback ekle

---

## Önerilen Kaynaklar

- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [Pinecone vs Chroma vs Weaviate](https://www.pinecone.io/learn/) — production vector DB karşılaştırma
- [Anthropic Cookbook: Memory](https://github.com/anthropics/anthropic-cookbook) — Claude'la memory pattern'leri
- [LangChain Memory](https://python.langchain.com/docs/modules/memory/) — daha gelişmiş bellek yönetimi
