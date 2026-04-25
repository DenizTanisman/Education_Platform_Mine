# IAU AI Platform — Master Prompt for Claude Code

> **Bu dosya Claude Code'un her session başlangıcında OKUMASI ZORUNLU olan kontrattır.**
> Kural ihlali proje bozulmasına yol açar. Kurallara uymadığın durumda çalışmayı
> durdur ve kullanıcıya sor.

---

## 1. PROJE KİMLİĞİ

- **Proje adı:** IAU AI Online Kurs Platformu (v3)
- **Amaç:** Öğrencilerin yapay zekayı ünite ünite öğrendiği, her ünitenin sonunda
  otomatik test edilen bir Python kodu yüklediği eğitim platformu.
- **Stack:** Next.js 16 + Prisma 7 + PostgreSQL 16 + Docker sandbox + Caddy
- **Platform:** Docker Compose ile tek host üzerinde çalışır.
- **Kritik farklar (v2.2 → v3):**
  - Cooldown YOK (sınırsız deneme)
  - Redis YOK (in-memory semaphore yeterli, <20 eşzamanlı)
  - gVisor YOK (standart Docker + seccomp + cap-drop yeterli)
  - Per-test detaylı feedback (expected vs actual)
  - Content-as-code (content/units/ klasörü, discover script)

---

## 2. MUTLAK SINIRLAR — İHLAL ETME

### 2.1. Dizin Sahipliği (OWNERSHIP BOUNDARIES)

```
iau_platform/
├── app/              ← CLAUDE CODE sahibi. Next.js kodu buraya.
├── runner/           ← CLAUDE CODE sahibi. Runner servisi buraya.
├── infra/            ← CLAUDE CODE sahibi. docker-compose, Caddyfile, Makefile, seccomp.json
├── scripts/          ← CLAUDE CODE sahibi. DB scripts, ingest, cleanup
├── docs/             ← CLAUDE CODE sahibi. Teknik dökümanlar, self-test MD'leri
│
├── content/          ← DENİZ sahibi. CLAUDE CODE DOKUNMAZ.
│   ├── inbox/        ← Deniz teslim kapısı — yeni içerik buraya atılır
│   └── units/        ← Aktif ünite içerikleri — ingest script yerleştirir
│
├── .env              ← DENİZ sahibi. Claude Code sadece .env.example yazabilir.
└── .env.example      ← CLAUDE CODE yazabilir
```

**KURAL:** Claude Code asla `content/` dizinine, `.env` dosyasına, veya
bu dosyanın (`00_MASTER_PROMPT.md`) kendisine yazmaz. Sadece Deniz bu
dosyaları değiştirebilir.

Eğer Claude Code yeni bir dizin yaratma ihtiyacı duyarsa, önce sorar. Yaratma
sonrası bu dokümanın §2.1 bölümüne eklenecek satırı Deniz'e bildirir.

### 2.2. Faz Disiplini

Claude Code herhangi bir anda **TEK BİR FAZ** üzerinde çalışır (bkz. 01_BUILD_PLAN.md).
- Faz tamamlanmadan bir sonraki faza geçilmez.
- Faz içinde alt-task'lar sırayla yapılır. Alt-task atlanmaz.
- Her alt-task bitince Deniz onayı beklenir.
- Onay gelmeden bir sonraki alt-task'a geçilmez.

### 2.3. Test-First Kural

- Her yeni kod dosyası, yanında o dosyayı test eden bir self-check içerir:
  - Manuel komut (örn: `docker compose exec app npm run check:auth`)
  - Veya otomatize test (Jest, Vitest, pytest)
- Çalışmayan kod commit edilmez. "TODO" içeren kod commit edilmez.

### 2.4. Güvenlik Sabitleri (GÜVENLİK PROTOKOLÜ'ne uyum)

- Hardcoded secret YOK. Her şey `process.env.XXX` üzerinden.
- SQL string concat YOK. Prisma ORM kullanılır.
- Parola hash: bcrypt cost 12. md5/sha1 kesinlikle yasak.
- User input: validate + sanitize. Zod şemaları kullanılır.
- CORS wildcard YOK. Whitelist.
- Debug=false production. Stack trace kullanıcıya gösterilmez.
- Her endpoint auth middleware ile korunur (public olanlar hariç, explicit whitelist).
- Sandbox: `--network=none`, `--read-only`, `--cap-drop=ALL`,
  `--security-opt=no-new-privileges`, `--security-opt=seccomp=<profile>`,
  `--pids-limit=64`, memory 512MB, CPU 0.5, timeout 10s.
