# IAU AI Platform — Build Plan

> This document defines the project's 8 phases and the sub-tasks of each phase.
> Each sub-task is a separate "stop": Claude Code builds it → self-test → (Deniz tests if needed) → commit + push → next.

**Status icons:**
- ⬜ Not done
- 🔄 Active
- ✅ Done, committed, pushed
- ⏸ Paused (waiting for Deniz's feedback)
- 🧪 Waiting for Deniz's manual test

**Sub-task type icons (00_MASTER_PROMPT.md §3):**
- 🤖 Auto-verifiable — if the Claude Code self-test PASSES, don't stop: push + continue
- 👤 Manual test needed — wait for Deniz's approval after the self-test

---

## CURRENT STATUS

**Phase:** `Phase 1 — Repo Skeleton`
**Sub-task:** `1.1 — Directory structure and git init`
**Last approval:** (none yet)

---

## Phase 1 — Repo Skeleton

Goal: An empty but working Docker Compose stack. No features, just
services coming up.

### 1.1 ⬜ 🤖 Directory structure and git init

**Exceptional approval points (specific to this sub-task, Deniz's input needed):**
1. GitHub repo name approval (e.g. `iau-ai-platform-v3`, private)
2. Large file strategy: Git LFS or external storage (see 00_MASTER_PROMPT.md §9.7)

Once these two questions are answered, the rest runs automatically.

- [ ] The following folders are created in the project root:
  ```
  app/ runner/ infra/ scripts/ docs/ content/inbox/ content/units/
  ```
- [ ] `.gitignore` (Node, Python, Docker, .env, .DS_Store, content PDFs/ZIPs)
- [ ] `README.md` placeholder (one line: "IAU AI platform, v3 in progress")
- [ ] `git init`, initial commit: `chore: initial repo scaffold`
- [ ] `docs/WIP.md` is created (content: "Faz 1.1 devam ediyor" — "Phase 1.1 in progress")
- [ ] GitHub remote setup (one-time approval from Deniz, see §9.1)

**Self-test:**
- `tree -L 2` output shows the structure above
- `git log` shows the first commit
- `git remote -v` shows origin
- `git push origin main` succeeds

**Deniz test:** None (automatic, done once the push succeeds).

### 1.2 ⬜ 🤖 docker-compose.yml skeleton

- [ ] 4 services defined: `caddy`, `app`, `runner`, `postgres`
- [ ] Two networks: `public_net`, `internal_net`
- [ ] Caddy only on `public_net`, postgres only on `internal_net`
- [ ] App on both networks, runner only on `internal_net`
- [ ] Services come up with "hello world" placeholder images
  (nginx:alpine, hello-world, etc.)
- [ ] `.env.example` filled in with all variables
- [ ] `infra/Caddyfile` minimal reverse proxy

**Self-test:**
- `docker compose config` syntax is valid
- `docker compose up -d` comes up without errors
- `docker compose ps` shows all "running"

**Deniz test:**
- Copy `.env.example` to `.env`
- Run `docker compose up -d`
- Does `http://localhost` respond?

### 1.3 ⬜ 🤖 Makefile and basic commands

- [ ] `make start` — `docker compose up -d --build`
- [ ] `make stop` — `docker compose down` (volumes kept)
- [ ] `make logs` — logs of all services
- [ ] `make status` — `docker compose ps` + health
- [ ] `make reset` — `docker compose down -v` (DANGEROUS, confirm prompt)
- [ ] `make clean` — remove containers, keep volumes
- [ ] All commands `.PHONY`

**Self-test:**
- Every command is run at least once
- `make reset` shows a "bunu yapmak istediğinizden emin misiniz" ("are you sure you want to do this") prompt on a wrong answer

**Deniz test:**
- Run `make start`, `make logs`, `make stop` in order

---

## Phase 2 — Sandbox Image + Harness

Goal: A Docker image and harness script that run student code safely.
Testable independently of the rest of the platform.

### 2.1 ⬜ 🤖 Sandbox Dockerfile

- [ ] `infra/sandbox.Dockerfile`: Python 3.11-slim base
- [ ] Non-root user (uid 1001)
- [ ] `/workspace` directory, student code will be mounted here read-only
- [ ] Pre-installed: pytest, pydantic, anthropic (minimal, only what tests need)
- [ ] Entrypoint: `python /workspace/harness.py`

**Self-test:**
- `docker build -t iau-sandbox:latest -f infra/sandbox.Dockerfile .` succeeds
- `docker run --rm iau-sandbox:latest python --version` → 3.11.x

### 2.2 ⬜ 🤖 Seccomp profile

- [ ] `infra/seccomp.json` — minimal syscall permissions
  - Base: Docker default seccomp
  - Extra deny: `ptrace`, `unshare`, `mount`, `umount`, `keyctl`, `bpf`,
    `userfaultfd`, `clone3` (newuser), `reboot`
- [ ] Documented: which syscall is blocked and why

**Self-test:**
- `python scripts/test-seccomp.sh` — the ptrace call is blocked
- Normal Python execution is unaffected

### 2.3 ⬜ 🤖 Harness.py (test runner)

- [ ] Looks for student code under `/workspace/code/`
- [ ] Imports the `/workspace/tests/test_runner.py` file
- [ ] Executes the test cases, with a timeout (2s) for each
- [ ] JSON output format (see 02_CONTENT_CONTRACT.md §3):
  ```json
  {
    "summary": {"total": N, "passed": N, "failed": N, "runtime_ms": N, "verdict": "passed|failed"},
    "groups": [{"name": "...", "tests": [...]}]
  }
  ```
- [ ] For each test case: id, status, expected, actual, input, hint
- [ ] Crash case (student code throws): caught, `status: "errored"`
- [ ] Timeout case: `status: "timeout"`
- [ ] Memory over limit: caught outside the runner (container kill)

**Self-test:**
- `pytest tests/test_harness.py` — 10+ scenarios (pass/fail/timeout/crash)

### 2.4 ⬜ 🤖 Hardened docker run command

- [ ] `runner/src/sandbox-runner.ts` — docker call via spawnSync
- [ ] All security flags (see 00_MASTER_PROMPT.md §2.4)
- [ ] Stdout 1MB cap, stderr 1MB cap
- [ ] Exit code is interpreted: 0 → parse JSON; 124 → timeout; other → crash

**Self-test:**
- Manual test: ZIP containing a fork bomb → container kill, error response
- Manual test: network access → `socket.gaierror` (no DNS)
- Manual test: file write to `/etc/` → permission denied

### 2.5 ⬜ 🤖 End-to-end sandbox test

- [ ] `scripts/test-sandbox.sh` — prepares a sample ZIP, calls the runner, returns JSON
- [ ] `docs/sandbox-security-selftest.md` — security test report

**Deniz test:**
- Run `make sandbox`
- `./scripts/test-sandbox.sh examples/pass.zip` → PASS report
- `./scripts/test-sandbox.sh examples/fail.zip` → FAIL report + details
- `./scripts/test-sandbox.sh examples/malicious.zip` → error, host unaffected

---

## Phase 3 — Prisma Schema + Content Discovery

Goal: The database schema and a script that loads the `content/units/` folder into the DB.

### 3.1 ⬜ 🤖 Prisma schema

- [ ] `app/prisma/schema.prisma` — the following models:
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
- `npx prisma migrate dev --name init` succeeds
- `npx prisma studio` opens, tables are visible

### 3.2 ⬜ 🤖 Content ingest script

- [ ] `scripts/ingest-content.ts` — scans the `content/inbox/` folder
- [ ] Format: `unit-XX-<slug>.zip` (see 02_CONTENT_CONTRACT.md)
- [ ] ZIP validation: schema check, are the required files present
- [ ] If invalid, writes to `content/inbox/errors/<zip-name>.log`
- [ ] If valid, extracts into `content/units/unit-XX-<slug>/`
- [ ] DB upsert: into the Unit, Video, Project, TestGroup, TestCase tables
- [ ] Copies PDFs into `app/public/pdfs/`
- [ ] Leaves test_runner.py in `content/units/.../tests/`
- [ ] On success, moves the ZIP into the `content/inbox/processed/` folder
- [ ] Dry-run mode: with the `--dry-run` flag, makes no DB changes, only validates

**Self-test:**
- A sample unit-00-welcome.zip is prepared
- `npm run ingest -- --dry-run` → validation OK
- `npm run ingest` → a Unit row is created in the DB
- Broken ZIP → log in the errors folder

### 3.3 ⬜ 🤖 Ingest trigger mechanism

- [ ] `make ingest` command → `docker compose exec app npm run ingest`
- [ ] (Optional v2) File watcher: automatic triggering with `chokidar`
- [ ] Endpoint for manual triggering from the Admin UI (admin role only)

**Deniz test:**
- Drop a sample unit ZIP into `content/inbox/`
- Run `make ingest`
- See the Unit row with `npx prisma studio`
- It appears on the `http://localhost/admin/units` page (via a DB query if the page doesn't exist yet)

---

## Phase 4 — Runner Service

Goal: An HTTP service that accepts submission requests from Next.js, spawns the sandbox,
and returns the result.

### 4.1 ⬜ 🤖 Runner skeleton (Express + TypeScript)

- [ ] `runner/package.json`, `runner/tsconfig.json`
- [ ] `runner/src/server.ts` — Express, `/healthz`, `/run` endpoints
- [ ] Shared secret middleware (`x-runner-secret` header)
- [ ] Request body validation (Zod): unitId, zipBuffer, submissionId
- [ ] Size check: 10MB max

### 4.2 ⬜ 🤖 In-memory semaphore + queue

- [ ] Max 4 concurrent with `p-limit`
- [ ] Wait queue max 10 (429 if full)
- [ ] Submission tracking: start time, status
- [ ] Graceful shutdown: doesn't exit before current jobs finish (30s timeout)

### 4.3 ⬜ 🤖 Sandbox orchestration

- [ ] `runner/src/sandbox.ts` — the hardened docker run wrapper from Phase 2.4
- [ ] ZIP extract to `/tmp/sub-<uuid>/`
- [ ] Fetch test runner files from the DB (via Prisma Client)
- [ ] Container spawn, stdout parse
- [ ] Temp directory cleanup (regardless of success/failure)

### 4.4 ⬜ 🤖 Report post-processing

- [ ] Map the harness JSON to the Prisma schema
- [ ] Write SubmissionTestResult rows
- [ ] Update Submission.status (passed/failed)
- [ ] On pass, update UnitProgress and unlock the next Unit

**Self-test:**
- Integration test: sample submission → full flow → correct rows in the DB

**Deniz test:**
- `curl -X POST http://localhost:4000/run -H "x-runner-secret: ..." -F "zip=@..."`
- Response: JSON report
- New Submission + Results in the DB

---

## Phase 5 — Next.js Auth

Goal: User register/login/logout, route guard, rate limit.

### 5.1 ⬜ 🤖 Auth library (jose + bcrypt)

- [ ] `app/lib/auth.ts` — JWT sign/verify, httpOnly cookie
- [ ] bcrypt cost 12
- [ ] Timing-safe password compare
- [ ] Session expiry: 7 days, sliding renewal

### 5.2 ⬜ 🤖 API routes

- [ ] POST `/api/register` — email+password, duplicate check
- [ ] POST `/api/login` — credential check, cookie set
- [ ] POST `/api/logout` — cookie clear
- [ ] GET `/api/me` — current user info
- [ ] Rate limit: 5 req/hour per IP for register+login

### 5.3 ⬜ 🤖 Middleware (edge)

- [ ] `app/middleware.ts` — verify JWT for protected routes
- [ ] Role check for admin-only routes
- [ ] Public routes: `/`, `/login`, `/register`, `/healthz`

### 5.4 ⬜ 👤 Register & Login UI

- [ ] `/register` form (Zod validation, client + server)
- [ ] `/login` form
- [ ] Error handling: user already exists, wrong password, rate limit

**Deniz test:**
- Register → login → me endpoint → logout flow
- Rate limit: the 6th register attempt returns 429

---

## Phase 6 — Student UI

Goal: Dashboard, education, projects, and final pages.

### 6.1 ⬜ 👤 Dashboard
- [ ] Course list, unit cards
- [ ] For each unit: locked / in_progress / completed visual state
- [ ] The selected unit is kept in localStorage

### 6.2 ⬜ 👤 Education page
- [ ] PDF iframe (app/public/pdfs/)
- [ ] YouTube video embed
- [ ] Projects/final links in the side panel

### 6.3 ⬜ 👤 Projects page
- [ ] Render projects.md with react-markdown
- [ ] "Final'e geç" ("Go to the final") button (if not locked)

### 6.4 ⬜ 👤 Final page
- [ ] ZIP upload (drag & drop)
- [ ] Client-side pre-validation (size, extension)
- [ ] Status polling after upload (pending → running → done)
- [ ] Result screen: per-test details following the Phase 3 mockup
- [ ] Submission history link
- [ ] "Yeniden dene" ("Try again") button (NO cooldown)

### 6.5 ⬜ 👤 Submission history
- [ ] List of past attempts
- [ ] A detail page for each

**Deniz test:**
- Log in as a user → open a unit → read projects → upload ZIP → see the result
- 3 attempts in a row can be made for the same unit

---

## Phase 7 — Admin UI

Goal: Unit management UI (for manual editing outside of content-as-code).

### 7.1 ⬜ 👤 Admin dashboard
- [ ] Unit list, published toggle
- [ ] User list, role change
- [ ] Submission history (all users)

### 7.2 ⬜ 👤 Content ingest trigger
- [ ] "content/inbox'ı tara" ("Scan content/inbox") button in the UI → ingest runs
- [ ] Shows the operation logs

### 7.3 ⬜ 👤 Analytics page
- [ ] Total users, completed units, average number of attempts
- [ ] Pass rate for each unit

**Deniz test:**
- Log in with the admin account, try all management actions

---

## Phase 8 — Unit Content (together with Deniz)

Goal: Preparing the instructions + reference solution ZIPs for each unit.

This phase is **not something Claude Code does on its own**. Content prepared together
with Deniz in this main chat is packaged according to 02_CONTENT_CONTRACT.md
and dropped at the `content/inbox/` gate. Claude Code only runs the ingest.

Units are prepared in order:
- Unit 00 — Platform introduction (hello_world final)
- Unit 01 — (to be decided with Deniz)
- Unit 02 — ...
- (And so on)

What Deniz does for each unit (see 02_CONTENT_CONTRACT.md):
1. Prepare education.pdf
2. Write projects.md
3. Prepare test_runner.py, test it locally
4. Prepare pass_final.zip in the reference_solution/ folder
5. Package everything as a single ZIP
6. Drop it as `content/inbox/unit-XX-slug.zip`
7. Run `make ingest`
8. The Unit appears in the DB and is accessible in the UI

---

## CONTINUATION RULES

- A short retrospective at the end of each phase: what went well, what problems came up.
- A `docs/phase-X-report.md` file is created at the end of the phase.
- The new phase starts when Deniz says "move to the next phase".
