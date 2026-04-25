# System Readiness Playbook

End-to-end checklist for getting the platform from a fresh checkout to a
state where Deniz can start delivering Faz 8 unit content.

## Prerequisites

- Docker Desktop (daemon running)
- Node 22+ + npm (host-side tooling — `make ingest`, dev-mode `next dev`)
- Python 3.11+ (sandbox + harness pytest)
- 4 GB RAM available to Docker

## 1. Bootstrap

```bash
# 1.1 Secrets — copy the template and replace `change_me_*` values.
cp .env.example .env
# Generate strong randoms for JWT_SECRET and RUNNER_SHARED_SECRET:
openssl rand -hex 32   # paste into JWT_SECRET=
openssl rand -hex 32   # paste into RUNNER_SHARED_SECRET=

# 1.2 Build the sandbox image once (separate from the compose stack).
make sandbox

# 1.3 Build the migration helper (used by `make migrate`).
make migrate-build

# 1.4 Bring up postgres + run migrations.
make migrate
```

Verify:

```bash
docker compose exec postgres psql -U iau_user -d iau_platform -c "\dt"
# Expect 9 tables + _prisma_migrations.
```

## 2. Bring up the full stack

```bash
make start    # docker compose up -d --build
make status   # all services should be Up; postgres healthy
```

The first `make start` builds the `iau-app` and `iau-runner` images
(~5 min combined on a cold machine). Subsequent runs are seconds.

Caddy listens on `:80`. Open <http://localhost> — the home page renders
with `Giriş yap / Kayıt ol`.

## 3. Smoke flows

### 3.1 Auth round-trip

1. Visit `/register`, create an account.
2. You land on `/dashboard`. Empty unit list is expected on a fresh DB.
3. Hit `/api/me` directly: returns your user JSON.
4. Click `Çıkış`. `/dashboard` then redirects to `/login`.

### 3.2 Promote yourself to admin

```bash
make promote-admin EMAIL=your-account@example.com
```

Log out and back in (refreshes the session role claim). `/admin` is now
reachable and the navbar shows the admin link.

### 3.3 Sandbox self-test (offline of the app)

```bash
make sandbox-test
```

Expect 3/3 fixtures: `pass` -> `verdict=passed`, `fail` -> `verdict=failed`,
`malicious` -> 3/3 escape attempts contained. See
`docs/sandbox-security-selftest.md` for the threat-mitigation matrix.

### 3.4 First content ingest

Drop a content package into `content/inbox/unit-NN-slug.zip` (see
`02_CONTENT_CONTRACT.md` for the schema). Then:

```bash
make ingest-dry    # validates structure + reference solution; no DB write
make ingest        # commits to DB and lays out content/units/<slug>/
```

Or use the admin UI: `/admin` -> "Tara ve uygula" button. Output appears
inline. (The button is best-effort in compose — if it fails, fall back to
`make ingest` from the host.)

Verify the ingested unit on `/admin`: the unit row appears, toggle
`published` if needed, then a normal student account sees it on their
`/dashboard`.

### 3.5 End-to-end submission

As a logged-in student with at least one published unit:

1. `/dashboard` -> click the unit card.
2. Education page: PDF iframe loads, video embeds work.
3. `/units/<slug>/projects` renders the unit's `projects.md`.
4. `/units/<slug>/final` -> drop the student ZIP.
5. The result panel updates from `QUEUED` -> `RUNNING` -> `PASSED` or
   `FAILED` within ~5 seconds. Per-test rows show `expected` / `actual` /
   `hint` for failed cases.
6. `/units/<slug>/submissions` shows the deneme history.

## 4. Operational checklist

- `make logs` — tail every service together.
- `make stop` — bring everything down (volumes preserved).
- `make reset` — DESTRUCTIVE: drops data volumes after a typed-in `YES`.
- `make ingest-dry` — re-validate inbox without DB writes.
- `make migrate` — apply any new prisma migrations.

## 5. Known caveats

- **internal_net is not `internal: true`.** Caddy still cannot reach
  postgres (it's not on `internal_net`), but `internal: true` blocked
  one-off tooling containers from reaching prisma's binary mirror; we
  rely on segmentation rather than total egress isolation.
- **`/admin` ingest button** runs the ingest in-process inside the app
  container. The script invokes the runner CLI as a subprocess using
  `node --experimental-strip-types`; in compose mode this requires the
  runner CLI to live inside the app image, which it currently does NOT
  (the app image only carries `app/` files). Use `make ingest` from the
  host for the canonical path; the admin button is a v2 nicety.
- **Reference solution check** runs through the actual sandbox — it
  spawns docker, which means `make ingest` needs a working docker daemon
  and the `iau-sandbox` image already built. `make ingest` depends on
  `make sandbox` for that reason.
- **First admin** is bootstrapped via `make promote-admin EMAIL=...`.
  There is no UI flow for the very first admin because the user list
  page is admin-only.

## 6. Phase tags

Each phase ends with an annotated tag on `main`:
`phase-1-complete` ... `phase-7-complete`. Use `git log <tag>..HEAD` to
diff what changed since a phase boundary.
