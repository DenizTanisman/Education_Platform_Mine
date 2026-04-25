# Modül 3 — Final Görevi

## Amaç

Bu modül kursun **omurgasının başladığı yer**. M0-M2'de "altyapı"yı kurdun:
Python, dosya I/O, HTTP, retry. Şimdi ilk LLM çağrısını yapacaksın ve hemen
**paralel** çağrıyla atacaksın. 10 başlık varsa, 10 ayrı isteği aynı anda
yollayıp sonuçları sıralı toplayacaksın.

> Bu modülde **iki kritik kavram**: (1) OpenAI SDK'sı ile chat.completions
> nasıl kullanılır, (2) `asyncio.gather` ile paralel I/O. İkincisi yapay
> zeka uygulamalarının "%99 daha hızlı" hilesinin temeli.

---

## Ön Hazırlık

### 1. Çalışma klasörü ve sanal ortam

```bash
mkdir m03-final
cd m03-final

python -m venv venv
source venv/bin/activate   # macOS/Linux
# .\venv\Scripts\Activate.ps1   # Windows
```

### 2. requirements.txt

```
openai>=1.50
python-dotenv>=1.0
```

```bash
pip install -r requirements.txt
```

### 3. .env dosyası

```bash
# .env (asla git'e commit etme!)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxx
```

```bash
echo ".env" >> .gitignore
```

### 4. Test API key'i (opsiyonel, yerel test için)

OpenAI API key'in yoksa: https://platform.openai.com → API keys.
Yeni hesap için $5 free credit yeterli (gpt-4o-mini ile binlerce çağrı).

> **Önemli:** Sandbox testleri **gerçek API çağrısı yapmaz**. Hepsi mock'lanır.
> Yani API key'in olmasa bile platforma yüklediğin kod testten geçer.
> Yerel testlerinde gerçek API kullanmak istiyorsan key gerek.

---

## Görev Tanımı

`summarizer.py` adında **tek bir dosya** oluştur. İçinde **4 fonksiyon, 1
exception sınıfı, build_client + build_parser ve CLI giriş noktası** olmalı.

---

### Exception sınıfı — `SummarizeError`

```python
class SummarizeError(Exception):
    """Raised when summarization fails for any reason."""
    pass
```

---

### Fonksiyon 1 — `build_client`

**İmza:**
```python
def build_client(api_key: str | None = None) -> AsyncOpenAI:
    ...
```

**Davranış:**
- `api_key` parametresi → onu kullan
- Yoksa → `os.environ.get("OPENAI_API_KEY")` ile oku
- Hâlâ yoksa → `ValueError` fırlat

> **Test notu:** Test runner mock client kullanıyor, bu fonksiyonu çağırmaz.
> Yani API key olmadan da test geçer.

---

### Fonksiyon 2 — `summarize_one` (async)

**İmza:**
```python
async def summarize_one(
    title: str,
    client,
    model: str = "gpt-4o-mini",
    max_tokens: int = 100,
    temperature: float = 0.3,
) -> str:
    ...
```

**Davranış:**

1. **Önce** boş title kontrolü → `ValueError` (API çağrısı yapmadan)
2. `client.chat.completions.create(...)` ile çağrı
3. `messages` listesinde **iki rol** olmalı: `system` + `user`
4. Hata durumunda → `SummarizeError` ile sarmala
5. `response.choices[0].message.content` döndür (`.strip()` ile)
6. Content `None` ise → `SummarizeError`

**System prompt önerisi:**
```
Sen kısa, net özetler yazan bir asistansın.
Verilen başlık için 1-2 cümlelik Türkçe özet üret.
Format: yalnızca özet metni, başka açıklama veya markdown kullanma.
```

---

### Fonksiyon 3 — `summarize_many` (async, paralel)

**İmza:**
```python
async def summarize_many(
    titles: list[str],
    client,
    max_concurrency: int = 5,
    **kwargs,
) -> list[str]:
    ...
```

**Davranış:**
- Her başlık için `summarize_one` çağır
- **Paralel olarak** çalıştır (`asyncio.gather`)
- Eşzamanlı istek sayısını `max_concurrency` ile sınırla (`asyncio.Semaphore`)
- **Sıra korunmalı** — `summaries[i]` `titles[i]`'ye karşılık gelmeli
- Boş liste → boş liste döndür (hata değil)

**Pattern:**
```python
async def summarize_many(titles, client, max_concurrency=5, **kwargs):
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded(title):
        async with semaphore:
            return await summarize_one(title, client, **kwargs)

    tasks = [_bounded(t) for t in titles]
    return await asyncio.gather(*tasks)
```

---

### Fonksiyon 4 — `save_summaries`

**İmza:**
```python
def save_summaries(
    titles: list[str],
    summaries: list[str],
    path: str,
) -> None:
    ...
```

**Davranış:**
- Her başlığı kendi özetiyle eşle
- JSON formatında dosyaya yaz: `[{"title": ..., "summary": ...}, ...]`
- `ensure_ascii=False`, `indent=2`
- `len(titles) != len(summaries)` → `ValueError`

---

### CLI — `build_parser` ve `main`

```python
def build_parser():
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--input", required=True)        # TXT, satır başına başlık
    parser.add_argument("--output", required=True)       # JSON output
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--model", default="gpt-4o-mini")
    return parser
```

CLI'da `asyncio.run(_run(args))` deseni ile async fonksiyonu çağır.

