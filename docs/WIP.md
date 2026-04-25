# Work In Progress

> Bu dosya Claude Code tarafından otomatik güncellenir. Yarım kalan işi ve
> bir sonraki session'ın nereden devam edeceğini gösterir.

## Aktif durum

- **Faz:** Faz 2 — Sandbox Image + Harness
- **Alt-task:** 2.1 — Sandbox Dockerfile (tamam)
- **Branch:** `feat/sandbox-dockerfile`
- **Faz 1:** merged to `main`, `phase-1-complete` tag pushed.
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

## Bir sonraki adım

Alt-task 2.2 — Seccomp profili (`infra/seccomp.json`, deny list: ptrace/unshare/
mount/umount/keyctl/bpf/userfaultfd/clone3/reboot).
