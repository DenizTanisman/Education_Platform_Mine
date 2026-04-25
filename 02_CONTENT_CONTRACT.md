# IAU AI Platform — Content Delivery Contract

> Bu doküman Deniz'in ünite içeriklerini platforma teslim ederken uyacağı
> formatı tanımlar. Claude Code bu formatta gelen ZIP'leri otomatik işler.
>
> **Temel prensip:** Deniz sadece `content/inbox/` dizinine ZIP atar.
> Başka hiçbir yere dokunmaz. Claude Code asla `content/inbox/` içine yazmaz.

---

## 1. GENEL ŞEMA

Her ünite tek bir ZIP olarak teslim edilir:

```
content/inbox/unit-07-rag-pipeline.zip
```

Dosya adı şu formata uymalı:
- Prefix: `unit-`
- Sıra numarası: `00`, `01`, `02`, ... (iki basamak)
- Slug: kebab-case, İngilizce, alfanümerik + tire
- Uzantı: `.zip`

**Regex:** `^unit-\d{2}-[a-z0-9-]+\.zip$`

**Geçerli örnekler:**
- `unit-00-welcome.zip`
- `unit-01-python-basics.zip`
- `unit-07-rag-pipeline.zip`

**Geçersiz örnekler:**
- `unit-7-rag.zip` (tek basamak)
- `unit-01-RAG Pipeline.zip` (boşluk, büyük harf)
- `ünite-01.zip` (ASCII olmayan)

---

## 2. ZIP İÇİ DİZİN YAPISI (zorunlu)

```
unit-07-rag-pipeline.zip
├── unit.yaml                    # ZORUNLU — ünite metadata
├── education.pdf                # ZORUNLU — ders notları
├── projects.md                  # ZORUNLU — proje talimatları (markdown)
├── tests/
│   └── test_runner.py           # ZORUNLU — harness uyumlu test dosyası
├── reference/
│   └── pass_final.zip           # ZORUNLU — geçen referans çözüm
└── videos.yaml                  # OPSIYONEL — YouTube video listesi
```

### 2.1. unit.yaml (zorunlu)

```yaml
order: 7                         # integer, sıra
slug: rag-pipeline               # dosya adındakiyle eşleşmeli
title: RAG Pipeline              # insan-okuru başlık
description: |                   # kısa açıklama (max 500 char)
  Retrieval Augmented Generation temelleri. Document loader, embeddings,
  vector search ve cevap sentezi.
tags: [rag, embeddings, vector-search]   # opsiyonel
duration_minutes: 180            # tahmini öğrenme süresi
published: true                  # false ise ingest DB'ye yazar ama UI'da gizli
test_groups:
  - name: Document loader
    weight: 1
    order: 1
  - name: Vector search
    weight: 2
    order: 2
  - name: End-to-end pipeline
    weight: 3
    order: 3
```

### 2.2. education.pdf (zorunlu)

- Format: PDF (A4 veya Letter)
- Max boyut: 20 MB
- İçerik: ders notları, şemalar, örnekler

### 2.3. projects.md (zorunlu)

- Format: GitHub Flavored Markdown
- `react-markdown` ile render edilecek
- İçerik: öğrencinin **lokalinde** yapması gereken pratik görevler
- ZIP'e koyacağı dosya yapısını burada netleştir
- Max 500 satır

Önerilen yapı:

```markdown
# Unit 7 — RAG Pipeline

## Amaç
<feynman yaklaşımıyla genel resim>

## Ön hazırlık
- Python 3.11
- requirements.txt: ...

## Görevler

### Görev 1 — Document Loader
<açıklama>

**Beklenen fonksiyon imzası:**
```python
def load_document(path: str) -> list[Chunk]: ...
```

### Görev 2 — Vector Search
...

## Teslim formatı
Aşağıdaki dosya yapısıyla bir ZIP oluşturun:

```
submission.zip
├── loader.py
├── search.py
└── pipeline.py
```
```

### 2.4. tests/test_runner.py (zorunlu)

Harness bu dosyayı import eder. Şu kontratı takip eder:

