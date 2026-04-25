# Work In Progress

> Bu dosya Claude Code tarafından otomatik güncellenir. Yarım kalan işi ve
> bir sonraki session'ın nereden devam edeceğini gösterir.

## Yön (2026-04-25, Deniz)

> Sistem tamamen hazır olsun → sonra Deniz Faz 8 içeriklerini getirir.
> Faz 2.5'ten Faz 7'ye kadar tek tek alt-task onayı bekleme; faz-sonu
> merge'leri otomatik yap (gh CLI serbest, §9 + memory). UI heavy
> alt-task'larda (6.x, 7.x) auto-checks (build / typecheck / smoke)
> yeterli — görsel manuel test EN SON, sistem bütünüyle hazırken.

## Aktif durum

- **Faz:** Faz 2 — Sandbox Image + Harness
- **Alt-task:** 3.2 + 3.3 — Content ingest + make ingest (tamam)
- **Branch:** `feat/content-ingest` (chained on `feat/prisma-schema`)
- **Faz 1 + Faz 2 → main, `phase-1-complete` ve `phase-2-complete` tag'ları pushed.
- **Remote:** `origin` → `https://github.com/DenizTanisman/Education_Platform_Mine.git`

## Son durum notları

- Büyük dosya stratejisi: **Seçenek C — şimdilik git'ten hariç**.
  PDF'ler, inbox ZIP'leri, reference çözüm ZIP'leri `.gitignore`'da.
  LFS veya external storage kararı Faz 8'de verilecek.
- Root'taki kontrat MD'leri (`00_MASTER_PROMPT.md`, `01_BUILD_PLAN.md`,
  `02_CONTENT_CONTRACT.md`) git tarafından tracked.
- Faz 1.2 tamamlandı: 4 servis (caddy/app/runner/postgres) placeholder
  image'larla ayağa kalkıyor. `http://localhost` 200 döndü. `internal_net`
  postgres için izole, `public_net` sadece caddy için host'a açık.
- Faz 1.3 tamamlandı: `Makefile` altı hedefle (`start/stop/logs/status/reset/clean`).
  `reset` "YES" confirm prompt'u ile korunuyor.
- Faz 1 → `main`'e merged (PR #2 squash — feat/makefile feat/compose-skeleton'dan
  branch'lendiği için her iki alt-task da tek squash'ta indi). PR #1 orphan,
  kapatıldı. `phase-1-complete` tag pushed.
- Faz 2.1 tamamlandı: `infra/sandbox.Dockerfile` — Python 3.11-slim, uid 1001
  (regular, --system kaldırıldı SYS_UID_MAX warning için), pytest/pydantic/anthropic
  pin'li, ENTRYPOINT `python /workspace/harness.py`. 240MB. harness.py 2.3'te gelecek.
- Faz 2.2 tamamlandı: `infra/seccomp.json` — moby v27.3.1 default base,
  extra-deny list (ptrace/unshare/mount/umount/umount2/keyctl/bpf/userfaultfd/
  clone3/reboot) hem ALLOW rule'larından çıkarıldı hem de en üste explicit
  ERRNO block olarak eklendi. `scripts/test-seccomp.sh` control+test1+test2 geçti.
  Gerekçeler `docs/sandbox-seccomp.md`'de.
- Faz 2.3 tamamlandı: `infra/sandbox/harness.py` + `harness_api.py`,
  Dockerfile `COPY --chmod=0444` ile her ikisini de `/workspace`'e ro
  kopyalıyor. Per-test 2s SIGALRM timeout, outer run_tests timeout (default 60s).
  JSON contract (02_CONTENT_CONTRACT.md §3) harness-level failure'da bile
  garantili. `tests/test_harness.py` 13 senaryoyla geçti + container-içi smoke
  (full 2.4 security flag'leri altında bile harness çalıştı).
- Faz 2.4 tamamlandı: `runner/` TS scaffold (Node 24 native TS, no tsx/ts-node).
  `runner/src/sandbox-runner.ts` — `runSandbox()` + `buildDockerArgs()`.
  Tüm §2.4 flag'leri: `--network=none --read-only --cap-drop=ALL
  --security-opt=no-new-privileges --security-opt=seccomp=... --pids-limit=64
  --memory=512m --memory-swap=512m --cpus=0.5 --tmpfs /tmp:rw,noexec,nosuid,size=64m`.
  Detached watchdog container'ı `docker kill` ile hard-stop ediyor (spawnSync
  timeout sadece CLI client'ı öldürüyor, container'ı değil — belt+suspenders).
  stdout/stderr 1MB cap (maxBuffer). Outcome union: ok/timeout/crash/invalid_json/output_truncated.
  Integration suite 8/8: arg construction (2) + happy/timeout/network/readonly/
  fork-bomb-containment/fail-propagation (6).

- Faz 2.5 tamamlandı: `runner/src/cli.ts` (thin CLI), `scripts/test-sandbox.sh`,
  `scripts/sandbox-examples/{pass,fail,malicious}/{tests,code}/`,
  `docs/sandbox-security-selftest.md`, Makefile'a `sandbox` ve `sandbox-test`
  target'ları eklendi. 3/3 örnek doğrulandı: pass→passed, fail→failed (clean
  diff), malicious→3/3 escape contained (URLError/OSError/ptrace rv=-1).
- Faz 2 → main: PR'lar yeniden açıldı (downstream'ler her squash'ta kapanıyor —
  pattern memory'de). 5 PR sırayla squash-merged, `phase-2-complete` tag pushed.
- Faz 3.1 tamamlandı: `app/prisma/schema.prisma` — 9 model (User, Unit, Video,
  Project, TestGroup, TestCase, UnitProgress, Submission, SubmissionTestResult)
  + 4 enum. Migration: `init` + `running_submission_partial_unique` (raw SQL
  partial unique index, prisma henüz native desteklemiyor). `app/Dockerfile.migrate`
  (node:20-slim + openssl) ve `make migrate-build` / `make migrate` target'ları.
  `internal_net`'in `internal: true` flag'i kaldırıldı — segmentation kalıyor
  (Caddy'nin postgres'i göremiyor olması) ama bir-off tooling container'ları
  prisma binary'lerini fetch edebilsin.

- Faz 3.2 + 3.3 tamamlandı: `app/scripts/ingest-content.ts` — filename regex,
  ZIP extraction (adm-zip), unit.yaml parse (yaml), required-files check,
  reference solution sandbox check (runner CLI), Prisma upsert (Unit, Video,
  Project, TestGroup; TestCase lazily on first submission). `--dry-run` flag.
  Hatalı ZIP'ler `content/inbox/errors/<zip>.log`'a yazılır, geçenler
  `processed/`'a taşınır.
  - 13 unit testi (`app/scripts/ingest-content.test.ts`) geçti.
  - End-to-end smoke: gerçek ZIP → ingest pipeline → sandbox PASS → DB'ye
    Unit+TestGroup yazıldı, PDF kopyalandı, ZIP processed'a taşındı.
  - `make ingest` / `make ingest-dry`: HOST'tan koşar (docker-in-docker path
    translation derdi yok). Postgres `127.0.0.1:5433`'te loopback exposure.

## Bir sonraki adım

Faz 3 sonu merge → Faz 4 — Runner HTTP service (`runner/src/server.ts`,
Express, /run + /healthz, p-limit semaphore, Faz 4.4'te submission DB writes).
