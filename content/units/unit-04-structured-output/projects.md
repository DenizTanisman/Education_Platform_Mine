# Modül 4 — Final Görevi

## Amaç

M3'te LLM'den **string** aldın — özet metni. Ama gerçek otomasyonda
"Şu yorumu özetle" yetmez; çoğu zaman **yapısal bilgi** istersin:
"rating kaç?", "kategori ne?", "kırmızı bayrak var mı?".

Bu modülde LLM'i **tip-güvenli, doğrulanmış JSON** üretmeye zorlamayı
öğreneceksin. Pydantic ile bir veri sınıfı tanımlarsın, OpenAI SDK'sı o
sınıfa **garantili** uygun çıktı üretir.

> Bu, LLM uygulamalarının **kalbidir**. "Cevap içine bakıp regex'le ayıklamak"
> antik çağ — Pydantic + structured outputs ile cevap doğru şekilde gelmek
> ZORUNDA.

---

## Ön Hazırlık

```bash
mkdir m04-final && cd m04-final

python -m venv venv
source venv/bin/activate

cat > requirements.txt << EOF
openai>=1.50
pydantic>=2.5
python-dotenv>=1.0
EOF

pip install -r requirements.txt

cat > .env << EOF
OPENAI_API_KEY=sk-proj-xxxxxxxx
EOF

echo ".env" >> .gitignore
```

---

## Görev Tanımı

`extractor.py` adında **tek bir dosya** oluştur. İçinde:

- 2 Enum (`Sentiment`, `Category`)
- 1 Pydantic model (`ReviewAnalysis`)
- 1 custom exception (`ExtractError`)
- 4 fonksiyon (`build_client`, `extract_review`, `extract_many`, `save_analyses`)
- CLI giriş noktası

---

### Enum 1 — `Sentiment`

```python
from enum import Enum

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
```

> **Önemli:** `str, Enum` — bu pattern Pydantic'in JSON schema üretirken
> string değerlerini kullanmasını sağlar. Çıplak `Enum` yerine `str, Enum`.

---

### Enum 2 — `Category`

5 değer: `PRODUCT`, `SERVICE`, `DELIVERY`, `SUPPORT`, `OTHER` (her biri
karşılık string değeri ile).

---

### Pydantic Model — `ReviewAnalysis`

```python
from pydantic import BaseModel, Field

class ReviewAnalysis(BaseModel):
    rating: int = Field(
        ge=1, le=5,
        description="Yıldız puanı tahmini (1=en kötü, 5=en iyi)",
    )
    sentiment: Sentiment = Field(
        description="Genel duygu tonu",
    )
    category: Category = Field(
        description="Yorum hangi konuyla ilgili",
    )
    summary: str = Field(
        description="2-3 cümlelik Türkçe özet",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Yorumda bahsedilen ciddi sorunlar (yoksa boş liste)",
    )
```

**Field constraint'leri kritik:**
- `ge=1, le=5` — rating bu aralıkta zorunlu (Pydantic validator + LLM zoru)
- `description="..."` — LLM bunu okuyup neyi doldurması gerektiğini bilir
- `default_factory=list` — red_flags boş liste default

---

### Exception — `ExtractError`

M3'teki `SummarizeError` ile aynı pattern.

---

### Fonksiyon 1 — `build_client`

M3 ile aynı: `AsyncOpenAI` döndür, `OPENAI_API_KEY` env var'ından oku.

---

### Fonksiyon 2 — `extract_review` (async)

**İmza:**
```python
async def extract_review(
    text: str,
    client,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> ReviewAnalysis:
    ...
```

**Davranış:**

1. Boş text → `ValueError` (API çağrısı yapmadan)
2. **`client.chat.completions.parse(...)`** kullan (`create` değil!)
3. `response_format=ReviewAnalysis` parametresi ile schema'yı geç
4. `messages` listesinde system + user
5. API hatası → `ExtractError` ile sar
6. `response.choices[0].message.parsed` döndür
7. `parsed is None` ise → `ExtractError`

**System prompt önerisi:**
```
Sen kullanıcı yorumlarından yapısal bilgi çıkaran bir asistansın.
Verilen yorumu analiz et ve verilen şemaya uygun JSON döndür.
Tüm değerleri Türkçe yaz. red_flags listesi ürün/hizmetle ilgili
ciddi sorunları içersin. Sorun yoksa boş liste döndür.
```

**Önemli — `parse` vs `create` farkı:**

| Method | Ne yapar |
|---|---|
| `client.chat.completions.create(...)` | Raw response döndürür, `.choices[0].message.content` (string) |
| `client.chat.completions.parse(...)` | Otomatik JSON Schema + parse, `.choices[0].message.parsed` (Pydantic instance) |

`parse` SDK'nın yeni helper'ı — Pydantic class'ını alıyor, JSON schema üretiyor,
API'ye gönderiyor, cevabı parse ediyor. Sen sadece sınıfı veriyorsun.

---

### Fonksiyon 3 — `extract_many` (async, paralel)

M3'teki `summarize_many` ile **birebir aynı pattern**:
- `asyncio.Semaphore(max_concurrency)` ile rate limit
- `asyncio.gather` ile sıra koruyarak paralel
- Boş liste → boş liste

---

### Fonksiyon 4 — `save_analyses`

**İmza:**
```python
def save_analyses(
    texts: list[str],
    analyses: list[ReviewAnalysis],
    path: str,
) -> None:
    ...
```

