# Work In Progress

> Bu dosya Claude Code tarafından otomatik güncellenir. Yarım kalan işi ve
> bir sonraki session'ın nereden devam edeceğini gösterir.

## Aktif durum

- **Faz:** Faz 1 — Repo İskeleti
- **Alt-task:** 1.3 — Makefile ve temel komutlar (tamam). Faz 1 bitti.
- **Branch:** `feat/makefile` (pushed)
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

## Bir sonraki adım

Faz 1 tüm alt-task'ları bitti (1.1, 1.2, 1.3). §9.3 gereği faz sonu merge
zamanı: `feat/compose-skeleton` ve `feat/makefile` branch'lerini `main`'e
sırayla squash-merge + `phase-1-complete` tag. Deniz onayı bekleniyor.

Sonra Faz 2 — Sandbox Image + Harness başlar.
