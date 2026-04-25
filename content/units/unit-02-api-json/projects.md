# Modül 2 — Final Görevi

## Amaç

Bu modülde öğreneceğin tek cümle: **dış dünyaya çık.** M0'da Python yazdın,
M1'de yerel dosyaya/DB'ye veri sakladın. Şimdi bir public API'den veri çekip
işleyeceksin.

Ama dış dünya **güvenilir değil** — DNS hatası olabilir, sunucu down olabilir,
rate limit yiyebilirsin. Bu yüzden sadece "GET at, JSON aç" yetmez. Otomasyon
yazıyorsun: **hatalara dirençli** olması gerek.

> Bu modül LLM'siz son modül. M3'ten itibaren OpenAI çağırmaya başlayacağız —
> ama bu modülde öğrendiğin retry, logging ve graceful error handling
> kalıpları **OpenAI çağrılarında da aynen** geçerli olacak.

---

## Ön Hazırlık

### 1. Çalışma klasörü ve sanal ortam

```bash
mkdir m02-final
cd m02-final

python -m venv venv
source venv/bin/activate   # macOS / Linux
# .\venv\Scripts\Activate.ps1   # Windows
```

### 2. requirements.txt

Bu modülde **dış bağımlılık var**: `requests`. M1'den farkı bu.

```
# requirements.txt
requests>=2.31
```

```bash
pip install -r requirements.txt
```

---

## Görev Tanımı

`fetcher.py` adında **tek bir dosya** oluştur. İçinde **3 fonksiyon, 1 exception
sınıfı, 1 parser builder ve bir CLI giriş noktası** olmalı.

> M1'deki gibi tek dosya mimarisi. Mock'larla test ediliyor; gerçek HTTP
> çağrısı yapmadan da testler geçer.

---

### Exception sınıfı — `FetchError`

Önce kendi exception tipini tanımla:

```python
class FetchError(Exception):
    """Raised when fetch_with_retry exhausts retries or hits a fatal error."""
    pass
```

Bu, retry tükendiğinde veya retry edilmeyecek bir HTTP hatası alındığında
fırlatacağın özel hata sınıfı.

---

### Fonksiyon 1 — `fetch_with_retry`

**İmza:**
```python
def fetch_with_retry(
    url: str,
    max_retries: int = 3,
    timeout: int = 10,
    backoff_base: float = 1.0,
    session=None,
) -> dict | list:
    ...
```

**Davranış:**

| Durum | Aksiyon |
|---|---|
| Boş url | `ValueError` fırlat (HTTP çağrısı yapmadan) |
| 200 OK | `response.json()` döndür |
| 4xx (404 dahil, 429 hariç) | Tek deneme, `FetchError` fırlat |
| 429, 500, 502, 503, 504 | Retry et |
| `ConnectionError`, `Timeout` vs | Retry et |
| JSON parse hatası | `FetchError` fırlat (sarılı) |
| max_retries tükenirse | `FetchError` fırlat |

**Backoff:** Her retry öncesi `backoff_base * (2 ** (attempt - 1))` saniye bekle.
Yani base=1.0 ile: 1s, 2s, 4s.

**İpuçları:**
- `requests.Session()` kullan (parametre olarak da gelebilir, test bunu
  override eder)
- `RETRYABLE_STATUS = {429, 500, 502, 503, 504}` set'i tanımla
- `requests.exceptions.RequestException` ata (ConnectionError, Timeout,
  vs hepsinin parent'ı)
- `JSONDecodeError`'ı yakala ve `FetchError`'a sar

---

### Fonksiyon 2 — `save_to_json`

**İmza:**
```python
def save_to_json(data, path: str) -> None:
    ...
```

**Davranış:**
- `data`'yı dosyaya yaz
- UTF-8 encoding zorunlu
- `ensure_ascii=False` (Türkçe karakterler `\u015f` yerine `ş` olarak yazılsın)
- `indent=2` (okunabilir format)

**Örnek:**
```python
save_to_json({"şehir": "İstanbul"}, "out.json")
# Dosya içeriği:
# {
#   "şehir": "İstanbul"
# }
```

---

### Fonksiyon 3 — `fetch_and_save`

**İmza:**
```python
def fetch_and_save(url: str, output_path: str, **kwargs) -> dict:
    ...
```

**Davranış:**
- `fetch_with_retry(url, **kwargs)` ile veriyi çek
- `save_to_json(data, output_path)` ile kaydet
- Bir özet dict döndür: `{"url": ..., "output": ..., "size_bytes": ...}`

---

### CLI — `build_parser` ve `main`

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=10)
    return parser
