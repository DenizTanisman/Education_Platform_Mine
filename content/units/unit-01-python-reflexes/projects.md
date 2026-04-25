# Modül 1 — Final Görevi

## Amaç

Bu modülde öğrendiklerini birleştirip **kendi başına çalışabilen bir komut
satırı aracı** yazacaksın: SQLite veritabanına görev ekleyen, listeleyen ve
tamamlandı olarak işaretleyen bir todo CLI'ı.

Bu görev küçük görünebilir ama otomasyonun **kalbidir**: senin yokken çalışan,
veriyi kalıcı olarak saklayan, terminalden parametreyle kontrol edilebilen
bir program. Kursun geri kalanında bunu LLM ile birleştirip **akıllı
asistanlar** yapacaksın.

> Bu modülde **harici LLM kütüphanesi yok**. Henüz API çağrısı atmayacaksın.
> Sadece Python'un kendi standart kütüphanesi — sqlite3, argparse, json,
> logging — yeterli.

---

## Ön Hazırlık

### 1. Çalışma klasörü

```bash
mkdir m01-final
cd m01-final
```

### 2. Sanal ortam aç

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
```

Aktif olduğunda terminalin başında `(venv)` yazısı belirir.

### 3. requirements.txt

Bu modülde dış bağımlılık **gerekmiyor** çünkü kullanacağın her şey Python
standart kütüphanesinde var. Yine de dosyayı şöyle oluştur:

```bash
echo "# M1 stdlib only" > requirements.txt
```

İlerideki modüllerde bu dosyaya satırlar ekleyeceğiz.

---

## Görev Tanımı

`tool.py` adında **tek bir dosya** oluştur. İçinde aşağıdaki **5 fonksiyon**
ve bir CLI giriş noktası olmalı.

> **Mimari kararı:** Her şey `tool.py` içinde. Sıfırdan başladığın için
> tek dosya daha kolay takip edilir. İleriki modüllerde modüler yapıya
> geçeceğiz.

---

### Fonksiyon 1 — `init_db(path)`

Veritabanı şemasını oluşturur (yoksa). İlk çağrıldığında `tasks.db` dosyasını
yaratır, içinde `tasks` adlı bir tablo açar.

**İmza:**
```python
def init_db(path: str = "tasks.db") -> None:
    ...
```

**Tablo şeması:**
```sql
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Önemli:** `IF NOT EXISTS` kullanmazsan ikinci çağrıda hata alırsın.

---

### Fonksiyon 2 — `add_task(title, path)`

Yeni bir görev ekler ve **yeni id'yi** döndürür.

**İmza:**
```python
def add_task(title: str, path: str = "tasks.db") -> int:
    ...
```

**Davranış:**
- Boş veya sadece boşluktan oluşan başlık → `ValueError` fırlat
- Geçerli başlık → INSERT et, `cursor.lastrowid` döndür
- Title'ı `.strip()` ile baştaki/sondaki boşluklardan temizle

**Örnekler:**
```python
add_task("Toplantı planla", "test.db")  # → 1
add_task("Rapor yaz", "test.db")          # → 2
add_task("", "test.db")                   # → ValueError
add_task("   ", "test.db")                # → ValueError
```

---

### Fonksiyon 3 — `list_tasks(path)`

Tüm görevleri liste halinde döndürür. **id'ye göre artan sırada.**

**İmza:**
```python
def list_tasks(path: str = "tasks.db") -> list[dict]:
    ...
```

**Dönüş formatı:**
```python
[
    {"id": 1, "title": "Toplantı planla", "done": False, "created_at": "..."},
    {"id": 2, "title": "Rapor yaz",        "done": True,  "created_at": "..."},
]
```

**Önemli:** `done` alanı **bool** olmalı, int 0/1 değil. SQLite int olarak
saklar, sen Python tarafında dönüştür: `bool(row["done"])`.

---

### Fonksiyon 4 — `complete_task(task_id, path)`

Bir görevi tamamlandı olarak işaretler.

**İmza:**
```python
def complete_task(task_id: int, path: str = "tasks.db") -> bool:
    ...
```

**Davranış:**
- Var olan id → `UPDATE`, `True` döndür
- Var olmayan id → exception fırlatma, sadece `False` döndür
- `cursor.rowcount` UPDATE'ten sonra etkilenen satır sayısını verir

---

### Fonksiyon 5 — `build_parser()`

`argparse.ArgumentParser` nesnesi oluşturup döndürür. CLI'nin tüm bayrakları
burada tanımlı olmalı.

**İmza:**
```python
def build_parser() -> argparse.ArgumentParser:
    ...
```

