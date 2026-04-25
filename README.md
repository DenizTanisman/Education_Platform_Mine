# IAU AI Platform

Yapay zekayı **ünite ünite, pratik üstünden** öğreten online kurs platformu.
Her ünite şu döngüyü içerir: ders notunu oku → proje talimatlarını incele
→ kendi kodunu yaz → ZIP'le yükle → otomatik testler birkaç saniye
içinde sonuç döndürür. Geçersen bir sonraki ünite açılır.

> **Esin:** [42 Ecole](https://42.fr) felsefesi — öğretmen anlatımı yerine
> kendi kodunu yazıp testten geçmen üzerine kurulu, proje tabanlı,
> kendi-tempolu öğrenme. Burada peer-grading yok; onun yerine her ünite
> için Deniz'in hazırladığı **referans çözüm** ve **harness uyumlu test
> setleri** sandbox içinde anında değerlendirme yapar.

## Kurs içeriği

9 ünitelik bir Python + LLM otomasyon yolu (her biri yaklaşık 3-5 saatlik
çalışma):

| # | Slug | Konu |
|---|---|---|
| 0 | `environment` | Geliştirme Ortamı ve Python Temelleri |
| 1 | `python-reflexes` | Python Otomasyon Refleksleri |
| 2 | `api-json` | API ve JSON |
| 3 | `llm-sdk` | LLM SDK ile Doğrudan Bağlantı |
| 4 | `structured-output` | Structured Output ile Pydantic |
| 5 | `function-calling` | Function Calling ile Tool Kullanımı |
| 6 | `memory` | Memory ile Stateful Agent |
| 7 | `rag` | RAG ile Doküman Tabanlı Asistan |
| 8 | `capstone` | Capstone — Mini Jarvis |

## Mimari

```
┌──────────┐     ┌─────────────┐     ┌──────────┐
│  Caddy   │ ──▶ │  Next.js    │ ──▶ │  Runner  │
│  :80     │     │  app:3000   │     │  :4000   │
│ /pdfs/*  │     │  (App       │     │ (Express │
│  static  │     │  Router)    │     │  + queue)│
└──────────┘     └─────┬───────┘     └────┬─────┘
                       │                   │
                       ▼                   ▼
                 ┌──────────┐       ┌──────────────┐
                 │ Postgres │       │ iau-sandbox  │
                 │   16     │       │ (Docker run  │
                 └──────────┘       │  per submit) │
                                    └──────────────┘
```

**Bileşenler:**

- **Next.js 15** — App Router, server components, Tailwind YOK (basit
  globals.css). Auth: jose JWT + bcrypt + httpOnly cookie + edge middleware.
- **Runner** — Node 22 + native TS strip-types, Express + Zod + p-limit.
  Her submission için yeni bir sandbox container'ı spawn eder.
- **Sandbox** — Python 3.11-slim + harness + course deps (pytest,
  pydantic, anthropic, requests, openai, python-dotenv). Submission
  süresince **`--network=none --read-only --cap-drop=ALL`** ve özel
  seccomp profili altında çalışır; her test için 2s wall-clock
  timeout, watchdog 10s sonra container'ı kill eder.
- **Caddy** — Reverse proxy + `/pdfs/*` altındaki ders PDF'lerini
  doğrudan static-serve eder (Next.js standalone public/ servislemediği
  için).
- **Postgres 16** — Prisma 5 ile schema (User, Unit, Video, Project,
  TestGroup, TestCase, UnitProgress, Submission, SubmissionTestResult).

## Hızlı başlangıç

### Gereksinimler

- Docker Desktop (daemon çalışır halde)
- Node 22+ ve npm (host tarafı: `make ingest`, dev mode)
- macOS / Linux (Windows test edilmedi)

### Adım adım

```bash
# 1. Repo'yu klonla
git clone https://github.com/DenizTanisman/Education_Platform_Mine.git
cd Education_Platform_Mine

# 2. Secret'ları oluştur. .gitignore'da olduğu için elle yaratman gerek.
cp .env.example .env

# JWT_SECRET ve RUNNER_SHARED_SECRET değerlerini openssl ile üret
# (en az 32 karakter):
openssl rand -hex 32   # → .env'deki JWT_SECRET satırına yapıştır
openssl rand -hex 32   # → .env'deki RUNNER_SHARED_SECRET satırına yapıştır

# 3. Sandbox image'ını bir kerelik build et (compose'tan bağımsız).
make sandbox

# 4. Migration helper image'ı + DB migration.
make migrate

# 5. Tüm stack'i ayağa kaldır (app + runner + caddy + postgres).
make start

# 6. İçerikleri DB'ye al (9 ünite ZIP'i content/inbox/processed/'da hazır,
#    ama DB row'ları için ingest gerekiyor):
cp content/inbox/processed/*.zip content/inbox/
make ingest

# 7. Tarayıcıda http://localhost'a git.
```

### Kullanım

**Öğrenci olarak:**

1. `/register` üzerinden kayıt ol.
2. `/dashboard` → Ünite 00 "açık" görünür, kartı tıkla.
3. Education sayfasında PDF iframe'inde ders notunu oku.
4. "Proje talimatları →" linkine git, `projects.md`'i oku.
5. Lokalinde kodu yaz, `submission.zip` olarak paketle.
6. "Final ZIP yükle →" sayfasında sürükle-bırak.
7. ~5 saniye içinde **PASSED** ya da **FAILED** + per-test detay
   (expected / actual / hint) görürsün.
8. Geçince Ünite 01 otomatik açılır.

**Admin olarak:**

İlk admin'i terminal'den promote etmen gerekiyor — UI flow'u admin-only
olduğu için kendi kendini admin yapamazsın:

```bash
make promote-admin EMAIL=senin-emailin@example.com
```

Sonra **çıkış yapıp tekrar giriş yap** (JWT cookie'sinin role claim'i
yenilensin). `/admin` paneline erişimin olur:

- Unit listesi + `published` toggle
- Kullanıcı listesi + role flip
- Içerik ingest tetikleyicisi (best-effort, host-side `make ingest`
  daha güvenilir)
- Analitik (pass-rate, ortalama deneme, vs.)
- Tüm denemeler audit (son 200)

## İçerik formatı (Faz 8 — yeni ünite eklemek)

Yeni bir ünite hazırlamak için `02_CONTENT_CONTRACT.md` dosyasındaki
şemaya uy:

```
unit-NN-slug.zip
├── unit.yaml                # metadata: order, slug, title, test_groups
├── education.pdf            # ders notu (max 20MB)
├── projects.md              # proje talimatları (markdown)
├── tests/
│   └── test_runner.py       # harness uyumlu test dosyası
├── reference/
│   └── pass_final.zip       # geçen referans çözüm (zorunlu — ingest
│                            #   sırasında sandbox'ta test edilir)
└── videos.yaml              # opsiyonel — YouTube embed listesi
```

ZIP'i `content/inbox/`'a at, `make ingest-dry` ile doğrula, sorunsuzsa
`make ingest` ile DB'ye yaz. Ingest sırasında **referans çözüm sandbox'ta
çalıştırılır** — geçemezse ünite reddedilir, hata `content/inbox/errors/`
altına yazılır.

Detay: `02_CONTENT_CONTRACT.md` (yapı), `docs/READINESS.md` (operasyonel
playbook).

## Eksik olan / manuel olan adımlar

- **`.env` dosyası** repo'da yok (secret'ları içerdiği için
  `.gitignore`'da). `cp .env.example .env` ile oluştur, `JWT_SECRET` ve
  `RUNNER_SHARED_SECRET`'i `openssl rand -hex 32` ile değiştir.
- **İlk admin** terminal'den `make promote-admin EMAIL=...` ile
  yapılır. UI'dan yapılamaz çünkü kullanıcı listesi ADMIN-only.
- **Migration ve ingest** otomatik değil. `make migrate` (her schema
  değişikliğinde), `make ingest` (her yeni ünite ZIP'i için) elle koşulur.
- **`/admin` panelindeki "Tara ve uygula" butonu** compose içinde
  best-effort — runner CLI app container'ında bulunmadığı için bazı
  durumlarda fail eder. Canonical yol: host'tan `make ingest`.
- **Postgres host portu (5433)** sadece geliştirme içindir (prisma
  studio + host-side ingest). Production'da bu mapping kaldırılmalı.
- **Sandbox runner gid 0 (root group)** ile çalışıyor — Docker
  socket'e erişmek için. Pratikte güvenlik etkisi yok (runner zaten
  host docker daemon'una erişiyor) ama prod-grade için ayrı bir docker
  daemon (örn. dind, sysbox) düşünülebilir.

## Geliştirme & test

```bash
# Sandbox güvenlik testi (3 fixture: pass / fail / malicious)
make sandbox-test

# Pytest harness suite (host)
cd app && npm test            # 27/27 — auth, rate-limit, ingest

# Runner integration suite (host, real docker)
cd runner && npm test         # 12/12 — sandbox flags, queue, e2e

# Type-check
cd app && npm run typecheck
cd runner && npm run typecheck

# Stack kontrolleri
make logs       # tüm servislerin logları
make status     # docker compose ps + health
make stop       # down (volume korunur)
make reset      # DESTRUCTIVE — volumes silinir, "YES" confirm prompt
```

## Faz haritası

Her faz `main` üzerinde annotated bir tag ile işaretli:

| Tag | İçerik |
|---|---|
| `phase-1-complete` | Repo iskelet + Docker compose + Makefile |
| `phase-2-complete` | Sandbox image, seccomp, harness, hardened runner wrapper |
| `phase-3-complete` | Prisma schema + content ingest pipeline |
| `phase-4-complete` | Runner HTTP service (Express + queue + Prisma write-back) |
| `phase-5-complete` | Auth (jose JWT + bcrypt + login/register UI) |
| `phase-6-complete` | Student UI (dashboard / education / projects / final / submissions) |
| `phase-7-complete` | Admin UI (panel / ingest / analytics / audit) |
| `system-ready` | Production Dockerfile'lar + compose wiring + READINESS playbook |
| `faz-8-content-loaded` | 9 ünite (Otomasyon kursu) ingested + tracked |

`git log <tag>..HEAD` ile faz sınırlarına göre diff alınabilir.

## Kontrat dosyaları

Repo, planlamayı kod-içi dokümantasyona değil **root'taki sözleşme MD'lerine**
emanet eder:

- `00_MASTER_PROMPT.md` — Claude Code çalışma kuralları, ownership
  sınırları, güvenlik sabitleri
- `01_BUILD_PLAN.md` — 8 faz × N alt-task yol haritası
- `02_CONTENT_CONTRACT.md` — Faz 8 içerik teslim şeması
- `docs/READINESS.md` — operasyonel playbook + manuel test akışları
- `docs/sandbox-seccomp.md` — seccomp profil rationale
- `docs/sandbox-security-selftest.md` — threat → mitigation matrisi
- `docs/WIP.md` — yarım kalan iş + bir sonraki adım

## Lisans

İçerik (PDF'ler, projects.md, test_runner.py'ler) Deniz Tanışman'a
aittir; izinsiz kopyalanamaz. Platform kodu (Next.js, runner, sandbox)
ileride MIT olarak ayrılabilir — şimdilik özel.