---

## Kullanım Örneği

```bash
# titles.txt
Yapay zeka tarihçesi
Transformer mimarisi
Python asyncio kullanımı
Vector database temelleri

# Çalıştır
python summarizer.py --input titles.txt --output summaries.json --concurrency 4

# Çıktı
2026-04-25 14:30:01 [INFO] Summarizing 4 titles with concurrency=4
2026-04-25 14:30:02 [INFO] Completed 4 summaries in 0.87s
{
  "count": 4,
  "elapsed_seconds": 0.87,
  "output": "summaries.json"
}
```

---

## Test Edilecek Davranışlar

`summarizer.py` dört grup test'ten geçirilir:

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| SDK çağrısı | 3 | String dönüş, system+user rolleri, model parametresi |
| Hata yönetimi | 3 | Boş title (API çağrısı yapmadan), API hatası wrapping, None content |
| Async paralellik | 3 | Sıra koruma, gerçekten paralel, semaphore limit |
| Dosyaya kaydetme | 3 | JSON array schema, UTF-8, length mismatch |

**Toplam:** 12 test.

---

## Mock Stratejisi (Önemli)

Test runner **gerçek OpenAI API'sine değil mock client'a** çağrı atar:

```python
client = MagicMock()
async def fake_create(**kwargs):
    msg = MagicMock(); msg.content = "özet"
    choice = MagicMock(); choice.message = msg
    resp = MagicMock(); resp.choices = [choice]
    return resp

client.chat.completions.create = fake_create
```

**Bu yüzden:**
- Test runner `summarize_one(title, mock_client)` şeklinde çağırır
- Senin fonksiyonun `client` parametresi almalı (built-in `AsyncOpenAI` yaratmamalı)
- API key olmadan da testler çalışmalı

---

## OpenAI vs Anthropic — Paralel Bilgi

Bu kursta OpenAI'ı öğretiyoruz ama Anthropic'in Claude SDK'sı **çok benzer**:

| Konu | OpenAI | Anthropic |
|---|---|---|
| Import | `from openai import AsyncOpenAI` | `from anthropic import AsyncAnthropic` |
| Client | `AsyncOpenAI(api_key=...)` | `AsyncAnthropic(api_key=...)` |
| Method | `client.chat.completions.create(...)` | `client.messages.create(...)` |
| Model | `"gpt-4o-mini"` | `"claude-haiku-4-5"` |
| Mesaj | `[{"role":"system",...},{"role":"user",...}]` | `system="..."` (param), `messages=[{"role":"user",...}]` |
| Yanıt | `response.choices[0].message.content` | `response.content[0].text` |

İki SDK arasında geçmek 1-2 saatlik refactor — kavramsal olarak aynı şey.
M3'te OpenAI öğreniyoruz, M5'ten itibaren Anthropic örnekleri de göreceksin.

---

## Teslim Formatı

```
solution.zip
├── summarizer.py
└── requirements.txt
```

`.env`, `*.json`, `__pycache__` ZIP'e koyma.

---

## İpuçları

### Async/await temelleri

```python
import asyncio

# Async fonksiyon tanımı
async def fetch_one():
    await asyncio.sleep(1)
    return "data"

# Async fonksiyon ÇAĞIRMA — ya async context'te ya da asyncio.run ile
async def main():
    result = await fetch_one()      # tek
    results = await asyncio.gather( # paralel
        fetch_one(),
        fetch_one(),
        fetch_one(),
    )

asyncio.run(main())
```

### Semaphore pattern (rate limit)

```python
sem = asyncio.Semaphore(3)  # en fazla 3 eşzamanlı

async def limited_call():
    async with sem:           # girip "1 slot" alır
        return await heavy_op()  # bitince slot'u bırakır
```

### Mock-friendly kod yazma

```python
# ❌ Test edilmesi zor
async def summarize(title):
    client = AsyncOpenAI()    # her çağrıda yeni client
    return await client.chat.completions.create(...)

# ✅ Test edilmesi kolay
async def summarize(title, client):  # client dışarıdan
    return await client.chat.completions.create(...)
```

---

## Yerel Test (Gerçek API ile)

```bash
# 5 başlıklı test
cat > test_titles.txt << EOF
Python asyncio
Transformer mimarisi
Vector database
Retrieval-augmented generation
Function calling
EOF

python summarizer.py --input test_titles.txt --output out.json --concurrency 3
cat out.json
```

Maliyet tahmini: 5 başlık × ~150 token × $0.00015/1K = **~$0.0001** (yarım kuruş).

---

## Anti-pattern Uyarıları

- ❌ **Sequential `for` döngüsü** — 10 çağrı 10 saniye, paralel 1 saniye
- ❌ **API key URL'sinde** — `?api_key=...` yerine SDK'nın doğru yöntemini kullan
- ❌ **Sınırsız concurrency** — 100 çağrıyı aynı anda atarsan rate limit yer
- ❌ **`requests.get` ile direkt HTTP** — SDK kullan, retry/auth otomatik
- ❌ **Sync `OpenAI` ile gather** — async için `AsyncOpenAI` gerekli

---

## Önerilen Kaynaklar

- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [OpenAI API reference](https://platform.openai.com/docs/api-reference)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Python asyncio tutorial](https://docs.python.org/3/library/asyncio-task.html)
- [Real Python — async I/O](https://realpython.com/async-io-python/)
