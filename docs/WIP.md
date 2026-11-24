# Work In Progress

> This file is updated automatically by Claude Code. It shows unfinished work and
> where the next session should pick up.

## Direction (2026-04-25, Deniz)

> Get the system fully ready → then Deniz brings the Phase 8 content.
> From Phase 2.5 through Phase 7, don't wait for approval on each sub-task; do
> end-of-phase merges automatically (gh CLI allowed, §9 + memory). For UI-heavy
> sub-tasks (6.x, 7.x), auto-checks (build / typecheck / smoke) are
> enough — manual visual testing comes LAST, once the whole system is ready.

## Current status

- **Phase:** Phase 2 — Sandbox Image + Harness
- **Status:** System ready. Phases 1-7 → main, `system-ready` tag.
- **Branch:** `main` (chore/readiness merged)
- **Pending:** Phase 8 — Deniz dropping unit content into `content/inbox/`.
- **Remote:** `origin` → `https://github.com/DenizTanisman/Education_Platform_Mine.git`

## Latest status notes

- Large-file strategy: **Option C — excluded from git for now**.
  PDFs, inbox ZIPs and reference solution ZIPs are in `.gitignore`.
  The LFS vs. external storage decision will be made in Phase 8.
- The contract MDs at the root (`00_MASTER_PROMPT.md`, `01_BUILD_PLAN.md`,
  `02_CONTENT_CONTRACT.md`) are tracked by git.
- Phase 1.2 done: 4 services (caddy/app/runner/postgres) come up with placeholder
  images. `http://localhost` returned 200. `internal_net` is isolated
  for postgres, `public_net` is exposed to the host only for caddy.
- Phase 1.3 done: `Makefile` with six targets (`start/stop/logs/status/reset/clean`).
  `reset` is guarded by a "YES" confirm prompt.
- Phase 1 → merged into `main` (PR #2 squash — since feat/makefile was branched
  from feat/compose-skeleton, both sub-tasks landed in a single squash). PR #1 orphaned,
  closed. `phase-1-complete` tag pushed.
- Phase 2.1 done: `infra/sandbox.Dockerfile` — Python 3.11-slim, uid 1001
  (regular, --system removed because of the SYS_UID_MAX warning), pytest/pydantic/anthropic
  pinned, ENTRYPOINT `python /workspace/harness.py`. 240MB. harness.py comes in 2.3.
- Phase 2.2 done: `infra/seccomp.json` — moby v27.3.1 default base,
  extra-deny list (ptrace/unshare/mount/umount/umount2/keyctl/bpf/userfaultfd/
  clone3/reboot) both removed from the ALLOW rules and added at the top as an explicit
  ERRNO block. `scripts/test-seccomp.sh` control+test1+test2 passed.
  Rationale in `docs/sandbox-seccomp.md`.
- Phase 2.3 done: `infra/sandbox/harness.py` + `harness_api.py`,
  the Dockerfile copies both read-only into `/workspace` with `COPY --chmod=0444`.
  Per-test 2s SIGALRM timeout, outer run_tests timeout (default 60s).
  JSON contract (02_CONTENT_CONTRACT.md §3) guaranteed even on
  harness-level failure. `tests/test_harness.py` passed with 13 scenarios + in-container smoke
  (the harness ran even under the full 2.4 security flags).
- Phase 2.4 done: `runner/` TS scaffold (Node 24 native TS, no tsx/ts-node).
  `runner/src/sandbox-runner.ts` — `runSandbox()` + `buildDockerArgs()`.
  All §2.4 flags: `--network=none --read-only --cap-drop=ALL
  --security-opt=no-new-privileges --security-opt=seccomp=... --pids-limit=64
  --memory=512m --memory-swap=512m --cpus=0.5 --tmpfs /tmp:rw,noexec,nosuid,size=64m`.
  A detached watchdog hard-stops the container with `docker kill` (the spawnSync
  timeout only kills the CLI client, not the container — belt+suspenders).
  stdout/stderr 1MB cap (maxBuffer). Outcome union: ok/timeout/crash/invalid_json/output_truncated.
  Integration suite 8/8: arg construction (2) + happy/timeout/network/readonly/
  fork-bomb-containment/fail-propagation (6).

- Phase 2.5 done: `runner/src/cli.ts` (thin CLI), `scripts/test-sandbox.sh`,
  `scripts/sandbox-examples/{pass,fail,malicious}/{tests,code}/`,
  `docs/sandbox-security-selftest.md`, `sandbox` and `sandbox-test`
  targets added to the Makefile. 3/3 examples verified: pass→passed, fail→failed (clean
  diff), malicious→3/3 escapes contained (URLError/OSError/ptrace rv=-1).