- Rate limiting tüm public endpoint'lerde (in-memory, sliding window).
- Her endpoint Zod ile input validation.
- Yüklenen ZIP için: size limit, decompressed size limit, file count limit,
  allowed extensions whitelist, path traversal kontrolü.

### 2.5. Geliştirme Disiplini

- Ana branch (`main`) her zaman çalışır durumda olmalıdır.
- Yeni özellik → yeni branch (`feat/<name>`). Test + onay olmadan merge yok.
- Her commit mesajı Conventional Commits formatında:
  - `feat(auth): add JWT refresh flow`
  - `fix(runner): handle zip bomb edge case`
  - `docs(architecture): add runner flow diagram`
- **Proje sonunda değil, her onaylanan alt-task'tan sonra GitHub'a push yapılır** (bkz: §9 GitHub Push Protokolü).
- README.md proje başlangıcında minimal, Faz 7 sonunda portfolio kalitesinde final.

### 2.6. Kişisel Bilgi Yasağı

- Kodda, testlerde, seed verilerinde, dökümanlarda kişisel bilgi KULLANILMAZ.
- Mock data: `test+1@example.com`, `Alice Example`, vs. gibi jenerik.
- Partner/işbirlikçi isimleri, kullanıcının özel bilgileri asla belge veya koda girmez.

---

## 3. ÇIKTI FORMATI — DENİZ'E NASIL TESLİM EDERSİN

Claude Code bir alt-task bitirdiğinde rapor verir. Ama **her alt-task iki farklı
sınıftan birine girer** ve davranış buna göre değişir:

### 3.A. OTOMATIK-DOĞRULANABİLİR ALT-TASK (çoğunluk)

Alt-task sadece komut çıktılarıyla doğrulanabilirse (build success, unit test pass,
health check, grep sonucu, docker compose up OK), Deniz'i **rahatsız etme**:

1. Self-test komutlarını çalıştır.
2. Hepsi PASS ise:
   - Commit et (conventional)
   - Push et (§9 GitHub Push Protokolü)
   - Kısa rapor ver (aşağıdaki format)
   - **Hemen sıradaki alt-task'a geç ve çalışmaya başla**
3. Herhangi bir self-test FAIL ise:
   - Dur. Deniz'e hatayı ve ne denediğini bildir.
   - 3 denemeden fazla tekrar etme.

**Kısa rapor formatı (otomatik devam durumu):**

```
✅ Alt-task X.Y: <başlık> tamamlandı.

Yapılanlar: <1-2 satır>
Değişen dosyalar: <liste>
Self-test: unit PASS (12/12) · build OK · secret grep CLEAN
Commit: feat(auth): add JWT signing helper → pushed to origin/feat/<n>

▶️ Alt-task X.Y+1: <başlık> başlıyor.
```

### 3.B. MANUEL-TEST GEREKTİREN ALT-TASK (duraklama)

Alt-task'ın tamamlanması Deniz'in tarayıcıda tıklamasını, UI'ı göz
kontrolüyle doğrulamasını, veya subjektif bir değerlendirme yapmasını
gerektiriyorsa: **DUR**. Uzun rapor ver:

```
✋ Alt-task X.Y: <başlık> — Deniz testi bekleniyor.

### Yapılanlar
- <bullet>

### Değişen dosyalar
- <liste>

### Otomatik self-test sonuçları
- [x] unit test: PASS (12/12)
- [x] build: OK
- [x] security grep: CLEAN

### Neden manuel test gerekli
<UI akışı, subjektif değerlendirme, vb.>

### Deniz'e test talimatı
1. `docker compose up -d`
2. Tarayıcıda `http://localhost/register`
3. Test hesabı oluştur: `demo@test.com` / `Test1234!`
4. Beklenen: 200 OK, /login'e redirect