```python
# content/inbox/.../tests/test_runner.py

from harness_api import TestResult, TestGroup, register

# Student code'u import etmek için sys.path'e /workspace/code eklenir
# (harness.py bunu otomatik yapar)
import sys
sys.path.insert(0, '/workspace/code')


def run_tests() -> list[TestGroup]:
    """
    Harness bu fonksiyonu çağırır. Her TestGroup, unit.yaml'daki
    test_groups'tan biriyle 'name' alanı üzerinden eşleşmeli.
    """
    groups = []

    # ---- Group 1: Document loader ----
    g1 = TestGroup(name="Document loader")

    try:
        from loader import load_document
        chunks = load_document("fixtures/sample.pdf")
        if len(chunks) == 5:
            g1.add(TestResult(
                id="test_load_basic",
                status="passed",
                runtime_ms=12,
            ))
        else:
            g1.add(TestResult(
                id="test_load_basic",
                status="failed",
                expected="len(chunks) == 5",
                actual=f"len(chunks) == {len(chunks)}",
                input='load_document("fixtures/sample.pdf")',
                hint="PDF'deki her sayfa bir chunk olmalı",
            ))
    except Exception as e:
        g1.add(TestResult(
            id="test_load_basic",
            status="errored",
            detail=str(e),
        ))

    groups.append(g1)

    # ---- Group 2: Vector search ----
    # ...

    return groups
```

**Kurallar:**
- Her TestResult'ın `id`'si unique, snake_case, prefix `test_`
- `status` ∈ `{passed, failed, errored, timeout}`
- `failed` ise `expected` + `actual` zorunlu, `input` + `hint` opsiyonel
- `errored` ise `detail` zorunlu (exception mesajı, stack trace değil)
- `hint` öğrenciye gösterilir, net ve kısa olsun
- Her test 2 saniyede bitmeli (harness timeout)

### 2.5. reference/pass_final.zip (zorunlu)

Bu ZIP **öğrencinin yükleyeceği** çözümün referans versiyonudur.

**Amaçları:**
- Ingest sırasında otomatik test edilir → `pass_final.zip` gerçekten geçiyor mu
- Admin UI'da "referans çözüm" olarak görüntülenebilir (opsiyonel)
- Deniz testini yerel olarak yaparken kullanır

**Şema:**
```
pass_final.zip
└── <projects.md'de belirtilen dosya yapısı>
```

Örnek:
```
pass_final.zip
├── loader.py
├── search.py
└── pipeline.py
```

**Kural:** Ingest script bu ZIP'i otomatik olarak sandbox'a submit eder.
Eğer tüm testler PASS dönmezse **ingest başarısız olur**, ünite DB'ye yazılmaz.

### 2.6. videos.yaml (opsiyonel)

```yaml
videos:
  - title: "RAG nedir, neden var?"
    youtube_id: "dQw4w9WgXcQ"
    duration_seconds: 720
    order: 1
  - title: "Embedding modelleri"
    youtube_id: "9bZkp7q19f0"
    duration_seconds: 900
    order: 2
```

---

## 3. HARNESS JSON ÇIKTI ŞEMASI (referans)

`test_runner.py` → `harness.py` → stdout:

```json
{
  "summary": {
    "total": 12,
    "passed": 10,
    "failed": 2,
    "errored": 0,
    "timeout": 0,
    "runtime_ms": 4823,
    "verdict": "failed"
  },
  "groups": [
    {
      "name": "Document loader",
      "weight": 1,
      "passed": 3,
      "total": 3,
      "tests": [
        {
          "id": "test_load_basic",
          "status": "passed",
          "runtime_ms": 12
        }
      ]
    },
    {
      "name": "Vector search",
      "weight": 2,
      "passed": 2,
      "total": 4,
      "tests": [
        {
          "id": "test_top_k_retrieval",
          "status": "failed",
          "expected": "first result id == \"doc_7\"",
          "actual": "first result id == \"doc_12\"",
          "input": "retrieve(\"Istanbul\", k=3)",
          "hint": "Cosine similarity normalizasyonu doğru mu",
          "runtime_ms": 22
        }
      ]
    }
  ]
}
```

`verdict`:
- `"passed"` → tüm testler passed
- `"failed"` → en az bir test failed/errored/timeout

---

## 4. DENİZ'İN HAZIRLIK WORKFLOW'U

Her ünite için izlenecek sıra:

1. **Çalışma dizini aç** (`~/scratch/unit-XX-slug/`)
2. **unit.yaml** yaz
3. **education.pdf** hazırla (veya mevcut materyalden dönüştür)
4. **projects.md** yaz — öğrenciye rehberlik eden görev listesi
5. **reference çözümü yaz** (`reference/pass_final/` klasöründe `.py` dosyaları)
6. **tests/test_runner.py** yaz — reference çözümü bu testlerden geçmeli
7. **Yerel test:**
   ```bash
   cd ~/scratch/unit-XX-slug
   cd reference && zip -r ../reference/pass_final.zip .
   cd ..
   # Lokal harness çalıştır
   python /path/to/platform/scripts/test-unit-locally.py .
   # → "all tests passed: 12/12" görmelisin
   ```