- Phase 2 → main: PRs reopened (downstream PRs get closed on every squash —
  pattern is in memory). 5 PRs squash-merged in order, `phase-2-complete` tag pushed.
- Phase 3.1 done: `app/prisma/schema.prisma` — 9 models (User, Unit, Video,
  Project, TestGroup, TestCase, UnitProgress, Submission, SubmissionTestResult)
  + 4 enums. Migrations: `init` + `running_submission_partial_unique` (raw SQL
  partial unique index, Prisma doesn't support it natively yet). `app/Dockerfile.migrate`
  (node:20-slim + openssl) and the `make migrate-build` / `make migrate` targets.
  The `internal: true` flag on `internal_net` was removed — segmentation stays
  (Caddy can't see postgres) but one-off tooling containers
  can fetch the Prisma binaries.

- Phases 3.2 + 3.3 done: `app/scripts/ingest-content.ts` — filename regex,
  ZIP extraction (adm-zip), unit.yaml parse (yaml), required-files check,
  reference solution sandbox check (runner CLI), Prisma upsert (Unit, Video,
  Project, TestGroup; TestCase lazily on first submission). `--dry-run` flag.
  Broken ZIPs are logged to `content/inbox/errors/<zip>.log`, passing ones
  are moved to `processed/`.
  - 13 unit tests (`app/scripts/ingest-content.test.ts`) passed.
  - End-to-end smoke: real ZIP → ingest pipeline → sandbox PASS → Unit+TestGroup
    written to the DB, PDF copied, ZIP moved to processed.
  - `make ingest` / `make ingest-dry`: run from the HOST (no docker-in-docker path
    translation hassle). Postgres exposed on loopback at `127.0.0.1:5433`.

- Phase 3 → main, `phase-3-complete` tag pushed.
- Phases 4.1-4.4 done: `runner/src/{server,queue,runner-core,db}.ts` —
  Express + Zod + p-limit (4 concurrent / 10 queued / 429 beyond), shared
  secret middleware (`x-runner-secret`, constant-time), 10MB JSON body cap,
  graceful shutdown with 30s drain. End-to-end: ZIP extract → sandbox call →
  Prisma transaction (Submission + SubmissionTestResult, lazy TestCase
  upsert by extId) → UnitProgress unlock-next-on-pass. `app/prisma/schema.prisma`
  also writes to `runner/node_modules/.prisma/client/` via a second generator block
  (cross-package Prisma access without needing npm workspaces).
  - `runner/tests/server.test.ts`: 4 HTTP/auth + 1 full E2E (real sandbox +
    real Prisma write + UnitProgress verify) — 12/12 PASS in total
    (sandbox-runner integration 6/6 + arg construction 2/2 + server 4/0).

- Phase 4 → main, `phase-4-complete` tag pushed.
- Phases 5.1-5.4 done: Next.js 15 scaffold (App Router), NO Tailwind
  (plain globals.css), tsconfig + standalone output. `app/lib/auth.ts`
  (Node, bcrypt + signSession + maybeRefresh), `app/lib/auth-edge.ts`
  (jose-only verifySession — so the middleware doesn't leak bcrypt into the edge bundle),
  `app/lib/rate-limit.ts` (in-memory sliding window). API routes:
  /api/{register,login,logout,me,healthz}. Middleware role guard for /admin,
  JWT gate on protected routes. UI pages: /, /login (useSearchParams
  wrapped in Suspense), /register, /dashboard (Phase 6 placeholder).
  - Tests: 27/27 PASS (auth 8 + rate-limit 6 + ingest 13).
  - Build: clean, 12 routes, middleware 39.8 kB.
  - End-to-end smoke: register→cookie set, /api/me→user data, login bad pw→401,
    logout→cookie clear, /api/me afterwards→401, /dashboard→307 to /login.

- Phases 5, 6, 7 all → main + `phase-5-complete` / `phase-6-complete` /
  `phase-7-complete` tags pushed.
- Production Dockerfiles (`app/Dockerfile`, `runner/Dockerfile`),
  compose wiring (build:./app + build:./runner, content + seccomp +
  docker.sock + same-path repo bind mount, REPO_ROOT env), Caddyfile
  moved to app:3000, `make promote-admin EMAIL=...`, `docs/READINESS.md`.
- End-to-end compose smoke: register → /api/me → ingest → final upload →
  runner dispatch → docker-in-docker sandbox → PASSED → UnitProgress
  COMPLETED → admin pages reachable. **The submission reached a terminal state
  in a single poll (~600ms total)**.
- `system-ready` tag pushed.

## Next step

Phase 8 — Deniz prepares the unit content and drops it in the
`content/inbox/unit-NN-slug.zip` format. `make ingest` (from the host) records it in the DB. Manual test
playbook: `docs/READINESS.md`.