### Onay sonrası otomatik yapılacaklar
- git commit + push origin/feat/<n>
- Alt-task X.Y+1 (<başlık>) başlayacak
```

Deniz "onay" veya "geç" yazdığında:
1. Commit + push yap.
2. "Alt-task X.Y onaylandı, pushlandı. Sıradakine geçiyorum: X.Y+1." tek satır bildir.
3. **Durmadan** sıradaki alt-task'a başla.

### 3.C. HANGİSİ OLDUĞUNU NASIL KARAR VERİR?

Karar matrisi — alt-task otomatik-doğrulanabilir değildir eğer:
- UI render sonucu görsel kontrol istiyor
- Subjektif "güzel mi" değerlendirmesi
- Tarayıcıda manuel tıklama gerektiriyor
- End-to-end kullanıcı akışı (register → login → submit → sonuç)
- Deniz'in subjektif onayı gereken içerik (README wording, vb.)

Şüphedeysen 3.B'yi seç (daha konservatif). Ama gereksiz durma yapma —
build ve test command'ı PASS döndüyse onay istemeye gerek yok.

---

## 4. İÇERİK TESLİMATI — DENİZ KAPIDAN NE VERİR

Deniz final sınavlarını ve ünite içeriklerini hazırladığında Claude Code'a
direkt kod olarak vermez. Bunun yerine `content/inbox/` klasörüne belirli
formatta bir paket atar. Format detayı 02_CONTENT_CONTRACT.md dosyasındadır.

Claude Code'un görevi:
1. `scripts/ingest-content.ts` komutunu yazmış olmak (Faz 3'te).
2. Deniz `content/inbox/unit-XX.zip` attığında bu script çalışır ve içeriği
   doğru yere yerleştirir.
3. Claude Code **asla** `content/inbox/` içine manuel bir şey yazmaz.
4. Claude Code **asla** `content/units/` altındaki dosyaları düzenlemez.
   Sadece discovery + DB upsert yapar.

---

## 5. SESSION PROTOKOLÜ

Her Claude Code session'ı başlarken:

1. Bu dosyayı (00_MASTER_PROMPT.md) OKUDUĞUNU belirt.
2. `01_BUILD_PLAN.md` dosyasından mevcut aktif faz ve alt-task'ı belirt.
3. O alt-task'a odaklan. Başka şey yapma.
4. Alt-task bitince:
   - 3.A (otomatik-doğrulanabilir) → self-test yap, PASS ise commit+push+kısa
     rapor, **hemen sıradakine başla**. Deniz'i rahatsız etme.
   - 3.B (manuel test gerekli) → uzun rapor, DUR, onay bekle.
5. Deniz "onay"/"geç"/"devam" dediğinde: commit+push yap, sıradakine başla.
6. Sıradaki alt-task da aynı döngü.

**Temel kural:** Onay aldıktan sonra DURMA. Commit, push, ve sıradaki task
başlatma aynı yanıtın parçası olmalı.

Her session kapanırken:

1. Yarım kalan işi `docs/WIP.md` dosyasına yaz.
2. Bir sonraki session'ın nereden devam edeceğini açıkça belirt.
3. Commit edilmemiş değişiklik yok (her alt-task sonunda commit + push).

---

## 6. ANTIPATTERN UYARILARI — BUNLARI YAPMA

- ❌ "Proje genelinde refactor yapıyorum" — asla. Sadece aktif alt-task.
- ❌ Birden fazla faz aynı anda. Paralel iş yok.
- ❌ Manuel test gereken alt-task'ta onay beklemeden push — DUR (bkz: §3.B).
- ❌ Otomatik-doğrulanabilir alt-task'ta gereksiz onay isteme — DEVAM (bkz: §3.A).
- ❌ `content/` altına yazma. Orası Deniz'in.
- ❌ "Şunu da ekleyeyim" — scope creep. Sadece istenen.
- ❌ Commit mesajında "wip", "stuff", "changes". Conventional Commits zorunlu.
- ❌ Test yazmadan feature. Her kod + self-test.
- ❌ Secret'ı `.env` yerine koda koymak. Yasak.
- ❌ Kullanıcı kişisel bilgisini seed data olarak kullanmak. Yasak.
- ❌ Push'suz alt-task kapatma. Onaylandıysa muhakkak pushlanır.

---

## 7. OKUMAN GEREKEN DİĞER DÖKÜMANLAR

- `01_BUILD_PLAN.md` — Faz ve alt-task listesi
- `02_CONTENT_CONTRACT.md` — İçerik teslim formatı
- `docs/ARCHITECTURE.md` — Teknik mimari (Faz 1'de oluşturulacak)
- `docs/WIP.md` — Yarım kalan işler (otomatik güncellenir)

---

## 8. DENİZ İLE İLETİŞİM KURALLARI

- Belirsizlik varsa sor. Tahmin etme.
- Bir alt-task'ta 3 deneme sonunda tıkandıysan dur ve sor.
- Büyük karar (library seçimi, schema değişikliği, yeni servis) için onay al.
- Hata çıkarsa açıkça bildir, gizleme. "Çalıştı ama..." ifadesi şüphe doğurur.
- Türkçe yanıt ver ama kod/commit/log İngilizce olsun.

---

## 9. GITHUB PUSH PROTOKOLÜ

Her alt-task tamamlandığında (otomatik onaylı veya Deniz onayı sonrası)
**mutlaka GitHub'a pushlanır**. Araç: GitHub CLI (`gh`).

### 9.1. İlk session — repo kurulumu (bir kerelik)

Session başında `git remote -v` kontrol et:

**Remote yoksa:**
1. `gh auth status` ile authentication kontrol.
   - Unauthenticated ise: DUR, Deniz'e `gh auth login` yapmasını söyle.
2. Deniz'e sor (istisnai onay noktası):
   ```
   GitHub remote yok. Yeni private repo oluşturayım mı?
   Önerilen ad: iau-ai-platform-v3
   Görünürlük: private
   ```
3. Onay gelirse:
   ```bash
   gh repo create iau-ai-platform-v3 --private --source=. --remote=origin
   git branch -M main
   git push -u origin main
   ```
4. Remote bilgisi `docs/WIP.md`'ye yazılır.

**Remote varsa:** Atla, direkt §9.2'ye.

### 9.2. Her alt-task sonrası push döngüsü

Alt-task başlamadan:
```bash
git checkout -b feat/<short-name>   # ör: feat/auth-jwt, feat/sandbox-image
```

Alt-task bitince (otomatik veya onay sonrası):
```bash
git add -A
git diff --cached --stat   # değişiklik özeti log'a
git commit -m "<conventional-commit-message>"
git push -u origin feat/<short-name>
```

İlk başta `main`'e PR otomasyonu KURULMAZ. Feature branch'ler `main`'e
yalnızca faz tamamlandığında merge edilir (faz bitimi = manuel merge onayı).

### 9.3. Faz sonu merge

Faz'ın tüm alt-task'ları tamamlandığında:

1. Tüm feat/* branch'leri `main`'e sırayla merge (squash commit):
   ```bash
   gh pr create --base main --head feat/<name> --title "Phase N.X: <title>" --fill
   gh pr merge --squash --delete-branch
   ```
2. `main` üzerinde `git tag phase-N-complete` tag'i
3. `git push --tags`

### 9.4. Commit mesajı şablonu

Conventional Commits + alt-task referansı:

```
<type>(<scope>): <description>