**Önemli — Enum serialization:**
```python
# YANLIŞ — direkt sözlüğe çevirme:
records = [{"review": t, "analysis": a.dict()} for t, a in zip(...)]
# Çıktı: "sentiment": <Sentiment.POSITIVE: 'positive'>  ← bozuk

# DOĞRU — Pydantic'in JSON serialization mode'u:
records = [
    {"review": t, "analysis": a.model_dump(mode="json")}
    for t, a in zip(texts, analyses)
]
# Çıktı: "sentiment": "positive"  ← string
```

`model_dump(mode="json")` Enum'ları `.value`'larına dönüştürür.

Kalanı M3'teki `save_summaries` ile aynı: ensure_ascii=False, length mismatch ValueError.

---

### CLI — `build_parser` ve `main`

```python
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--concurrency", type=int, default=5)
parser.add_argument("--model", default="gpt-4o-mini")
```

`asyncio.run(_run(args))` ile çalıştır.

---

## Kullanım Örneği

```bash
cat > reviews.txt << EOF
Ürün çok kaliteli, tam beklediğim gibi geldi. Hızlı kargo. Tavsiye ederim.
Kargo 5 gün gecikti, müşteri hizmetleri açmadı. Para iadesi istedim, henüz alamadım.
İdare eder. Fiyatına göre fena değil ama harika da değil.
EOF

python extractor.py --input reviews.txt --output analyses.json
```

Beklenen çıktı:
```json
{
  "count": 3,
  "output": "analyses.json",
  "categories": {
    "product": 1,
    "service": 0,
    "delivery": 1,
    "support": 0,
    "other": 1
  }
}
```

---

## Test Edilecek Davranışlar

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| Schema doğrulama | 3 | Required fields, rating bounds, Sentiment enum values |
| LLM çağrısı | 3 | Returns ReviewAnalysis, response_format passed, system+user roles |
| Hata yönetimi | 3 | Empty text rejected, API error wrapped, parsed=None handled |
| Dosyaya kaydetme | 3 | JSON array schema, Enum as string, length mismatch raises |

**Toplam:** 12 test.

---

## OpenAI vs Anthropic — Structured Output

İki SDK çok farklı yaklaşımlar kullanır:

| Konu | OpenAI | Anthropic |
|---|---|---|
| Method | `client.chat.completions.parse(...)` | `client.messages.create(...)` (tool calling ile) |
| Schema yolu | `response_format=ReviewAnalysis` | `tools=[{"name":"extract", "input_schema":{...}}]` + force tool use |
| Response | `.choices[0].message.parsed` | `.content[0].input` (tool args) |

**Anthropic'te yaklaşım:** "structured output" diye ayrı feature yok — onun yerine
**tool calling** kullanılır. Bir "extract_review" tool'u tanımlarsın, modeli onu
çağırmaya zorlarsın, tool argümanları senin yapısal verin olur.

Sonuç pratik olarak aynı: tip-güvenli structured output. Ama implementation
farklı, bu yüzden iki provider arasında geçerken refactor lazım.

---

## Teslim Formatı

```
solution.zip
├── extractor.py
└── requirements.txt
```

---

## İpuçları

### Pydantic Field shortcut'ları

```python
class Movie(BaseModel):
    title: str                                    # zorunlu
    year: int = Field(ge=1900, le=2100)          # aralık
    rating: float = Field(ge=0, le=10)           # ondalıklı
    genres: list[str] = Field(default_factory=list)  # boş liste default
    director: str | None = None                   # opsiyonel
```

### LLM'e iyi description vermek

LLM `description` alanını okuyarak ne dolduracağını bilir. İyi description
= daha doğru çıktı:

```python
# YETERSİZ
rating: int = Field(description="puan")

# İYİ
rating: int = Field(
    ge=1, le=5,
    description="Yorumdan tahmin edilen yıldız puanı. 1=çok kötü, 3=vasat, 5=mükemmel.",
)
```

### Nested Pydantic models

```python
class Address(BaseModel):
    city: str
    country: str

class Person(BaseModel):
    name: str
    age: int
    address: Address  # nested
```

OpenAI structured output nested yapıyı destekler. Karmaşık şemalar mümkün.

### Refusal handling

LLM bazen "bu yorumu çıkartamam" diye refuse edebilir (içerik filtresi):

```python
parsed = response.choices[0].message.parsed
if parsed is None:
    refusal = response.choices[0].message.refusal
    if refusal:
        raise ExtractError(f"Model refused: {refusal}")
```

---

## Yerel Test (Gerçek API ile)

Üç farklı yorum dene:

```bash
cat > test_reviews.txt << EOF
Bu telefon harika, hızlı şarj oluyor, kamerası muhteşem.
Sahte ürün geldi, orijinal değil. Para iadesi istiyorum.
Kararsızım, fiyatı uygun ama kalitesi vasat.
EOF

python extractor.py --input test_reviews.txt --output out.json
cat out.json
```

Maliyet: ~$0.0002 (3 yorum × ~200 token).

---

## Anti-pattern Uyarıları

- ❌ **`response.choices[0].message.content` parse etmeye çalışmak** — `parsed` kullan
- ❌ **`a.dict()`** (deprecated, Pydantic v1) — `a.model_dump(mode="json")`
- ❌ **`Enum` çıplak** — `str, Enum` çoklu inheritance kullan
- ❌ **Field description boş bırakmak** — LLM ne yazacağını anlamaz
- ❌ **Çok karmaşık nested schema** — 3 katmandan fazla → LLM zorlanır

---

## Önerilen Kaynaklar

- [Pydantic v2 docs](https://docs.pydantic.dev/latest/)
- [OpenAI Structured Outputs guide](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI Cookbook: Structured Output examples](https://github.com/openai/openai-cookbook)
- [Anthropic Tool Use guide](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)
