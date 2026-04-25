# Modül 0 — Final Görevi

## Amaç

Bu modülde Python kurulumunu yaptın, terminali tanıdın ve ilk script'lerini
çalıştırdın. Şimdi öğrendiklerini birleştirip **üç fonksiyon yazacaksın**.
Bu fonksiyonlar küçük ama kursun geri kalanında defalarca kullanacağın
kalıpları (string formatlama, listeyle çalışma, koşullu sayma) içeriyor.

> Bu modülün finali "kelime ezberi" değil, refleks kazandırma egzersizi.
> Çözmeye çalışırken takılırsan ipuçlarını oku, hâlâ takılırsan kursun
> Discord kanalında sor.

---

## Ön Hazırlık

1. Python 3.11 veya üzeri kurulu olmalı:
   ```bash
   python --version
   # veya
   python3 --version
   ```

2. Bir çalışma klasörü aç:
   ```bash
   mkdir m00-final
   cd m00-final
   ```

3. (Önerilir) Sanal ortam aç — modülün eğitim materyalinde anlatıldı:
   ```bash
   python -m venv venv

   # macOS / Linux
   source venv/bin/activate

   # Windows (PowerShell)
   .\venv\Scripts\Activate.ps1
   ```

4. Bu modülde **harici kütüphane gerekmez**. Sadece Python'un kendisi yeterli.

---

## Görev Tanımı

`solution.py` adında bir dosya oluştur ve aşağıdaki **üç fonksiyonu** yaz.

### Görev 1 — `selamla(isim)` fonksiyonu

Bir isim alır, o ismi içeren bir Türkçe selamlama döndürür.

**Beklenen imza:**
```python
def selamla(isim: str) -> str:
    ...
```

**Davranış:**
- `selamla("Ayşe")` → `"Merhaba, Ayşe!"`
- `selamla("Çağrı")` → `"Merhaba, Çağrı!"` (Türkçe karakterler sorun olmamalı)
- `selamla("")` → `"Merhaba!"` (boş string verilirse sadece "Merhaba!" dön)

**İpucu:** f-string kullan. `f"Merhaba, {isim}!"` formatı tüm görevi çözer
ama boş string'i ayrı kontrol etmen gerek.

---

### Görev 2 — `topla(sayilar)` fonksiyonu

Bir sayı listesi alır, hepsinin toplamını döndürür.

**Beklenen imza:**
```python
def topla(sayilar: list[int]) -> int:
    ...
```

**Davranış:**
- `topla([1, 2, 3, 4, 5])` → `15`
- `topla([])` → `0` (boş liste — toplam sıfır)
- `topla([-3, -2, -1, 0, 1, 2, 3])` → `0` (negatifler normal toplanır)

**İpucu:** Bir `for` döngüsüyle her elemanı bir `total` değişkenine ekle.
Python'un yerleşik `sum()` fonksiyonunu kullanmadan da, kullanarak da
yazabilirsin — ikisi de geçer.

---

### Görev 3 — `cift_say(sayilar)` fonksiyonu

Bir sayı listesi alır, içindeki **çift sayıların adedini** döndürür.

**Beklenen imza:**
```python
def cift_say(sayilar: list[int]) -> int:
    ...
```

**Davranış:**
- `cift_say([1, 2, 3, 4, 5, 6])` → `3` (2, 4, 6 çifttir)
- `cift_say([])` → `0`
- `cift_say([0, -2, -1, -4, 7])` → `3` (0, -2, -4 hepsi çift)

**İpucu:** Modulo operatörü `%` ile çift sayıyı tespit edersin: `x % 2 == 0`
ifadesi `True` ise `x` çifttir. **0 sayısı çifttir.** Negatif sayılar için
Python'da `-2 % 2` sonucu `0` döner — yani normal kontrol yeterli, özel
durum yazma.

---

## Test Edilecek Davranışlar

Senin gönderdiğin `solution.py` üç grup test'ten geçirilir:

| Grup | Test sayısı | Neyi kontrol eder |
|---|---|---|
| selamla fonksiyonu | 3 | Normal isim, boş string, Türkçe karakter |
| topla fonksiyonu | 3 | Pozitif sayılar, boş liste, negatif sayılar |
| cift_say fonksiyonu | 3 | Karışık sayılar, boş liste, sıfır + negatifler |

**Toplam:** 9 test. Hepsini geçmen gerekiyor (cooldown yok, istediğin kadar
deneyebilirsin).

---

## Teslim Formatı

Şu yapıda bir ZIP dosyası hazırla:

```
solution.zip
└── solution.py
```

Yani ZIP'in içinde **sadece** `solution.py` olsun, başka klasör veya
dosya olmasın. Platform üzerinden bu ZIP'i Final sayfasında yükle.

> İstersen yanına `requirements.txt` da koyabilirsin (M0'da boş yeterli)
> ama zorunlu değil.

---

## Nasıl Yerel Olarak Test Ederim?

Submission'ı yüklemeden önce kendi makinende denemek istersen:

```bash
# solution.py aynı klasörde olduğunu varsayarak
python -c "from solution import selamla; print(selamla('Test'))"
# Beklenen: Merhaba, Test!
```

Veya Python'un interactive shell'inde:
```python
>>> from solution import topla
>>> topla([1, 2, 3])
6
```

Beklediğin değer geliyorsa hazırsın.

---

## İpuçları (Genel)

- **Hardcoded liste yazma.** Yani `if sayilar == [1,2,3,4,5]: return 15` gibi
  her olası input'u tek tek kontrol etme. Test farklı listeyle çalıştırılır,
  hep `failed` alırsın.
- **Print bırakma.** Kodun arasına `print("buradayım")` koyduysan teslim
  etmeden önce sil. Test runner çıktısını okumaz ama temiz kod alışkanlığı kazan.
- **İndentation.** Python boşluğa hassas — fonksiyon gövdesi 4 boşluk
  içeride olmalı. VS Code Python eklentisi otomatik düzeltir.
- **Türkçe karakterler.** `def selamla(isim)` yazarken sorun yok ama
  dosya UTF-8 kaydetmiş olduğundan emin ol (VS Code default UTF-8'dir).

---

## Önerilen Kaynaklar

- [Python resmi tutorial — Veri yapıları](https://docs.python.org/3/tutorial/datastructures.html)
- [Python f-string referansı](https://docs.python.org/3/tutorial/inputoutput.html#fancier-output-formatting)
- [Real Python — Fonksiyon temeli](https://realpython.com/defining-your-own-python-function/)