Task: X.Y — <alt-task başlığı>

<opsiyonel açıklama>

Self-test: unit PASS (12/12) · build OK · secret grep CLEAN
```

Örnek:
```
feat(auth): add JWT signing helper with jose

Task: 5.1 — Auth library (jose + bcrypt)

Implements JWT sign/verify with httpOnly cookies, bcrypt cost 12,
timing-safe password compare.

Self-test: unit PASS (8/8) · build OK · secret grep CLEAN
```

### 9.5. Push başarısız olursa

- Network hatası → 3 kez retry (exponential backoff: 2s, 5s, 10s)
- Authentication hatası → DUR, Deniz'e bildir
- Merge conflict (rare, branch izolasyonu sayesinde) → DUR, Deniz'e bildir
- Protected branch push reddi → DUR, PR flow'una geç

### 9.6. .gitignore zorunlulukları

Her push'tan önce `.gitignore` şunları içermeli:
- `.env`
- `node_modules/`
- `content/inbox/*.zip`
- `content/inbox/processed/`
- `content/inbox/errors/`
- `content/units/*/education.pdf` (büyük dosyalar — LFS veya dışarıda)
- `*.log`
- `.next/`, `dist/`, `build/`
- `app/public/pdfs/*.pdf` (aynı sebeple)

`content/units/` altındaki **yapısal dosyalar** (`unit.yaml`, `projects.md`,
`tests/test_runner.py`) git'e dahil olur — PDF ve ZIP içerik dışarıda.

### 9.7. Büyük dosya stratejisi

Education PDF'leri ve reference ZIP'leri git'e commit edilmez. İki seçenek:

1. **Git LFS** (önerilen): Deniz isterse Faz 1.1'de `git lfs track "*.pdf"` kurulur
2. **External storage**: PDF'ler S3/CDN'de, sadece URL DB'de tutulur

Claude Code Faz 1.1'de bu seçimi Deniz'e sorar (istisnai onay noktası).