8. **ZIP paketle:**
   ```bash
   cd ~/scratch
   zip -r unit-XX-slug.zip unit-XX-slug/
   ```
9. **Kapıya bırak:**
   ```bash
   cp unit-XX-slug.zip /path/to/platform/content/inbox/
   ```
10. **Ingest tetikle:**
    ```bash
    make ingest
    ```
11. **Doğrula:**
    - Terminal çıktısı "unit-XX ingested" gösterir
    - `npx prisma studio` → Unit tablosunda yeni row
    - UI'da `http://localhost/dashboard` → ünite görünür
    - Reference solution otomatik test edilir → tüm testler PASS

12. **Hata durumu:**
    - `content/inbox/errors/unit-XX-slug.log` dosyasında hata detayı
    - ZIP `content/inbox/` içinde kalır, yeniden denenebilir
    - Düzelt → yeniden at → `make ingest`

---

## 5. TESLİMATTAN SONRA NE OLUR (Claude Code'un işi)

Ingest script şu adımları izler:

1. `content/inbox/unit-XX-slug.zip` tespit edilir
2. Şema validation (bu dokümandaki kurallar)
3. Geçici dizine açılır (`/tmp/ingest-<uuid>/`)
4. `unit.yaml` parse edilir
5. `reference/pass_final.zip` otomatik sandbox'a submit edilir
6. Tüm testler PASS değilse → HATA, `content/inbox/errors/` klasörüne log
7. PASS ise:
   - `content/units/unit-XX-slug/` klasörüne yerleştirilir
   - `education.pdf` → `app/public/pdfs/unit-XX-slug.pdf`
   - DB upsert: Unit, Video, Project, TestGroup, TestCase
   - ZIP `content/inbox/processed/` klasörüne taşınır
8. Başarı mesajı terminal'e yazılır

---

## 6. GÜNCELLEME SENARYOSU

Deniz bir üniteyi düzeltmek isterse:

1. Yeni ZIP hazırla (aynı slug, aynı order)
2. `content/inbox/` içine at
3. `make ingest`
4. Script: order + slug eşleşmesi varsa **upsert** yapar
5. `published: false` yaparsan UI'dan gizlenir ama veriler korunur
6. Tamamen silmek istersen admin UI'dan manuel silme (v2)

**Önemli:** Aynı slug + farklı order kombinasyonu yasak. Bu durumda script
hata verir ve eski değeri korur.

---

## 7. YASAKLAR

- ❌ `content/inbox/` içine `.py` veya `.md` gibi düz dosya atmak (her şey ZIP)
- ❌ ZIP içinde symbolic link
- ❌ ZIP içinde `.exe`, `.sh`, `.bat` dosyaları
- ❌ `__MACOSX/`, `.DS_Store` (tolere edilir ama uyarı)
- ❌ `test_runner.py` dışında `.py` dosyası `tests/` altında (harness import confliği)
- ❌ Kişisel bilgi (isim, email, telefon) unit.yaml veya projects.md'de
- ❌ Test case'lerde hardcoded path (`C:\Users\...`)

---

## 8. MINI REFERENCE — ÖRNEK ZIP İÇERİĞİ

Çalışır minimal bir örnek:

```
unit-00-welcome.zip
├── unit.yaml
├── education.pdf
├── projects.md
├── tests/
│   └── test_runner.py
└── reference/
    └── pass_final.zip
```

`unit.yaml`:
```yaml
order: 0
slug: welcome
title: Welcome to IAU AI
description: "Platform tanıtımı ve ilk Python kodu."
published: true
test_groups:
  - name: Hello world
    weight: 1
    order: 1
```

`tests/test_runner.py`:
```python
from harness_api import TestResult, TestGroup
import sys
sys.path.insert(0, '/workspace/code')

def run_tests():
    g = TestGroup(name="Hello world")
    try:
        from solution import greet
        result = greet("Deniz")
        if result == "Hello, Deniz!":
            g.add(TestResult(id="test_greet_basic", status="passed"))
        else:
            g.add(TestResult(
                id="test_greet_basic",
                status="failed",
                expected='"Hello, Deniz!"',
                actual=repr(result),
                input='greet("Deniz")',
            ))
    except Exception as e:
        g.add(TestResult(id="test_greet_basic", status="errored", detail=str(e)))
    return [g]
```

`reference/pass_final.zip` içi:
```
pass_final.zip
└── solution.py
```

`solution.py`:
```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

Bu örnek işler: `make ingest` → DB'ye Unit-0 gelir, kullanıcılar
erişebilir, öğrenci `solution.py` yazar → ZIP atar → PASS alır.
