# IAU AI Platform

An online course platform that teaches AI **unit by unit, through practice**.
Each unit follows the same loop: read the lesson notes → study the project
instructions → write your own code → upload it as a ZIP → automated tests
return a result within a few seconds. Pass, and the next unit unlocks.

> **Inspiration:** the [42 Ecole](https://42.fr) philosophy — project-based,
> self-paced learning built on writing your own code and passing tests
> instead of listening to lectures. There is no peer grading here; instead,
> for each unit a **reference solution** and **harness-compatible test
> sets** prepared by Deniz grade submissions instantly inside a sandbox.

## Course content

A 9-unit Python + LLM automation track (each unit is roughly 3-5 hours of
work). The course material itself is in Turkish; unit titles are shown
below in English:

| # | Slug | Topic |
|---|---|---|
| 0 | `environment` | Development Environment and Python Basics |
| 1 | `python-reflexes` | Python Automation Reflexes |
| 2 | `api-json` | APIs and JSON |
| 3 | `llm-sdk` | Direct Connection with an LLM SDK |
| 4 | `structured-output` | Structured Output with Pydantic |
| 5 | `function-calling` | Tool Use with Function Calling |
| 6 | `memory` | Stateful Agent with Memory |
| 7 | `rag` | Document-Based Assistant with RAG |
| 8 | `capstone` | Capstone — Mini Jarvis |

## Architecture

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

**Components:**

- **Next.js 15** — App Router, server components, NO Tailwind (plain
  globals.css). Auth: jose JWT + bcrypt + httpOnly cookie + edge middleware.
- **Runner** — Node 22 + native TS strip-types, Express + Zod + p-limit.
  Spawns a fresh sandbox container for every submission.
- **Sandbox** — Python 3.11-slim + harness + course deps (pytest,
  pydantic, anthropic, requests, openai, python-dotenv). For the duration
  of a submission it runs under **`--network=none --read-only --cap-drop=ALL`**
  and a custom seccomp profile; each test has a 2s wall-clock
  timeout, and a watchdog kills the container after 10s.
- **Caddy** — Reverse proxy; static-serves the lesson PDFs under
  `/pdfs/*` directly (because Next.js standalone does not serve
  public/).
- **Postgres 16** — Schema via Prisma 5 (User, Unit, Video, Project,
  TestGroup, TestCase, UnitProgress, Submission, SubmissionTestResult).

## Quick start

### Requirements

- Docker Desktop (daemon running)
- Node 22+ and npm (host side: `make ingest`, dev mode)
- macOS / Linux (Windows not tested)

### Step by step

```bash
# 1. Clone the repo
git clone https://github.com/DenizTanisman/Education_Platform_Mine.git
cd Education_Platform_Mine

# 2. Create the secrets. .env is in .gitignore, so you have to create it by hand.
cp .env.example .env

# Generate JWT_SECRET and RUNNER_SHARED_SECRET with openssl
# (at least 32 characters):
openssl rand -hex 32   # → paste into the JWT_SECRET line in .env
openssl rand -hex 32   # → paste into the RUNNER_SHARED_SECRET line in .env

# 3. Build the sandbox image once (independent of compose).
make sandbox

# 4. Migration helper image + DB migration.
make migrate

# 5. Bring up the whole stack (app + runner + caddy + postgres).
make start

# 6. Load the content into the DB (the 9 unit ZIPs are ready in
#    content/inbox/processed/, but the DB rows need an ingest):
cp content/inbox/processed/*.zip content/inbox/
make ingest

# 7. Open http://localhost in your browser.
```

### Usage

**As a student:**

1. Sign up via `/register`.
2. `/dashboard` → Unit 00 shows as "open"; click its card.
3. On the Education page, read the lesson notes in the PDF iframe.
4. Follow the "Proje talimatları →" (project instructions) link and read `projects.md`.
5. Write the code locally and package it as `submission.zip`.
6. Drag and drop it on the "Final ZIP yükle →" (upload final ZIP) page.
7. Within ~5 seconds you see **PASSED** or **FAILED** plus per-test details
   (expected / actual / hint).
8. Once you pass, Unit 01 unlocks automatically.

**As an admin:**

The first admin has to be promoted from the terminal — the UI flow is
admin-only, so you cannot make yourself an admin:

```bash
make promote-admin EMAIL=senin-emailin@example.com
```

Then **log out and log back in** (so the role claim in the JWT cookie is
refreshed). You now have access to the `/admin` panel:

- Unit list + `published` toggle
- User list + role flip
- Content ingest trigger (best-effort; host-side `make ingest` is
  more reliable)
- Analytics (pass rate, average attempts, etc.)
- Audit of all attempts (last 200)

## Content format (Phase 8 — adding a new unit)

To prepare a new unit, follow the schema in
`02_CONTENT_CONTRACT.md`:

```
unit-NN-slug.zip
├── unit.yaml                # metadata: order, slug, title, test_groups
├── education.pdf            # lesson notes (max 20MB)
├── projects.md              # project instructions (markdown)
├── tests/
│   └── test_runner.py       # harness-compatible test file
├── reference/
│   └── pass_final.zip       # passing reference solution (required —
│                            #   tested in the sandbox during ingest)
└── videos.yaml              # optional — YouTube embed list
```

Drop the ZIP into `content/inbox/`, validate it with `make ingest-dry`, and
if it is clean write it to the DB with `make ingest`. During ingest **the
reference solution is run in the sandbox** — if it fails, the unit is
rejected and the error is written under `content/inbox/errors/`.

Details: `02_CONTENT_CONTRACT.md` (structure), `docs/READINESS.md` (operational
playbook).

## Missing / manual steps

- **The `.env` file** is not in the repo (it holds secrets, so it is in
  `.gitignore`). Create it with `cp .env.example .env` and replace
  `JWT_SECRET` and `RUNNER_SHARED_SECRET` with `openssl rand -hex 32`.
- **The first admin** is created from the terminal with
  `make promote-admin EMAIL=...`. It cannot be done from the UI because the
  user list is ADMIN-only.
- **Migration and ingest** are not automatic. Run `make migrate` (on every
  schema change) and `make ingest` (for every new unit ZIP) by hand.
- **The "Tara ve uygula" (scan and apply) button in the `/admin` panel** is
  best-effort inside compose — it fails in some cases because the runner CLI
  is not present in the app container. The canonical path: `make ingest`
  from the host.
- **The Postgres host port (5433)** is for development only (prisma
  studio + host-side ingest). Remove this mapping in production.
- **The sandbox runner runs with gid 0 (root group)** — to access the
  Docker socket. In practice this has no security impact (the runner
  already talks to the host docker daemon), but for production-grade a
  separate docker daemon (e.g. dind, sysbox) could be considered.

## Development & testing

```bash
# Sandbox security test (3 fixtures: pass / fail / malicious)
make sandbox-test

# Pytest harness suite (host)
cd app && npm test            # 27/27 — auth, rate-limit, ingest

# Runner integration suite (host, real docker)
cd runner && npm test         # 12/12 — sandbox flags, queue, e2e

# Type-check
cd app && npm run typecheck
cd runner && npm run typecheck

# Stack checks
make logs       # logs of all services
make status     # docker compose ps + health
make stop       # down (volumes kept)
make reset      # DESTRUCTIVE — volumes are deleted, "YES" confirm prompt
```

## Phase map

Each phase is marked with an annotated tag on `main`:

| Tag | Contents |
|---|---|
| `phase-1-complete` | Repo skeleton + Docker compose + Makefile |
| `phase-2-complete` | Sandbox image, seccomp, harness, hardened runner wrapper |
| `phase-3-complete` | Prisma schema + content ingest pipeline |
| `phase-4-complete` | Runner HTTP service (Express + queue + Prisma write-back) |
| `phase-5-complete` | Auth (jose JWT + bcrypt + login/register UI) |
| `phase-6-complete` | Student UI (dashboard / education / projects / final / submissions) |
| `phase-7-complete` | Admin UI (panel / ingest / analytics / audit) |
| `system-ready` | Production Dockerfiles + compose wiring + READINESS playbook |
| `faz-8-content-loaded` | 9 units (Automation course) ingested + tracked |

Use `git log <tag>..HEAD` to diff along phase boundaries.

## Contract files

The repo keeps its planning not in in-code documentation but in the
**contract MDs at the root**:

- `00_MASTER_PROMPT.md` — Claude Code working rules, ownership
  boundaries, security constants
- `01_BUILD_PLAN.md` — 8 phases × N sub-tasks roadmap
- `02_CONTENT_CONTRACT.md` — Phase 8 content delivery schema
- `docs/READINESS.md` — operational playbook + manual test flows
- `docs/sandbox-seccomp.md` — seccomp profile rationale
- `docs/sandbox-security-selftest.md` — threat → mitigation matrix
- `docs/WIP.md` — unfinished work + next step

## License

The content (PDFs, projects.md, test_runner.py files) belongs to Deniz
Tanışman and may not be copied without permission. The platform code
(Next.js, runner, sandbox) may be split out under MIT later — private
for now.