**Bayraklar:**
- `--add TITLE` — yeni görev ekler
- `--list` — `action="store_true"`, tüm görevleri listeler
- `--complete ID` — `type=int`, görevi tamamlar
- (Opsiyonel) `--db PATH` — alternatif DB dosyası

**Önemli:** `--complete` bayrağı **`type=int`** parametresi almalı. Aksi halde
`--complete abc` yazıldığında argparse hatası veremez.

**İpucu:** `--add`, `--list`, `--complete` mutually exclusive olmalı (aynı
anda sadece biri kullanılabilir):
```python
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--add", ...)
group.add_argument("--list", ...)
group.add_argument("--complete", ...)
```

---

### CLI giriş noktası — `main()` ve `if __name__ == "__main__"`

`tool.py` doğrudan çalıştırıldığında parser'ı kullansın:

```python
def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.add is not None:
        new_id = add_task(args.add)
        print(json.dumps({"id": new_id, "title": args.add.strip()}))
    elif args.list:
        tasks = list_tasks()
        print(json.dumps(tasks, indent=2, ensure_ascii=False))
    elif args.complete is not None:
        ok = complete_task(args.complete)
        if not ok:
            print(json.dumps({"error": f"id {args.complete} bulunamadı"}), file=sys.stderr)
            return 1
        print(json.dumps({"id": args.complete, "done": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## Kullanım

Yazdıktan sonra şöyle çalıştırılabilmeli:

```bash
python tool.py --add "Pazartesi toplantısı"
# Çıktı: {"id": 1, "title": "Pazartesi toplantısı"}

python tool.py --add "Rapor yaz"
# Çıktı: {"id": 2, "title": "Rapor yaz"}

python tool.py --list
# Çıktı:
# [
#   {"id": 1, "title": "Pazartesi toplantısı", "done": false, "created_at": "..."},
#   {"id": 2, "title": "Rapor yaz",            "done": false, "created_at": "..."}
# ]

python tool.py --complete 1
# Çıktı: {"id": 1, "done": true}

python tool.py --complete 99
# Çıktı (stderr): {"error": "id 99 bulunamadı"}
# Exit code: 1
```

---

## Test Edilecek Davranışlar

`tool.py` dört grup test'ten geçirilir:

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| Veritabanı işlemleri | 3 | add/list/complete temel akış |
| Hata yönetimi | 3 | Boş başlık, var olmayan id |
| Argparse yapısı | 3 | Bayraklar, type=int, store_true |
| JSON çıktı formatı | 3 | list[dict], required keys, done bool |

**Toplam:** 12 test. Hepsini geçmen gerekiyor.

---

## Teslim Formatı

```
solution.zip
├── tool.py
└── requirements.txt
```

`tasks.db` dosyasını ZIP'e koyma — sandbox kendi temiz DB'sini kullanacak.

---

## İpuçları

### SQLite tuzakları

- `with sqlite3.connect(path) as conn:` deyimi commit'i otomatik yapar
- `IF NOT EXISTS` clause her CREATE TABLE'da olsun
- SQL parametreleri **mutlaka** `?` placeholder ile, asla string concat ile:
  - ❌ `f"INSERT INTO tasks VALUES ('{title}')"` (SQL injection)
  - ✅ `"INSERT INTO tasks VALUES (?)", (title,)`

### Argparse tuzakları

- `action="store_true"` flag tipinde bayraklar için (`--list`)
- `type=int` argparse'a tip dönüşümü yaptırır
- `add_mutually_exclusive_group(required=True)` ile en az birinin verilmesini zorla

### JSON ve UTF-8

- `json.dumps(..., ensure_ascii=False)` Türkçe karakterler için
- Python objesi → JSON: `json.dumps(obj)`
- JSON → Python: `json.loads(s)`

### Try/except

```python
try:
    new_id = add_task(args.add)
except ValueError as e:
    print(f"Hata: {e}", file=sys.stderr)
    return 1
```

`Exception` yakalama generic — spesifik tip yakala (ValueError, sqlite3.Error).

---

## Yerel Test

ZIP'i göndermeden önce kendi makinende dene:

```bash
# Aynı klasörde, venv aktif:
python tool.py --add "Test 1"
python tool.py --add "Test 2"
python tool.py --list

# tasks.db dosyası klasörde oluşmuş olmalı
ls
# venv/  tool.py  requirements.txt  tasks.db
```

`tasks.db` dosyasını silersen sıfırlanır:
```bash
rm tasks.db
```

---

## Önerilen Kaynaklar

- [Python sqlite3 dokümantasyonu](https://docs.python.org/3/library/sqlite3.html)
- [Python argparse tutorial](https://docs.python.org/3/howto/argparse.html)
- [Python json modülü](https://docs.python.org/3/library/json.html)
- [Real Python — SQLite tutorial](https://realpython.com/python-sqlite-sqlalchemy/)
