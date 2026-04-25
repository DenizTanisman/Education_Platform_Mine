# IAU AI Platform — Build Plan

> Bu doküman projenin 8 fazını ve her fazın alt-task'larını tanımlar.
> Her alt-task ayrı bir "durak"tır: Claude Code yapar → self-test → (gerekirse Deniz test) → commit + push → sıradaki.

**Durum simgeleri:**
- ⬜ Yapılmadı
- 🔄 Aktif
- ✅ Tamamlandı, commit'lendi, pushlandı
- ⏸ Duraklatıldı (Deniz feedback'i bekleniyor)
- 🧪 Deniz manuel testi bekleniyor

**Alt-task tipi simgeleri (00_MASTER_PROMPT.md §3):**
- 🤖 Otomatik-doğrulanabilir — Claude Code self-test PASS ise durma, push + devam
- 👤 Manuel test gerekli — self-test sonrası Deniz onayı bekle

---

## AKTİF DURUM

**Faz:** `Faz 1 — Repo İskeleti`
**Alt-task:** `1.1 — Dizin yapısı ve git init`
**Son onay:** (henüz yok)

---

## Faz 1 — Repo İskeleti

Amaç: Boş ama çalışır bir Docker Compose stack'i. Hiçbir feature yok, sadece
servisler ayakta kalkıyor.

### 1.1 ⬜ 🤖 Dizin yapısı ve git init

**Istisnai onay noktaları (bu alt-task'a özel, Deniz müdahalesi gerekli):**
1. GitHub repo adı onayı (örn: `iau-ai-platform-v3`, private)
2. Büyük dosya stratejisi: Git LFS mi, external storage mu (bkz: 00_MASTER_PROMPT.md §9.7)

Bu iki soruya cevap alındıktan sonra geri kalanı otomatik yürür.

- [ ] Projenin root dizininde şu klasörler oluşur:
  ```
  app/ runner/ infra/ scripts/ docs/ content/inbox/ content/units/
  ```
- [ ] `.gitignore` (Node, Python, Docker, .env, .DS_Store, content PDFs/ZIPs)
- [ ] `README.md` placeholder (tek satır: "IAU AI platform, v3 in progress")
- [ ] `git init`, initial commit: `chore: initial repo scaffold`
- [ ] `docs/WIP.md` oluşturulur (içeriği: "Faz 1.1 devam ediyor")
- [ ] GitHub remote setup (Deniz'den bir kerelik onay, bkz: §9.1)

**Self-test:**
- `tree -L 2` çıktısı yukarıdaki yapıyı gösterir
- `git log` ilk commit'i gösterir
- `git remote -v` origin gösterir
- `git push origin main` başarılı

**Deniz testi:** Yok (otomatik, push başarılı olunca tamam).

### 1.2 ⬜ 🤖 docker-compose.yml iskeleti

- [ ] 4 servis tanımlı: `caddy`, `app`, `runner`, `postgres`
- [ ] İki network: `public_net`, `internal_net`
- [ ] Caddy sadece `public_net`'te, postgres sadece `internal_net`'te
- [ ] App her iki network'te, runner sadece `internal_net`'te
- [ ] Servisler "hello world" placeholder image'larla ayağa kalkıyor
  (nginx:alpine, hello-world, vs.)
- [ ] `.env.example` dosyası tüm değişkenlerle doldurulmuş
- [ ] `infra/Caddyfile` minimal reverse proxy

**Self-test:**
- `docker compose config` syntax doğru
- `docker compose up -d` hata vermeden ayağa kalkar
- `docker compose ps` hepsi "running"

**Deniz testi:**
- `.env.example`'ı `.env` olarak kopyala
- `docker compose up -d` çalıştır
- `http://localhost` yanıt veriyor mu

### 1.3 ⬜ 🤖 Makefile ve temel komutlar

- [ ] `make start` — `docker compose up -d --build`
- [ ] `make stop` — `docker compose down` (volume korunur)
- [ ] `make logs` — tüm servislerin logları
- [ ] `make status` — `docker compose ps` + health
- [ ] `make reset` — `docker compose down -v` (TEHLİKELİ, confirm prompt)
- [ ] `make clean` — container sil, volume koru
- [ ] Tüm komutlar `.PHONY`

**Self-test:**
- Her komut en az bir kez çalıştırılır
- `make reset` yanlış yazımda "bunu yapmak istediğinizden emin misiniz" prompt

**Deniz testi:**
- `make start`, `make logs`, `make stop` sırayla çalıştır

---

## Faz 2 — Sandbox Image + Harness

Amaç: Öğrenci kodunu güvenli şekilde çalıştıran Docker image ve harness script.
Platform geri kalanından bağımsız test edilebilir.

### 2.1 ⬜ 🤖 Sandbox Dockerfile

- [ ] `infra/sandbox.Dockerfile`: Python 3.11-slim base
- [ ] Non-root user (uid 1001)
- [ ] `/workspace` dizini, öğrenci kodu buraya read-only mount edilecek
- [ ] Pre-installed: pytest, pydantic, anthropic (minimal, sadece test için gerekli)
- [ ] Entrypoint: `python /workspace/harness.py`

**Self-test:**
- `docker build -t iau-sandbox:latest -f infra/sandbox.Dockerfile .` başarılı
- `docker run --rm iau-sandbox:latest python --version` → 3.11.x

### 2.2 ⬜ 🤖 Seccomp profili

- [ ] `infra/seccomp.json` — minimum syscall izinleri
  - Base: Docker default seccomp
  - Extra deny: `ptrace`, `unshare`, `mount`, `umount`, `keyctl`, `bpf`,
    `userfaultfd`, `clone3` (newuser), `reboot`
- [ ] Dokümante edilmiş: hangi syscall neden blocked

**Self-test:**
- `python scripts/test-seccomp.sh` — ptrace çağrısı bloklanıyor
- Normal Python çalışması etkilenmiyor

### 2.3 ⬜ 🤖 Harness.py (test runner)

- [ ] `/workspace/code/` altında öğrenci kodunu arar
- [ ] `/workspace/tests/test_runner.py` dosyasını import eder
- [ ] Test case'leri execute eder, her biri için timeout (2s)
- [ ] JSON output formatı (bkz: 02_CONTENT_CONTRACT.md §3):
  ```json
  {
    "summary": {"total": N, "passed": N, "failed": N, "runtime_ms": N, "verdict": "passed|failed"},
    "groups": [{"name": "...", "tests": [...]}]
  }
  ```
- [ ] Her test case için: id, status, expected, actual, input, hint
- [ ] Crash durumu (student code throws): yakalanır, `status: "errored"`
- [ ] Timeout durumu: `status: "timeout"`
- [ ] Memory over: runner dışında yakalanır (container kill)

**Self-test:**
- `pytest tests/test_harness.py` — 10+ senaryo (pass/fail/timeout/crash)

### 2.4 ⬜ 🤖 Hardened docker run komutu

- [ ] `runner/src/sandbox-runner.ts` — spawnSync ile docker çağrısı
- [ ] Tüm güvenlik flag'leri (bkz: 00_MASTER_PROMPT.md §2.4)
- [ ] Stdout 1MB cap, stderr 1MB cap
- [ ] Exit code yorumlanır: 0 → parse JSON; 124 → timeout; diğer → crash

**Self-test:**
- Manuel test: fork bomb içeren ZIP → container kill, error response
- Manuel test: network access → `socket.gaierror` (no DNS)
- Manuel test: file write `/etc/` → permission denied

### 2.5 ⬜ 🤖 End-to-end sandbox testi

- [ ] `scripts/test-sandbox.sh` — örnek bir ZIP hazırlar, runner'ı çağırır, JSON döndürür
- [ ] `docs/sandbox-security-selftest.md` — güvenlik testleri raporu

**Deniz testi:**
- `make sandbox` çalıştır
- `./scripts/test-sandbox.sh examples/pass.zip` → PASS raporu
- `./scripts/test-sandbox.sh examples/fail.zip` → FAIL raporu + detay
- `./scripts/test-sandbox.sh examples/malicious.zip` → error, host etkilenmedi

---

## Faz 3 — Prisma Şeması + Content Discovery

Amaç: Veritabanı şeması ve `content/units/` klasöründen DB'ye yükleme scripti.

### 3.1 ⬜ 🤖 Prisma şeması

- [ ] `app/prisma/schema.prisma` — aşağıdaki modeller:
  - `User` (id, email, passwordHash, role, createdAt)
  - `Unit` (id, slug, order, title, description, published)
  - `Video` (id, unitId, title, youtubeId, pdfPath, order)
  - `Project` (id, unitId, title, markdownContent, order)
  - `TestGroup` (id, unitId, name, order, weight)
  - `TestCase` (id, testGroupId, name, description, hint)
  - `UnitProgress` (id, userId, unitId, status, completedAt)
  - `Submission` (id, userId, unitId, status, zipHash, report, createdAt)
  - `SubmissionTestResult` (id, submissionId, testCaseId, status, detail, runtimeMs)
- [ ] Partial unique index: `(userId, unitId)` where `status='running'` on Submission
- [ ] Enums: `UserRole`, `UnitStatus`, `SubmissionStatus`, `TestStatus`
- [ ] Initial migration commit

**Self-test:**
- `npx prisma migrate dev --name init` başarılı
- `npx prisma studio` açılır, tablolar görünür

### 3.2 ⬜ 🤖 Content ingest script

- [ ] `scripts/ingest-content.ts` — `content/inbox/` klasörünü tarar
- [ ] Format: `unit-XX-<slug>.zip` (bkz: 02_CONTENT_CONTRACT.md)
- [ ] ZIP doğrulama: şema kontrolü, gerekli dosyalar var mı
- [ ] Hatalıysa `content/inbox/errors/<zip-name>.log` dosyasına yazar
- [ ] Doğruysa `content/units/unit-XX-<slug>/` altına açar
- [ ] DB upsert: Unit, Video, Project, TestGroup, TestCase tablolarına
- [ ] PDF'leri `app/public/pdfs/` altına kopyalar
- [ ] test_runner.py'yi `content/units/.../tests/` içinde bırakır
- [ ] Başarı durumunda ZIP'i `content/inbox/processed/` klasörüne taşır
- [ ] Dry-run modu: `--dry-run` flag'iyle DB değişikliği yapmaz, sadece validate

**Self-test:**
- Örnek bir unit-00-welcome.zip hazırlanır
- `npm run ingest -- --dry-run` → validation OK
- `npm run ingest` → DB'de Unit row'u oluşur
- Bozuk ZIP → errors klasörüne log

### 3.3 ⬜ 🤖 Ingest trigger mekanizması

- [ ] `make ingest` komutu → `docker compose exec app npm run ingest`
- [ ] (Opsiyonel v2) File watcher: `chokidar` ile otomatik tetikleme
- [ ] Admin UI'dan manuel tetikleme endpoint'i (sadece admin role)

**Deniz testi:**
- Örnek unit ZIP'i `content/inbox/` içine at
- `make ingest` çalıştır
- `npx prisma studio` ile Unit row'u görür
- `http://localhost/admin/units` (henüz yoksa DB sorgusuyla) sayfada görünür

---

## Faz 4 — Runner Servisi

Amaç: Next.js'ten gelen submission isteğini kabul eden, sandbox'ı spawn eden,
sonuç döndüren HTTP servisi.

### 4.1 ⬜ 🤖 Runner iskeleti (Express + TypeScript)

- [ ] `runner/package.json`, `runner/tsconfig.json`
- [ ] `runner/src/server.ts` — Express, `/healthz`, `/run` endpoint'leri
- [ ] Shared secret middleware (`x-runner-secret` header)
- [ ] Request body validation (Zod): unitId, zipBuffer, submissionId
- [ ] Boyut kontrolü: 10MB max

### 4.2 ⬜ 🤖 In-memory semaphore + queue

- [ ] `p-limit` ile max 4 eşzamanlı
- [ ] Bekleme kuyruğu max 10 (dolu ise 429)
- [ ] Submission tracking: başlangıç zamanı, status
- [ ] Graceful shutdown: mevcut işler bitmeden kapanmaz (30s timeout)

### 4.3 ⬜ 🤖 Sandbox orchestration

- [ ] `runner/src/sandbox.ts` — Faz 2.4'teki hardened docker run wrapper
- [ ] ZIP extract to `/tmp/sub-<uuid>/`
- [ ] Test runner dosyalarını DB'den çek (via Prisma Client)
- [ ] Container spawn, stdout parse
- [ ] Temp dizin cleanup (başarı/başarısızlık fark etmez)

### 4.4 ⬜ 🤖 Report post-processing

- [ ] Harness JSON'u Prisma şemasına map et
- [ ] SubmissionTestResult row'ları yaz
- [ ] Submission.status güncelle (passed/failed)
- [ ] Pass ise UnitProgress güncelle, sıradaki Unit'i unlock

**Self-test:**
- Integration test: örnek submission → tüm akış → DB'de correct row'lar

**Deniz testi:**
- `curl -X POST http://localhost:4000/run -H "x-runner-secret: ..." -F "zip=@..."`
- Response: JSON report
- DB'de yeni Submission + Results

---

## Faz 5 — Next.js Auth

Amaç: Kullanıcı register/login/logout, route guard, rate limit.

### 5.1 ⬜ 🤖 Auth library (jose + bcrypt)

- [ ] `app/lib/auth.ts` — JWT sign/verify, httpOnly cookie
- [ ] bcrypt cost 12
- [ ] Timing-safe password compare
- [ ] Session expiry: 7 gün, sliding renewal

### 5.2 ⬜ 🤖 API routes

- [ ] POST `/api/register` — email+password, duplicate check
- [ ] POST `/api/login` — credential check, cookie set
- [ ] POST `/api/logout` — cookie clear
- [ ] GET `/api/me` — current user info
- [ ] Rate limit: 5 req/hour per IP for register+login

### 5.3 ⬜ 🤖 Middleware (edge)

- [ ] `app/middleware.ts` — protected routes için JWT doğrula
- [ ] Admin-only routes için role check
- [ ] Public routes: `/`, `/login`, `/register`, `/healthz`

### 5.4 ⬜ 👤 Register & Login UI

- [ ] `/register` formu (Zod validation, client + server)
- [ ] `/login` formu
- [ ] Error handling: kullanıcı zaten var, yanlış şifre, rate limit

**Deniz testi:**
- Register → login → me endpoint → logout akışı
- Rate limit: 6. register denemesi 429 döner

---

## Faz 6 — Öğrenci UI

Amaç: Dashboard, education, projects, final sayfaları.

### 6.1 ⬜ 👤 Dashboard
- [ ] Kurs listesi, ünite kartları
- [ ] Her ünite için: locked / in_progress / completed görsel durum
- [ ] Seçili ünite localStorage'da tutulur

### 6.2 ⬜ 👤 Education sayfası
- [ ] PDF iframe (app/public/pdfs/)
- [ ] YouTube video embed
- [ ] Yan panelde projects/final link'leri

### 6.3 ⬜ 👤 Projects sayfası
- [ ] react-markdown ile projects.md render
- [ ] "Final'e geç" butonu (locked değilse)

### 6.4 ⬜ 👤 Final sayfası
- [ ] ZIP upload (drag & drop)
- [ ] Client-side pre-validation (size, extension)
- [ ] Upload sonrası status polling (pending → running → done)
- [ ] Sonuç ekranı: Faz 3 mockup'ına göre per-test detay
- [ ] Submission history linki
- [ ] "Yeniden dene" butonu (cooldown YOK)

### 6.5 ⬜ 👤 Submission history
- [ ] Geçmiş denemeler listesi
- [ ] Her biri için detay sayfası

**Deniz testi:**
- Bir kullanıcı olarak giriş → ünite aç → projects oku → ZIP yükle → sonuç gör
- Aynı ünite için 3 deneme üst üste yapılabiliyor

---

## Faz 7 — Admin UI

Amaç: Ünite yönetimi UI (content-as-code dışında manuel düzenleme için).

### 7.1 ⬜ 👤 Admin dashboard
- [ ] Unit listesi, published toggle
- [ ] User listesi, role değişimi
- [ ] Submission history (tüm kullanıcılar)

### 7.2 ⬜ 👤 Content ingest tetikleyici
- [ ] UI'dan "content/inbox'ı tara" butonu → ingest çalışır
- [ ] İşlem loglarını gösterir

### 7.3 ⬜ 👤 Analitik sayfa
- [ ] Toplam kullanıcı, tamamlanan ünite, ortalama deneme sayısı
- [ ] Her ünite için pass rate

**Deniz testi:**
- Admin hesabıyla giriş, tüm yönetim aksiyonlarını dene

---

## Faz 8 — Ünite İçerikleri (Deniz ile birlikte)

Amaç: Her ünitenin instructions + reference solution ZIP'lerini hazırlama.

Bu faz **Claude Code'un kendi başına yapacağı bir şey değil**. Deniz ile bu
ana chat'te birlikte hazırlanan içerikler, 02_CONTENT_CONTRACT.md'ye göre
paketlenip `content/inbox/` kapısına atılır. Claude Code sadece ingest'i koşar.

Üniteler sırayla hazırlanır:
- Unit 00 — Platform tanıtımı (hello_world final)
- Unit 01 — (Deniz ile kararlaştırılacak)
- Unit 02 — ...
- (Devamı)

Her ünite için Deniz'in yapacakları (bkz: 02_CONTENT_CONTRACT.md):
1. education.pdf hazırla
2. projects.md yaz
3. test_runner.py hazırla, yerel olarak test et
4. reference_solution/ klasöründe pass_final.zip hazırla
5. Hepsini tek bir ZIP olarak paketle
6. `content/inbox/unit-XX-slug.zip` olarak at
7. `make ingest` çalıştır
8. DB'de Unit görünür, UI'da erişilebilir

---

## DEVAM KURALLARI

- Her faz bitince kısa bir retrospektif: ne iyi gitti, ne sorun çıktı.
- Faz sonunda `docs/phase-X-report.md` dosyası oluşur.
- Deniz "sonraki faza geç" dediğinde yeni faz başlar.