```

`main()` parser'ı kullanıp `fetch_and_save`'i çağırsın, sonucu JSON olarak
yazdırsın.

---

## Kullanım Örneği

REST Countries API ile Türkiye verisi:

```bash
python fetcher.py --url https://restcountries.com/v3.1/name/turkey \
                  --output turkey.json
```

Beklenen log + çıktı:
```
2026-04-25 14:32:01 [INFO] fetcher: GET https://restcountries.com/... (attempt 1/3)
2026-04-25 14:32:02 [INFO] fetcher: Saved 12453 bytes to turkey.json
{
  "url": "https://restcountries.com/v3.1/name/turkey",
  "output": "turkey.json",
  "size_bytes": 12453,
  "type": "list"
}
```

---

## Test Edilecek Davranışlar

`fetcher.py` dört grup test'ten geçirilir:

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| Başarılı istek | 3 | dict ve list yanıt, boş url reddi |
| Hata yönetimi | 3 | 404 retry'sız fail, 500 retry tükenmesi, JSON parse hatası |
| Retry davranışı | 3 | 500→200, 503 retryable, ConnectionError retry |
| Dosyaya kaydetme | 3 | Dosya oluşturma, round-trip, UTF-8 koruma |

**Toplam:** 12 test. Hepsini geçmen gerekiyor.

---

## Mock Mantığı (Önemli)

Test runner **gerçek HTTP çağrısı yapmaz**. Bunun yerine
`requests.Session.get`'i mock'larla değiştirir. Yani:

- Test 1: "200 OK + dict body" mocklanır → senin kodun normal yolda çalışmalı
- Test 2: "404 Not Found" mocklanır → senin kodun retry yapmadan FetchError fırlatmalı
- Test 3: "ConnectionError, sonra 200" mocklanır → senin kodun ConnectionError'ı yakalayıp retry etmeli

**Bu yüzden:** Kodunda `requests.get(url)` yerine `session.get(url)` kullan
(parametre olarak `session` alıyorsun, default `None` ise `requests.Session()`
oluşturuyorsun). Bu pattern test edilebilir kodun temel kuralı.

---

## Teslim Formatı

```
solution.zip
├── fetcher.py
└── requirements.txt
```

`logs/` veya `*.json` dosyası ZIP'e koyma.

---

## İpuçları

### Retry pattern (manuel, tenacity yerine)

```python
for attempt in range(1, max_retries + 1):
    try:
        response = http.get(url, timeout=timeout)
        # ... durumu değerlendir ...
        return result  # başarı
    except RequestException:
        if attempt < max_retries:
            time.sleep(backoff_base * (2 ** (attempt - 1)))
        continue
raise FetchError(...)
```

### Logging şablonu

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fetcher")

logger.info("GET %s (attempt %d/%d)", url, attempt, max_retries)
logger.warning("Retryable status %d on attempt %d", code, attempt)
logger.error("Final failure: %s", err)
```

### JSON parse güvenliği

```python
try:
    return response.json()
except json.JSONDecodeError as e:
    raise FetchError(f"Invalid JSON: {e}") from e
```

### `from e` zincirleme

`raise NewError(...) from e` kullanırsan original hatanın stack trace'i
korunur, debug kolaylaşır.

---

## Yerel Test (gerçek API ile)

ZIP'i göndermeden önce gerçek bir API ile dene:

```bash
python fetcher.py --url https://restcountries.com/v3.1/name/turkey \
                  --output test.json
cat test.json | head -20
```

400 mü 200 mü test etmek için:
```bash
# var olmayan ülke (404 dönmeli, retry yapmamalı)
python fetcher.py --url https://restcountries.com/v3.1/name/zzznotexist \
                  --output xxx.json
echo "Exit: $?"
# Beklenen: stderr'de FetchError, exit code 1
```

---

## Anti-pattern Uyarıları

- ❌ **Generic `except:`** — spesifik exception yakala
- ❌ **`requests.get` doğrudan** — mock'lanamayan kod yazma, `session.get` kullan
- ❌ **API key URL'sinde** — header'a koy, querystring'e değil (M3'te detay)
- ❌ **`time.sleep(60)`** — hardcoded backoff yerine exponential
- ❌ **`raise Exception(...)`** — kendi `FetchError` sınıfını kullan

---

## Önerilen Kaynaklar

- [Python requests dokümantasyonu](https://requests.readthedocs.io/)
- [REST Countries API](https://restcountries.com/) (ücretsiz, key gerektirmez)
- [HTTP status codes referansı](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
- [Python logging tutorial](https://docs.python.org/3/howto/logging.html)
